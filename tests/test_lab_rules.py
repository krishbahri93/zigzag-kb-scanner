"""
Acceptance for the Automation Lab rules (entry_filters + lab_exits) and the engine's
dynamic-exit pass / entry-fill variants.
=====================================================================================

Three layers, mirroring how the pieces stack in production:
  * entry_filters.should_take() on synthetic Trades — each veto in isolation, plus the
    "missing evidence passes" contract (filters may only act on evidence that exists).
  * LabExits.check() on hand-computed bar sequences — early target, breakeven, trailing
    stop, gap fills, and the stop-before-target pessimism rule. Every expected fill is
    computable by hand from the docstring in rules/exit/lab_exits.py.
  * engine.run_backtest() on a tiny synthetic cache — proves the dynamic-exit pass is
    actually wired into the daily loop, that window_end truncates a run, and that
    entry_fill="next_open" defers the fill to the recorded next bar.

Everything here is pure-synthetic (no data cache needed), like test_backtest_rules.py.
"""
import pandas as pd
import pytest

from pinescan.backtest.contracts import Trade, Position
from pinescan.backtest.rules.registry import Policy
from pinescan.backtest.rules.selection.entry_filters import EntryFilters
from pinescan.backtest.rules.exit.lab_exits import LabExits
from pinescan.backtest import engine

D = [pd.Timestamp("2024-01-01") + pd.Timedelta(days=i) for i in range(10)]
NO_COSTS = {"brokerage_pct": 0.0, "slippage_pct": 0.0, "stt_pct": 0.0}


def _trade(**kw):
    """A synthetic Trade around round numbers: entry 100, target 120, stop 90."""
    base = dict(symbol="SYN", swing="T1", entry_date=D[0], entry_price=100.0,
                target=120.0, sl=90.0, natural_exit_date=None, natural_outcome="open")
    base.update(kw)
    return Trade(**base)


def _pos(t):
    """An open Position on `t` sized 1 share per rupee — qty is irrelevant to exits."""
    return Position(trade=t, notional=100_000.0, qty=1000.0, opened=t.entry_date,
                    fill_price=t.entry_price)


# ---------------------------------------------------------------------------
# entry_filters — each veto in isolation
# ---------------------------------------------------------------------------
def test_filters_all_off_takes_everything():
    assert EntryFilters().should_take(None, _trade()) is True


def test_candle_pos_veto_and_pass():
    rule = EntryFilters(min_candle_pos=0.6)
    assert rule.should_take(None, _trade(candle_pos=0.55)) is False   # weak close
    assert rule.should_take(None, _trade(candle_pos=0.80)) is True    # near the high
    assert rule.should_take(None, _trade(candle_pos=None)) is True    # no evidence -> pass


def test_green_only_veto():
    rule = EntryFilters(green_only=True)
    assert rule.should_take(None, _trade(is_green=False)) is False
    assert rule.should_take(None, _trade(is_green=True)) is True
    assert rule.should_take(None, _trade(is_green=None)) is True      # no evidence -> pass


def test_rel_vol_modes():
    gt_prev = EntryFilters(rel_vol="gt_prev")
    assert gt_prev.should_take(None, _trade(sig_volume=90.0, vol_prev=100.0)) is False
    assert gt_prev.should_take(None, _trade(sig_volume=110.0, vol_prev=100.0)) is True

    gt_avg = EntryFilters(rel_vol="gt_1_2x20d")
    assert gt_avg.should_take(None, _trade(sig_volume=110.0, vol_avg20=100.0)) is False  # < 1.2x
    assert gt_avg.should_take(None, _trade(sig_volume=130.0, vol_avg20=100.0)) is True


def test_min_rr_veto_and_none_is_unpassable():
    rule = EntryFilters(min_rr=1.0)
    assert rule.should_take(None, _trade(rr_remaining=0.5)) is False
    assert rule.should_take(None, _trade(rr_remaining=2.0)) is True
    # rr_remaining None means risk <= 0 (close at/under the stop) — never take that.
    assert rule.should_take(None, _trade(rr_remaining=None)) is False


# ---------------------------------------------------------------------------
# lab_exits — hand-computed bar sequences (entry 100, target 120, stop 90)
# ---------------------------------------------------------------------------
def test_early_target_fills_at_level_and_at_gap_open():
    # early 70% of the 100->120 run = 114.
    rule = LabExits(early_pct=70)
    p = _pos(_trade())
    assert rule.check(p, 104.0, 110.0, 103.0, 108.0, D[1]) is None       # high < 114 -> hold
    fill, reason = rule.check(p, 108.0, 115.0, 107.0, 112.0, D[2])       # touches 114
    assert (fill, reason) == (114.0, "early_tp")

    p2 = _pos(_trade())
    fill, reason = rule.check(p2, 116.0, 118.0, 115.0, 117.0, D[1])      # gaps OPEN above 114
    assert (fill, reason) == (116.0, "early_tp")                         # better fill kept


def test_breakeven_arms_on_prior_day_and_stops_at_entry():
    # 1R = 10 -> arming needs a CLOSE >= 110. The stop acts only on PRIOR-day state.
    rule = LabExits(be_arm_r=1.0)
    p = _pos(_trade())
    # Day 1: close 111 arms breakeven for tomorrow — but today's low 99 must NOT stop
    # us out (state updates after the day's checks; no lookahead).
    assert rule.check(p, 105.0, 112.0, 99.0, 111.0, D[1]) is None
    assert p.stop_now == 100.0                                           # armed at entry
    # Day 2: low touches 100 -> out at breakeven.
    fill, reason = rule.check(p, 103.0, 104.0, 99.5, 101.0, D[2])
    assert (fill, reason) == (100.0, "breakeven")


def test_trailing_stop_follows_peak_close():
    rule = LabExits(trail_pct=10)
    p = _pos(_trade())
    assert rule.check(p, 100.0, 111.0, 100.0, 110.0, D[1]) is None       # peak 110 -> stop 99
    assert p.stop_now == 99.0
    fill, reason = rule.check(p, 100.0, 101.0, 98.5, 99.5, D[2])         # low 98.5 <= 99
    assert (fill, reason) == (99.0, "trail_stop")


def test_trailing_stop_never_sits_below_v2_stop_and_only_rises():
    rule = LabExits(trail_pct=10)
    p = _pos(_trade())
    # Peak close 95 -> raw trail 85.5 sits BELOW V2's stop (90): dynamic stop stays 90,
    # and a low of 89 is V2's business (natural pass), not the dynamic stop's.
    assert rule.check(p, 95.0, 96.0, 94.0, 95.0, D[1]) is None
    assert p.stop_now == 90.0
    assert rule.check(p, 91.0, 92.0, 89.0, 91.0, D[2]) is None           # not ours to fire


def test_stop_checked_before_early_target_on_double_touch_days():
    # Both the trail stop AND the early level touched in one day -> pessimistic: stop.
    rule = LabExits(early_pct=70, trail_pct=10)
    p = _pos(_trade())
    assert rule.check(p, 100.0, 113.0, 100.0, 112.0, D[1]) is None       # peak 112 -> stop 100.8
    fill, reason = rule.check(p, 105.0, 115.0, 100.0, 101.0, D[2])       # touches both
    assert reason == "trail_stop" and fill == p.stop_now


# ---------------------------------------------------------------------------
# engine wiring — dynamic pass, window_end, entry_fill="next_open"
# ---------------------------------------------------------------------------
def _cache():
    """One symbol, five bars. High touches 115 on D3 (early-70 level is 114) while the
    V2 natural outcome stays 'open' — only the dynamic pass can close this trade."""
    return {"SYN": pd.DataFrame({
        "Open":  [100.0, 101.0, 104.0, 108.0, 112.0],
        "High":  [101.0, 106.0, 110.0, 115.0, 113.0],
        "Low":   [ 99.0, 100.0, 103.0, 107.0, 110.0],
        "Close": [100.0, 105.0, 108.0, 112.0, 111.0],
    }, index=pd.DatetimeIndex(D[:5]))}


def _policy(exit_rule="scanner_default", exit_params=None):
    return Policy(name="lab_test", description="", total_capital=1_000_000,
                  max_concurrent=10, sizing="fixed_amount",
                  sizing_params={"amount": 200_000}, selection="free_capital_first",
                  rotation="none", rotation_params={}, exit=exit_rule,
                  costs=NO_COSTS, exit_params=exit_params or {})


def test_engine_runs_dynamic_exit_pass():
    t = _trade(next_open=101.0, next_date=D[1])
    res = engine.run_backtest(_cache(), _policy("lab_exits", {"early_pct": 70}),
                              trades=[t])
    assert len(res.closed) == 1
    ct = res.closed[0]
    assert ct.outcome == "early_tp" and ct.exit_price == 114.0 and ct.exit_date == D[3]
    # Same run under the static default exit: nothing fires, closed at data end.
    res0 = engine.run_backtest(_cache(), _policy(), trades=[_trade()])
    assert res0.closed[0].outcome == "open_at_end"


def test_window_end_truncates_the_run():
    res = engine.run_backtest(_cache(), _policy("lab_exits", {"early_pct": 70}),
                              trades=[_trade()], window_end=D[2])
    ct = res.closed[0]
    # Early level (114) is never touched by D2 -> forced close at the window's last bar.
    assert ct.outcome == "open_at_end" and ct.exit_date == D[2] and ct.exit_price == 108.0
    assert res.equity_curve[-1][0] == D[2]                    # curve stops at the window


def test_entry_fill_next_open_defers_to_recorded_next_bar():
    t = _trade(next_open=101.0, next_date=D[1])
    res = engine.run_backtest(_cache(), _policy(), trades=[t])                  # close fill
    resn = engine.run_backtest(_cache(), _policy(), trades=[t], entry_fill="next_open")
    # ClosedTrade books the ACTUAL fill (pos.notional/pos.qty) — approx: float round-trip
    assert res.closed[0].entry_price == pytest.approx(100.0)
    assert resn.closed[0].entry_price == pytest.approx(101.0)  # the recorded next open
    assert resn.closed[0].entry_date == D[1]                   # booked at the fill day
    # A signal on the data's last bar has no next bar -> dropped, takes no trade.
    orphan = _trade(entry_date=D[4], next_open=None, next_date=None)
    resd = engine.run_backtest(_cache(), _policy(), trades=[orphan], entry_fill="next_open")
    assert len(resd.closed) == 0
