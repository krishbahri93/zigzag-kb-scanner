"""
Acceptance test for U2 — the portfolio account (cash / positions / equity curve).

Drives one position through its whole lifecycle (open -> mark -> close) and checks the
two invariants the rest of the backtester leans on: cash stays consistent with every
trade, and the derived numbers the rules/metrics read back out (qty, equity,
distance-to-target, gross pnl, R-multiple) are the exact arithmetic expected.
"""
import pandas as pd
import pytest

from pinescan.backtest.contracts import Trade
from pinescan.backtest.portfolio import Portfolio


def _trade():
    # entry 100, target 120, sl 95 -> 20 rupees of upside, 5 of entry-to-SL risk.
    return Trade(
        symbol="ACME",
        swing="T1",
        entry_date=pd.Timestamp("2024-01-01"),
        entry_price=100.0,
        target=120.0,
        sl=95.0,
    )


def test_portfolio_lifecycle_open_mark_close():
    p = Portfolio(starting_cash=1_000_000)
    start_cash = p.cash

    # open: notional 200000 at price 100 -> cash drops by the notional, qty = 2000.
    pos = p.open(_trade(), notional=200_000, price=100.0,
                 date=pd.Timestamp("2024-01-02"))
    assert start_cash - p.cash == 200_000
    assert pos.qty == 2000
    assert p.positions["ACME"] is pos

    # mark: at price 110 -> equity = cash + held shares valued at 110.
    equity = p.mark({"ACME": 110.0}, pd.Timestamp("2024-01-03"))
    assert equity == p.cash + 2000 * 110.0
    assert p.equity_curve[-1] == (pd.Timestamp("2024-01-03"), equity)

    # distance_to_target at 110 is halfway from entry 100 to target 120.
    assert p.distance_to_target("ACME", 110.0) == pytest.approx(0.5)

    # close: at target 120 -> cash rises by proceeds, gross pnl > 0, outcome 'tp'.
    cash_pre_close = p.cash
    ct = p.close("ACME", price=120.0, date=pd.Timestamp("2024-01-10"), outcome="tp")
    assert p.cash == cash_pre_close + 2000 * 120.0
    assert p.cash > cash_pre_close
    assert ct.pnl > 0 and ct.pnl == pytest.approx(40_000)   # 240000 - 200000, gross
    assert ct.outcome == "tp"

    # R-multiple = gross pnl / entry-to-SL risk = 40000 / (200000 - 2000*95) = 4.0.
    assert ct.r == pytest.approx(40_000 / (200_000 - 2000 * 95.0))

    # position is gone and exactly one ClosedTrade was booked.
    assert "ACME" not in p.positions
    assert p.closed == [ct]


def test_mark_falls_back_to_entry_when_price_missing():
    # robustness: a symbol absent from the price map is marked at its entry_price.
    p = Portfolio(starting_cash=1_000_000)
    p.open(_trade(), notional=200_000, price=100.0, date=pd.Timestamp("2024-01-02"))
    equity = p.mark({}, pd.Timestamp("2024-01-03"))         # no quote for ACME today
    assert equity == p.cash + 2000 * 100.0                  # fell back to entry 100


def test_can_afford_tracks_cash():
    p = Portfolio(starting_cash=200_000)
    assert p.can_afford(200_000) and not p.can_afford(200_001)
    p.open(_trade(), notional=200_000, price=100.0, date=pd.Timestamp("2024-01-02"))
    assert not p.can_afford(1)                              # fully deployed
