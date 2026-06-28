"""
Acceptance test for U7 — engine.run_backtest (the day-by-day portfolio simulator).
=================================================================================

The engine is the INTEGRATION unit, so these tests pin the loop's decisions, not the
signal math: events.trades_for is monkeypatched to return CRAFTED Trades, and the
`cache` is a tiny stub of hand-made Close series. That makes the timeline fully
deterministic, so we can assert exactly when the engine opens, skips, and rotates.

  * Scenario A (capacity) — with a 2-position cap and three trades that never exit,
    exactly two open and the third is tallied as skipped-for-no-room.
  * Scenario B (rotation) — with a 1-position cap, a held winner near its target is
    sold ("rotated") to fund a fresh entry under the nearest_to_target_band rule, but
    the same setup under the `none` rule skips the new entry instead.
  * Plus: the Result carries a non-empty equity curve and the expected metric keys.
"""
import pandas as pd

from pinescan.backtest import engine, events
from pinescan.backtest.contracts import Trade
from pinescan.backtest.rules.registry import Policy

# Three consecutive trading days used across the scenarios.
D1 = pd.Timestamp("2024-01-01")
D2 = pd.Timestamp("2024-01-02")
D3 = pd.Timestamp("2024-01-03")


def _policy(rotation, rotation_params=None, total=1_000_000, per_trade=200_000,
            max_concurrent=10):
    """A Policy built straight from fields (no JSON) so each test dials in exactly the
    cap and rotation rule it needs. Costs are zeroed so the cash arithmetic the
    assertions rely on stays exact; the shipped rule names resolve via the registry."""
    return Policy(
        name=f"test-{rotation}", description="",
        total_capital=total, max_concurrent=max_concurrent,
        sizing="fixed_amount", sizing_params={"amount": per_trade},
        selection="free_capital_first",
        rotation=rotation, rotation_params=rotation_params or {},
        exit="scanner_default", costs={},
    )


def _open_trade(symbol, entry_date, entry_price, target, sl):
    """A crafted Trade with NO natural exit (natural_outcome='open'), so the engine
    never closes it on its own — it stays open until the cap/rotation logic acts or the
    backtest ends. This isolates the capacity/rotation behavior under test."""
    return Trade(
        symbol=symbol, swing="T1", entry_date=entry_date, entry_price=entry_price,
        target=target, sl=sl, natural_exit_date=None, natural_outcome="open",
    )


def _cache(closes_by_symbol):
    """Stub cache: {symbol -> OHLCV-shaped df with just the Close column the engine
    reads}. Each value is {date: close}; the engine takes df['Close'] and indexes it by
    date, exactly as it would a real bar frame."""
    return {
        sym: pd.DataFrame({"Close": list(closes.values())}, index=list(closes.keys()))
        for sym, closes in closes_by_symbol.items()
    }


def _patch_trades(monkeypatch, crafted):
    """Make events.trades_for return the crafted trades for each symbol. Patching the
    module attribute works because engine.py calls events.trades_for via the module."""
    monkeypatch.setattr(events, "trades_for",
                        lambda sym, df, params=None: list(crafted.get(sym, [])))


# --------------------------------------------------------------------------------------
# Scenario A — capacity: cap of 2, three never-exiting trades => 2 open, 1 skipped.
# --------------------------------------------------------------------------------------
def test_capacity_caps_open_positions_and_counts_skips(monkeypatch):
    # Three symbols, each one trade firing on a different day; all stay open forever.
    crafted = {
        "S1": [_open_trade("S1", D1, 100.0, 120.0, 95.0)],
        "S2": [_open_trade("S2", D2, 100.0, 120.0, 95.0)],
        "S3": [_open_trade("S3", D3, 100.0, 120.0, 95.0)],
    }
    _patch_trades(monkeypatch, crafted)
    # Flat price 100 on every day for every symbol — pnl is irrelevant to this test.
    cache = _cache({s: {D1: 100.0, D2: 100.0, D3: 100.0} for s in ("S1", "S2", "S3")})

    policy = _policy(rotation="none", max_concurrent=2)   # cap = 2
    result = engine.run_backtest(cache, policy)

    # Exactly two distinct symbols ever opened (they appear in the closed ledger as the
    # end-of-data "open_at_end" exits); the third never opened.
    opened_symbols = {ct.symbol for ct in result.closed}
    assert opened_symbols == {"S1", "S2"}
    assert all(ct.outcome == "open_at_end" for ct in result.closed)
    assert len(result.closed) == 2

    # The third signal hit a full book with no rotation -> tallied as skipped.
    assert result.counters["signals_skipped_no_cash"] >= 1
    assert result.counters["rotations_triggered"] == 0


# --------------------------------------------------------------------------------------
# Scenario B — rotation: cap of 1, a winner near target funds a fresh entry (or not).
# --------------------------------------------------------------------------------------
def _scenario_b(rotation, rotation_params=None):
    """Shared setup: X opens D1 and rises to 119 (95% of the way to its 120 target) by
    D3; Y's entry fires on D3 while the single slot is full. Returns (cache, crafted)."""
    crafted = {
        "X": [_open_trade("X", D1, 100.0, 120.0, 90.0)],   # held winner, near target
        "Y": [_open_trade("Y", D3, 50.0, 60.0, 45.0)],     # fresh entry, fires while full
    }
    cache = _cache({
        "X": {D1: 100.0, D2: 110.0, D3: 119.0},            # 119 -> distance_to_target 0.95
        "Y": {D1: 50.0, D2: 50.0, D3: 50.0},
    })
    return cache, crafted


def test_rotation_band_rule_sells_winner_to_fund_new_entry(monkeypatch):
    cache, crafted = _scenario_b("nearest_to_target_band")
    _patch_trades(monkeypatch, crafted)
    policy = _policy(rotation="nearest_to_target_band",
                     rotation_params={"start": 10, "step": 10, "max": 40},
                     total=200_000, per_trade=200_000, max_concurrent=1)

    result = engine.run_backtest(cache, policy)

    # X was sold to make room -> recorded as a "rotated" exit, and the counter ticked.
    rotated = [ct for ct in result.closed if ct.outcome == "rotated"]
    assert [ct.symbol for ct in rotated] == ["X"]
    assert result.counters["rotations_triggered"] >= 1

    # Y got the freed slot: it opened, so it appears in the ledger (closed at end-of-data).
    assert any(ct.symbol == "Y" for ct in result.closed)
    assert result.counters["signals_skipped_no_cash"] == 0


def test_no_rotation_rule_skips_the_new_entry(monkeypatch):
    # Identical setup, but the `none` rotation rule frees nothing -> Y is skipped.
    cache, crafted = _scenario_b("none")
    _patch_trades(monkeypatch, crafted)
    policy = _policy(rotation="none", total=200_000, per_trade=200_000, max_concurrent=1)

    result = engine.run_backtest(cache, policy)

    # Nothing rotated, the new signal was skipped, and X never left until end-of-data.
    assert result.counters["rotations_triggered"] == 0
    assert result.counters["signals_skipped_no_cash"] >= 1
    assert all(ct.symbol != "Y" for ct in result.closed)       # Y never opened
    assert [ct.outcome for ct in result.closed] == ["open_at_end"]
    assert result.closed[0].symbol == "X"


# --------------------------------------------------------------------------------------
# The Result shape: a non-empty equity curve and the metric keys report.py expects.
# --------------------------------------------------------------------------------------
def test_result_has_metrics_and_equity_curve(monkeypatch):
    crafted = {"X": [_open_trade("X", D1, 100.0, 120.0, 90.0)]}
    _patch_trades(monkeypatch, crafted)
    cache = _cache({"X": {D1: 100.0, D2: 110.0, D3: 119.0}})
    policy = _policy(rotation="none", max_concurrent=1)

    result = engine.run_backtest(cache, policy)

    assert result.policy_name == policy.name
    assert result.equity_curve            # one mark per day -> non-empty
    assert len(result.equity_curve) == 3
    expected_keys = {
        "total_return_pct", "cagr", "max_drawdown_pct", "win_rate",
        "avg_r", "profit_factor", "avg_holding_days", "num_trades",
    }
    assert expected_keys <= set(result.metrics)
    # Engine counters are merged into the metrics namespace too.
    assert "signals_skipped_no_cash" in result.metrics
    assert "rotations_triggered" in result.metrics
