"""
Acceptance for the SHORT side of the Automation Lab (the NDS mirror).
=====================================================================

Same layering as test_lab_rules.py, with every expected number hand-computable on a
round-figure short: sell at 100, target 80 (the 0.618 first-touch edge), stop 110.
  * Portfolio short mechanics — margin lock, mirrored P&L, mark-to-market, progress.
  * entry_filters — the confirming candle for a short is RED.
  * LabExits short mirror — early target below, stop that only falls, trail above the
    lowest close, gap fills, stop-before-target pessimism.
  * engine — short round-trip via the dynamic pass, per-side caps, and the
    percent_of_equity compounding sizer.
"""
import pandas as pd
import pytest

from pinescan.backtest.contracts import Trade, Position
from pinescan.backtest.portfolio import Portfolio
from pinescan.backtest.rules.registry import Policy
from pinescan.backtest.rules.selection.entry_filters import EntryFilters
from pinescan.backtest.rules.exit.lab_exits import LabExits
from pinescan.backtest.rules.sizing.percent_of_equity import PercentOfEquity
from pinescan.backtest import engine

D = [pd.Timestamp("2024-01-01") + pd.Timedelta(days=i) for i in range(10)]
NO_COSTS = {"brokerage_pct": 0.0, "slippage_pct": 0.0, "stt_pct": 0.0}


def _strade(**kw):
    """A synthetic SHORT: sell 100, cover-target 80, stop 110 (risk = 10/share)."""
    base = dict(symbol="SYN", swing="T1", entry_date=D[0], entry_price=100.0,
                target=80.0, sl=110.0, natural_exit_date=None, natural_outcome="open",
                side="short")
    base.update(kw)
    return Trade(**base)


def _pos(t):
    return Position(trade=t, notional=100_000.0, qty=1000.0, opened=t.entry_date,
                    fill_price=t.entry_price)


# ---------------------------------------------------------------------------
# portfolio — short cash identities
# ---------------------------------------------------------------------------
def test_short_round_trip_cash_and_pnl():
    pf = Portfolio(1_000_000.0)
    pf.open(_strade(), 100_000.0, 100.0, D[0])            # margin locked
    assert pf.cash == 900_000.0
    # Marked at 95: margin + (100-95) x 1000 unrealised = 105k of holdings value.
    assert pf.mark({"SYN": 95.0}, D[1]) == pytest.approx(1_005_000.0)
    assert pf.distance_to_target("SYN", 90.0) == pytest.approx(0.5)   # halfway 100->80
    ct = pf.close("SYN", 90.0, D[2], "tp")
    assert ct.pnl == pytest.approx(10_000.0)              # (100-90) x 1000, GROSS
    assert ct.r == pytest.approx(1.0)                     # risk = (110-100) x 1000
    assert ct.side == "short"
    assert pf.cash == pytest.approx(1_010_000.0)

def test_short_losing_close_books_negative():
    pf = Portfolio(1_000_000.0)
    pf.open(_strade(), 100_000.0, 100.0, D[0])
    ct = pf.close("SYN", 110.0, D[1], "sl")               # stopped at 110
    assert ct.pnl == pytest.approx(-10_000.0)
    assert pf.cash == pytest.approx(990_000.0)


# ---------------------------------------------------------------------------
# entry_filters — a short's confirming candle is RED
# ---------------------------------------------------------------------------
def test_confirming_candle_flips_for_shorts():
    rule = EntryFilters(green_only=True)
    assert rule.should_take(None, _strade(is_green=True)) is False    # green = against
    assert rule.should_take(None, _strade(is_green=False)) is True    # red = confirming
    assert rule.should_take(None, _strade(is_green=None)) is True     # no evidence


# ---------------------------------------------------------------------------
# lab_exits — the short mirror, hand-computed (early-70 level = 86)
# ---------------------------------------------------------------------------
def test_short_early_target_fills_at_level_and_gap_open():
    rule = LabExits(early_pct=70)
    p = _pos(_strade())
    assert rule.check(p, 98.0, 99.0, 87.0, 96.0, D[1]) is None        # low > 86 -> hold
    fill, reason = rule.check(p, 95.0, 96.0, 84.0, 88.0, D[2])        # touches 86
    assert (fill, reason) == (86.0, "early_tp")

    p2 = _pos(_strade())
    fill, reason = rule.check(p2, 84.0, 85.0, 82.0, 83.0, D[1])       # gaps OPEN below 86
    assert (fill, reason) == (84.0, "early_tp")                       # better fill kept


def test_short_breakeven_arms_on_prior_day_no_lookahead():
    # 1R = 10 -> arming needs a CLOSE <= 90. Same-day spike must not stop us out.
    rule = LabExits(be_arm_r=1.0)
    p = _pos(_strade())
    assert rule.check(p, 95.0, 101.0, 88.0, 89.0, D[1]) is None       # arms for tomorrow
    assert p.stop_now == 100.0
    fill, reason = rule.check(p, 97.0, 100.5, 96.0, 99.0, D[2])       # high touches 100
    assert (fill, reason) == (100.0, "breakeven")


def test_short_trailing_stop_follows_lowest_close():
    rule = LabExits(trail_pct=10)
    p = _pos(_strade())
    assert rule.check(p, 95.0, 96.0, 89.0, 90.0, D[1]) is None        # trough 90 -> stop 99
    assert p.stop_now == pytest.approx(99.0)
    fill, reason = rule.check(p, 97.0, 99.5, 96.0, 98.0, D[2])        # high 99.5 >= 99
    assert (fill, reason) == (pytest.approx(99.0), "trail_stop")


def test_short_trail_never_looser_than_v2_stop():
    rule = LabExits(trail_pct=10)
    p = _pos(_strade())
    # Trough close 105 -> raw trail 115.5 sits ABOVE V2's 110 stop: stays 110, and a
    # 111 high is V2's business (the natural pass), not the dynamic stop's.
    assert rule.check(p, 104.0, 106.0, 103.0, 105.0, D[1]) is None
    assert p.stop_now == 110.0
    assert rule.check(p, 108.0, 111.0, 107.0, 109.0, D[2]) is None


def test_short_stop_beats_target_on_double_touch_days():
    rule = LabExits(early_pct=70, trail_pct=10)
    p = _pos(_strade())
    assert rule.check(p, 95.0, 96.0, 89.0, 90.0, D[1]) is None        # stop now 99
    fill, reason = rule.check(p, 95.0, 99.2, 85.0, 92.0, D[2])        # touches 99 AND 86
    assert reason == "trail_stop" and fill == pytest.approx(99.0)


# ---------------------------------------------------------------------------
# engine — short round-trip, per-side caps, compounding sizer
# ---------------------------------------------------------------------------
def _policy(exit_rule="scanner_default", exit_params=None, **kw):
    base = dict(name="lab_short_test", description="", total_capital=1_000_000,
                max_concurrent=10, sizing="fixed_amount",
                sizing_params={"amount": 200_000}, selection="free_capital_first",
                rotation="none", rotation_params={}, exit=exit_rule,
                costs=NO_COSTS, exit_params=exit_params or {})
    base.update(kw)
    return Policy(**base)


def test_engine_short_early_tp_via_dynamic_pass():
    cache = {"SYN": pd.DataFrame({
        "Open":  [100.0, 98.0, 95.0, 93.0],
        "High":  [101.0, 99.0, 96.0, 94.0],
        "Low":   [ 99.0, 95.0, 84.0, 90.0],
        "Close": [100.0, 96.0, 88.0, 92.0],
    }, index=pd.DatetimeIndex(D[:4]))}
    res = engine.run_backtest(cache, _policy("lab_exits", {"early_pct": 70}),
                              trades=[_strade()])
    ct = res.closed[0]
    assert ct.outcome == "early_tp" and ct.exit_price == 86.0 and ct.exit_date == D[2]
    assert ct.pnl == pytest.approx((100.0 - 86.0) * (200_000 / 100.0))


def test_engine_per_side_caps_split_the_book():
    idx = pd.DatetimeIndex(D[:3])
    flat = pd.DataFrame({"Open": [100.0] * 3, "High": [100.0] * 3,
                         "Low": [100.0] * 3, "Close": [100.0] * 3}, index=idx)
    cache = {"S1": flat, "S2": flat.copy(), "L1": flat.copy()}
    trades = [_strade(symbol="S1"), _strade(symbol="S2"),
              Trade(symbol="L1", swing="T1", entry_date=D[0], entry_price=100.0,
                    target=120.0, sl=90.0, natural_outcome="open", side="long")]
    res = engine.run_backtest(cache, _policy(max_long=1, max_short=1), trades=trades)
    sides = sorted(ct.side for ct in res.closed)
    assert sides == ["long", "short"]                       # one each; S2 refused
    assert res.metrics["signals_skipped_side_cap"] == 1


def test_percent_of_equity_compounds():
    pf = Portfolio(1_000_000.0)
    rule = PercentOfEquity(pct=10)
    assert rule.position_size(pf, None) == pytest.approx(100_000.0)
    pf.open(_strade(), 100_000.0, 100.0, D[0])              # book unchanged at cost basis
    assert rule.position_size(pf, None) == pytest.approx(100_000.0)
    pf.close("SYN", 90.0, D[1], "tp")                       # +10k banked
    assert rule.position_size(pf, None) == pytest.approx(101_000.0)
