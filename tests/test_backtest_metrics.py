"""
Acceptance test for U3 — metrics.summarize().

Guards the scoring unit that turns a finished backtest into the numbers report.py
shows. Uses hand-built equity curves with known returns/drawdowns and a tiny list of
ClosedTrade with known pnls, so each metric has a checkable expected value. The last
test pins the robustness contract: empty inputs must not crash.
"""
import math

import pandas as pd
import pytest

from pinescan.backtest.contracts import ClosedTrade
from pinescan.backtest.metrics import summarize

START = pd.Timestamp("2020-01-01")


def _ct(pnl, r, hold_days=10, outcome="tp"):
    """Build a ClosedTrade where only pnl / r / holding length matter to the metrics;
    prices are filled with plausible-but-irrelevant values."""
    return ClosedTrade(
        symbol="X", swing="T1",
        entry_date=START, exit_date=START + pd.Timedelta(days=hold_days),
        entry_price=100.0, exit_price=100.0 + pnl / 100.0,
        notional=10000.0, pnl=pnl, r=r, outcome=outcome,
    )


def test_total_return_and_cagr_over_one_year():
    # 100 -> 150 across ~365 days: +50% total, and ~50% annualized (span ≈ 1 year).
    curve = [(START, 100.0), (START + pd.Timedelta(days=365), 150.0)]
    res = summarize(curve, [], starting_capital=100.0)
    assert res["total_return_pct"] == pytest.approx(50.0, abs=0.01)
    assert res["cagr"] == pytest.approx(50.0, abs=1.0)   # loose: 365 vs 365.25-day year


def test_max_drawdown_from_a_dip():
    # 100 -> 150 -> 120 -> 160: peak 150, trough 120 => 20% drawdown.
    curve = [
        (START + pd.Timedelta(days=i), v)
        for i, v in enumerate([100.0, 150.0, 120.0, 160.0])
    ]
    res = summarize(curve, [], starting_capital=100.0)
    assert res["max_drawdown_pct"] == pytest.approx(20.0, abs=1e-6)


def test_trade_quality_stats():
    # pnls +100, +100, -50 => 2 of 3 wins; profit factor = 200 / 50 = 4.0.
    trades = [_ct(100, 2.0), _ct(100, 2.0), _ct(-50, -1.0)]
    res = summarize([], trades, starting_capital=100000.0)
    assert res["win_rate"] == pytest.approx(2 / 3, abs=1e-3)
    assert res["profit_factor"] == pytest.approx(4.0)
    assert res["avg_r"] == pytest.approx(1.0)            # mean(2, 2, -1)
    assert res["avg_holding_days"] == pytest.approx(10.0)
    assert res["num_trades"] == 3


def test_profit_factor_infinite_when_no_losses():
    res = summarize([], [_ct(100, 1.0), _ct(50, 1.0)], starting_capital=100000.0)
    assert res["profit_factor"] == math.inf
    assert res["win_rate"] == pytest.approx(1.0)


def test_counters_pass_through():
    counters = {"signals_skipped_no_cash": 5, "rotations_triggered": 2}
    res = summarize([], [], starting_capital=100000.0, counters=counters)
    assert res["signals_skipped_no_cash"] == 5
    assert res["rotations_triggered"] == 2


def test_empty_inputs_do_not_crash():
    res = summarize([], [], starting_capital=100000.0)            # counters defaulted
    assert res["num_trades"] == 0
    assert res["total_return_pct"] == pytest.approx(0.0)          # no curve => no change
    assert res["max_drawdown_pct"] == pytest.approx(0.0)
    # undefined-on-empty metrics report None rather than raising
    assert res["cagr"] is None
    assert res["win_rate"] is None
    assert res["avg_r"] is None
    assert res["profit_factor"] is None
    assert res["avg_holding_days"] is None
    # explicit counters=None is also fine
    assert summarize([], [], 100000.0, counters=None)["num_trades"] == 0
