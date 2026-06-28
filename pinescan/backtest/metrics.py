"""
metrics.py — performance statistics from a finished backtest.
=============================================================

ROLE IN THE FLOW
  The simulator (engine.py) hands its results to exactly one place for scoring:
  this unit. It is the last computation before report.py renders a human table,
  so every number a reader sees about "how good was this policy" originates here.

      engine.run_backtest()  -->  (equity_curve, closed_trades, counters)
                                              |
                                              v
                                   metrics.summarize()  -->  dict  -->  report.py

CONSUMES (the hand-off shapes — see contracts.py / portfolio.py)
  equity_curve     list[(date, equity)], chronological — the portfolio's mark-to-market
                   value sampled per day. Drives return / CAGR / drawdown.
  closed_trades    list[ClosedTrade] — finished positions. Drives the trade-quality
                   stats (win rate, R, profit factor, holding time).
  starting_capital number — the policy's initial cash, the denominator for returns.
  counters         optional dict of plain ints the engine tallied while running
                   (e.g. signals it had to skip for lack of cash). Passed straight
                   through so report.py can show "what the rules did", not just outcomes.

EXPOSES
  summarize(equity_curve, closed_trades, starting_capital, counters=None) -> dict
  A flat dict of named metrics (see summarize's docstring for the full key list).

ROBUSTNESS CONTRACT
  Empty inputs never crash. A metric that is mathematically undefined on empty data
  (a mean/fraction of nothing, an annual rate over a zero-length span) returns None;
  counts return 0. This lets report.py print "N/A" instead of blowing up on a policy
  that took no trades.

HOW TO EXTEND
  * add a metric            -> compute it inside summarize() and add a key to the
                               `result` dict below (and document it in this header).
  * add a portfolio counter -> have the engine include it in the `counters` dict;
                               it lands in the output namespace automatically — no
                               change needed here.
"""
from __future__ import annotations

import math
from typing import Optional

import pandas as pd

# Calendar-day basis for annualizing a return. 365.25 averages in leap years so a
# ~1-year backtest annualizes to ~its raw return rather than drifting by the leap day.
_DAYS_PER_YEAR = 365.25


def summarize(equity_curve, closed_trades, starting_capital, counters=None) -> dict:
    """Reduce a finished backtest to a flat dict of performance metrics.

    Args:
        equity_curve: chronological list of (date, equity) points — the portfolio's
            value over time. `date` may be anything pd.Timestamp() accepts.
        closed_trades: list of ClosedTrade (see contracts.py). May be empty.
        starting_capital: the initial capital; denominator for return metrics.
        counters: optional dict of engine-tallied integers, merged verbatim into the
            result so report.py can surface them alongside the computed stats.

    Returns:
        dict with these keys (None where undefined on the given data):
            total_return_pct  (final/start - 1) * 100, from the equity curve.
            cagr              annualized total return over the curve's date span, %.
            max_drawdown_pct  worst peak-to-trough decline on the curve, % (>= 0).
            win_rate          fraction of closed trades with pnl > 0, in [0, 1].
            avg_r             mean R-multiple across closed trades.
            profit_factor     gross profit / gross loss (math.inf if no losing trades).
            avg_holding_days  mean (exit_date - entry_date) in days.
            num_trades        count of closed trades.
        ...plus every key from `counters`.
    """
    # --- equity-curve metrics (independent of whether any trade closed) ----------
    # Fall back to starting_capital when there's no curve, so "nothing happened" reads
    # as a 0% return rather than a crash.
    final_equity = equity_curve[-1][1] if equity_curve else starting_capital
    first_date = equity_curve[0][0] if equity_curve else None
    last_date = equity_curve[-1][0] if equity_curve else None

    if starting_capital and starting_capital > 0:
        total_return_pct = (final_equity / starting_capital - 1.0) * 100.0
    else:
        total_return_pct = None  # no meaningful denominator

    cagr = _cagr_pct(starting_capital, final_equity, first_date, last_date)
    max_drawdown_pct = _max_drawdown_pct(equity_curve)

    # --- trade-quality metrics ---------------------------------------------------
    num_trades = len(closed_trades)

    if num_trades:
        wins = sum(1 for t in closed_trades if t.pnl > 0)
        win_rate = wins / num_trades
    else:
        win_rate = None  # fraction of an empty set is undefined

    avg_r = _mean(t.r for t in closed_trades)
    avg_holding_days = _mean(
        (pd.Timestamp(t.exit_date) - pd.Timestamp(t.entry_date)).days
        for t in closed_trades
        if t.entry_date is not None and t.exit_date is not None
    )
    profit_factor = _profit_factor(closed_trades)

    # --- outcome breakdown + P&L detail ------------------------------------------
    # How each finished position ended (the user wants explicit target/stop counts).
    # ClosedTrade.outcome is "tp" | "sl" | "rotated" | "open_at_end" (see contracts.py).
    by_outcome = {}
    for t in closed_trades:
        by_outcome[t.outcome] = by_outcome.get(t.outcome, 0) + 1
    wins = [t.pnl for t in closed_trades if t.pnl > 0]
    losses = [t.pnl for t in closed_trades if t.pnl < 0]

    # Order is for human readability in report.py; dict order is preserved in 3.7+.
    result = {
        "total_return_pct": total_return_pct,
        "cagr": cagr,
        "max_drawdown_pct": max_drawdown_pct,
        "win_rate": win_rate,
        "avg_r": avg_r,
        "profit_factor": profit_factor,
        "avg_holding_days": avg_holding_days,
        "num_trades": num_trades,
        # outcome counts — how positions actually closed
        "n_target_hit": by_outcome.get("tp", 0),       # reached the 0.618 target
        "n_stop_hit": by_outcome.get("sl", 0),         # hit the 0.236 stop
        "n_rotated_out": by_outcome.get("rotated", 0), # sold early to fund another entry
        "n_open_at_end": by_outcome.get("open_at_end", 0),  # still open when the run ended
        # P&L detail (rupees)
        "total_pnl": sum(t.pnl for t in closed_trades),
        "gross_profit": sum(wins),
        "gross_loss": sum(losses),
        "avg_win": _mean(iter(wins)),
        "avg_loss": _mean(iter(losses)),
        "expectancy": _mean(t.pnl for t in closed_trades),   # avg P&L per trade
        "best_trade": max((t.pnl for t in closed_trades), default=None),
        "worst_trade": min((t.pnl for t in closed_trades), default=None),
    }

    # Pass-through: engine counters share the output namespace. Keys are expected to be
    # distinct from the metric keys above; if not, the counter would win (caller's call).
    if counters:
        result.update(counters)

    return result


def _mean(values) -> Optional[float]:
    """Mean of an iterable, skipping None entries. Returns None on an empty result
    (a mean of nothing is undefined, and None lets report.py print 'N/A')."""
    vals = [v for v in values if v is not None]
    return sum(vals) / len(vals) if vals else None


def _max_drawdown_pct(equity_curve) -> float:
    """Worst peak-to-trough decline on the equity curve, as a positive percentage.

    Walks the curve once tracking the running peak; the drawdown at each point is how
    far equity has fallen below the highest equity seen so far. Returns 0.0 for an empty
    curve or one that only ever rises (never dips below a prior peak).
    """
    peak = None
    max_dd = 0.0
    for _, equity in equity_curve:
        if peak is None or equity > peak:
            peak = equity
        # Guard the division: a non-positive peak can't yield a meaningful percentage.
        if peak and peak > 0:
            dd = (peak - equity) / peak
            if dd > max_dd:
                max_dd = dd
    return max_dd * 100.0


def _cagr_pct(starting_capital, final_equity, first_date, last_date) -> Optional[float]:
    """Compound annual growth rate over the curve's date span, as a percentage.

    Returns None when it can't be defined: no/zero-length span, a non-positive starting
    capital, or a non-positive final equity (a fractional root of a negative number is
    not real). Guarding here keeps summarize() crash-free on degenerate backtests.
    """
    if starting_capital is None or starting_capital <= 0:
        return None
    if final_equity is None or final_equity <= 0:
        return None
    if first_date is None or last_date is None:
        return None

    years = (pd.Timestamp(last_date) - pd.Timestamp(first_date)).days / _DAYS_PER_YEAR
    if years <= 0:
        return None  # single point, or all samples on the same day
    return ((final_equity / starting_capital) ** (1.0 / years) - 1.0) * 100.0


def _profit_factor(closed_trades) -> Optional[float]:
    """Gross profit divided by gross loss across closed trades.

    Returns None when there are no trades (nothing to divide), and math.inf when there
    are winning trades but no losing ones (the classic "no losses" case — an infinitely
    good ratio). An all-breakeven set (some trades, but no win and no loss) is also None.
    """
    if not closed_trades:
        return None
    gross_win = sum(t.pnl for t in closed_trades if t.pnl > 0)
    gross_loss = sum(t.pnl for t in closed_trades if t.pnl < 0)  # <= 0
    if gross_loss == 0:
        return math.inf if gross_win > 0 else None
    return gross_win / abs(gross_loss)
