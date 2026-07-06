"""
engine.py — the day-by-day portfolio simulator that ties every unit together.
=============================================================================

ROLE IN THE FLOW (see backtest/__init__.py for the whole picture)
  This is the INTEGRATION unit. Every other backtester unit produces something this
  one consumes, and nothing else orchestrates them:

      events.trades_for(df) -> [Trade]   the fixed V2 signals, per symbol
      registry.build_rules(policy)       the money-management rule instances
      Portfolio(total_capital)           the account whose cash/positions we drive
      CostModel.from_policy(costs)        the friction subtracted on every fill
      metrics.summarize(...)              scores the finished run

  run_backtest() walks a single merged daily timeline and, on each day, calls those
  pieces in a FIXED order (exits, then entries, then mark-to-market). It owns no
  trading logic of its own beyond that ordering — WHICH signal to take and WHAT to
  sell when full are decisions delegated to the rules; WHAT a trade's TP/SL are is
  decided by V2 (frozen on the Trade). The engine only sequences them and keeps the
  Portfolio's books.

HOW A BACKTEST DAY WORKS (the loop in run_backtest)
  (a) EXITS first   — close any open position whose V2-natural TP/SL date has arrived,
                      filling at that swing's target (tp) or stop (otherwise).
  (b) ENTRIES next  — for every V2 entry that fired today: let the SELECTION rule veto
                      it; ask the SIZING rule for a notional; if there's free cash AND
                      a free slot, open it; otherwise ask the ROTATION rule to sell an
                      open position to make room, and open only if that freed a slot.
                      A signal that still doesn't fit is tallied as skipped.
  (c) MARK last     — record end-of-day equity (cash + held positions) onto the curve.
  After the final day, any still-open position is closed at its last known price with
  outcome "open_at_end" so the equity curve and trade list are complete.

  Doing exits before entries means capital a position frees by hitting TP today is
  available to a signal firing the SAME day — the natural first-come ordering.

COST CONVENTION (kept in lockstep with portfolio.py, which is GROSS)
  portfolio.open/close move cash and book pnl with NO costs. The engine layers them on:
    * at OPEN  — subtract entry_cost from cash (the buy-side friction).
    * at CLOSE — subtract exit_cost from cash AND subtract the full round_trip
                 (entry + exit) from the booked ClosedTrade.pnl.
  So cash absorbs entry friction at the buy and exit friction at the sell (= round_trip
  over the life of the trade), while pnl — booked only once, at close — absorbs the
  whole round_trip there. Cash and realised pnl therefore stay consistent. The two
  helpers below (_open_priced / _close_priced) are the ONLY places this netting lives,
  so all four close sites (TP/SL, rotation, end-of-data) apply it identically.

HOW TO EXTEND
  * change the daily decision ORDER (e.g. an extra exit pass) -> edit run_backtest's
    per-day body; keep exits-before-entries unless you mean to change that semantics.
  * apply costs differently (e.g. cost the rotation sell at its own price) -> change
    _close_priced; every close site inherits it.
  * add a per-run output (e.g. a daily positions log) -> add a field to Result and
    populate it in the loop; metrics/report read Result, not the Portfolio.
  * the SIGNALS and the RULES are deliberately NOT tunable here — change events.py or
    add a rule in rules/ instead, so the engine stays a pure sequencer.
"""
from collections import defaultdict
from dataclasses import dataclass
from typing import List

import pandas as pd

from . import events
from . import metrics
from .costs import CostModel
from .portfolio import Portfolio
from .rules.registry import build_rules


@dataclass
class Result:
    """Everything a finished run hands to report.py — the simulator's whole output.

    Produced once by run_backtest(); `metrics` is filled by metrics.summarize() so the
    scoring lives in one place (this is just the carrier). report.py reads these fields
    to render the table and the English rule-tree.
    """
    policy_name: str                 # which policy produced this run (Policy.name)
    equity_curve: list               # [(date, equity)] — Portfolio.equity_curve
    closed: list                     # [ClosedTrade] — every exit, in close order
    counters: dict                   # engine tallies (skips, rotations) for the report
    metrics: dict                    # metrics.summarize() output (scored stats)


def _price_on(close_series, date):
    """Today's close for one symbol, or None if that symbol didn't print a bar today.

    `close_series` is a symbol's Close column indexed by date. A missing date (data
    gap, holiday, listing/delisting edge) returns None so the caller can simply skip
    this symbol for the day rather than crash the whole run.
    """
    if close_series is None or date not in close_series.index:
        return None
    return float(close_series.loc[date])


def _open_priced(pf, costs, trade, notional, price, date):
    """Open `trade` in the portfolio and pay the buy-side friction.

    Delegates the cash/position bookkeeping to pf.open() (which is GROSS), then
    subtracts entry_cost from cash — the only buy-side cost (STT is sell-side; see
    costs.py). Centralised so the two open sites (direct open and post-rotation open)
    cost a fill identically.
    """
    pf.open(trade, notional, price, date)
    pf.cash -= costs.entry_cost(notional)


def _close_priced(pf, costs, symbol, price, date, outcome):
    """Close `symbol` at `price` with `outcome`, then net the costs, and return the
    ClosedTrade.

    pf.close() returns a GROSS ClosedTrade (proceeds back to cash, pnl = proceeds -
    notional). We then: subtract exit_cost from cash (the sell-side friction), and
    subtract the full round_trip (buy + sell) from the booked pnl so the recorded
    profit is net of the trade's entire life. This is the single netting point shared
    by all close reasons — TP/SL, rotation, and end-of-data — see the module header's
    COST CONVENTION.
    """
    ct = pf.close(symbol, price, date, outcome)
    pf.cash -= costs.exit_cost(ct.notional)
    ct.pnl -= costs.round_trip(ct.notional)
    return ct


def run_backtest(cache, policy, window_start=None, trades=None,
                 window_end=None, entry_fill="close") -> Result:
    """Replay one policy over a cache of daily bars and return its scored Result.

    window_start (optional pd.Timestamp/date): confine TRADING to dates >= this, while
    still detecting setups on the FULL history. This is how a short timeframe (e.g. the
    last 6 weeks) stays meaningful — the engine keeps the warmup it needs to find setups,
    but only entries from window_start onward are taken and the equity curve starts there.
    None = trade the whole history.

    window_end (optional, Automation Lab): stop TRADING after this date — the
    train/validate walk-forward split. Entries and bars beyond it are ignored;
    whatever is still open is closed at the window's last bar ("open_at_end").

    entry_fill ("close" | "next_open", Automation Lab): "close" fills at the signal
    bar's close (Krish's 3:20 PM behaviour — the default and historical assumption);
    "next_open" defers each entry to the NEXT bar's open (buy after confirmation),
    using the fill the Trade captured at detection time.

    Args:
        cache:  {symbol -> daily OHLCV DataFrame}. Each df must carry a "Close" column
                indexed by date; its index also contributes to the shared timeline.
                events.trades_for(symbol, df) is called once per symbol to get its
                fixed V2 Trades (this is the ONLY engine/signal touch-point).
        policy: a loaded registry.Policy — supplies starting capital, the per-trade
                size, the concurrent-position cap, the cost rates, and the names of the
                sizing/selection/rotation/exit rules to run.

    Returns:
        Result(policy_name, equity_curve, closed, counters, metrics). `counters` holds
        "signals_skipped_no_cash" and "rotations_triggered"; `metrics` is the
        metrics.summarize() scoring of the equity curve + closed trades.

    The loop is the day-by-day procedure documented in the module header: exits, then
    entries (selection -> sizing -> open-or-rotate), then mark, with leftovers closed
    at the end.
    """
    # --- wire up the run from the policy -------------------------------------------
    rules = build_rules(policy)               # {sizing, selection, rotation, exit}
    costs = CostModel.from_policy(policy.costs)
    pf = Portfolio(policy.total_capital)

    # --- gather every symbol's fixed V2 trades + its Close column ------------------
    # all_trades is the union of per-symbol Trade lists (one engine call each, read
    # only); close_series lets us look up any symbol's price on any date in O(1).
    # `trades` lets a caller precompute the V2 signals ONCE and reuse them across many
    # runs (they don't depend on the policy or window) — a big speedup for sweeps. When
    # None, detect them here. Either way we still build close_series from the cache.
    all_trades: List = list(trades) if trades is not None else []
    close_series = {}
    open_series = {}
    high_series = {}
    low_series = {}
    for sym, df in cache.items():
        if trades is None:
            all_trades += events.trades_for(sym, df)
        close_series[sym] = df["Close"]       # indexed by df.index (dates)
        # dynamic exits (Automation Lab) need the day's full bar; fall back to Close
        # for caches that only carry closes (behaviour then degrades gracefully)
        open_series[sym] = df["Open"] if "Open" in df.columns else df["Close"]
        high_series[sym] = df["High"] if "High" in df.columns else df["Close"]
        low_series[sym] = df["Low"] if "Low" in df.columns else df["Close"]

    # Entry-fill variant: each Trade knows both its fill styles (captured at detection).
    # "next_open" trades fire on their NEXT bar at its open; ones with no next bar drop.
    def _fire_date(t):
        return t.next_date if entry_fill == "next_open" else t.entry_date

    def _fire_price(t):
        return t.next_open if entry_fill == "next_open" else t.entry_price

    if entry_fill == "next_open":
        all_trades = [t for t in all_trades if t.next_date is not None and t.next_open is not None]

    # Window: setups were detected on FULL history above; here we keep only entries that
    # FIRE (at their fill date) inside [window_start, window_end]. None = unbounded.
    if window_start is not None:
        window_start = pd.Timestamp(window_start)
        all_trades = [t for t in all_trades if _fire_date(t) >= window_start]
    if window_end is not None:
        window_end = pd.Timestamp(window_end)
        all_trades = [t for t in all_trades if _fire_date(t) <= window_end]

    # Index the trades by the day they fire, so each loop day pulls its entries in O(1).
    # A defaultdict keeps insertion order within a day (stable -> deterministic runs).
    entries_by_date = defaultdict(list)
    for t in all_trades:
        entries_by_date[_fire_date(t)].append(t)

    # Engine tallies the report surfaces: how often a signal couldn't be funded, and how
    # often rotation freed a slot. metrics.summarize() passes these straight through.
    counters = {"signals_skipped_no_cash": 0, "rotations_triggered": 0}

    # The shared daily timeline = the union of every symbol's bar dates, sorted & unique.
    # pd.Index.union does exactly that (sorted, de-duplicated) across all frames.
    timeline = pd.DatetimeIndex([])
    for df in cache.values():
        timeline = timeline.union(df.index)
    dates = list(timeline)
    if window_start is not None:
        dates = [d for d in dates if d >= window_start]
    if window_end is not None:
        dates = [d for d in dates if d <= window_end]
    if not dates:                              # window contains no bars -> empty run
        return Result(policy.name, [], [], counters,
                      metrics.summarize([], [], policy.total_capital, counters))

    for d in dates:
        # (a) EXITS — close positions whose V2 natural TP/SL date has arrived.
        # list(...) snapshots the items so closing inside the loop can't mutate-during-
        # iterate. We fill at the swing's target on a "tp", else its stop, and book the
        # exit at the TRUE natural_exit_date (not d) so trade dates match V2 exactly.
        for sym, pos in list(pf.positions.items()):
            t = pos.trade
            if t.natural_exit_date is not None and d >= t.natural_exit_date:
                fill = t.target if t.natural_outcome == "tp" else t.sl
                _close_priced(pf, costs, sym, fill, t.natural_exit_date, t.natural_outcome)

        # (a2) DYNAMIC EXITS (Automation Lab) — the policy's exit rule sees today's bar
        # for every position that survived the natural pass, and may close it (early
        # target / breakeven / trailing stop). V2's own TP/SL always had first claim.
        exit_rule = rules["exit"]
        if getattr(exit_rule, "is_dynamic", False):
            for sym, pos in list(pf.positions.items()):
                bar_c = _price_on(close_series.get(sym), d)
                if bar_c is None:
                    continue                               # no bar today -> nothing to judge
                res = exit_rule.check(
                    pos,
                    _price_on(open_series.get(sym), d),
                    _price_on(high_series.get(sym), d),
                    _price_on(low_series.get(sym), d),
                    bar_c, d)
                if res is not None:
                    fill, reason = res
                    _close_priced(pf, costs, sym, fill, d, reason)

        # (b) ENTRIES — every V2 entry that fired today, in firing order.
        for t in entries_by_date.get(d, []):
            if t.symbol in pf.positions:
                continue                                   # one position per symbol
            if not rules["selection"].should_take(pf, t):
                continue                                   # policy vetoed this signal
            size = rules["sizing"].position_size(pf, t)
            price = _fire_price(t)                         # the trade's own recorded fill
            if price is None:
                continue                                   # no fill available

            has_room = pf.can_afford(size) and len(pf.positions) < policy.max_concurrent
            if has_room:
                _open_priced(pf, costs, t, size, price, d)
                pf.positions[t.symbol].fill_price = price  # dynamic-exit anchor
            else:
                # Full or short on cash -> ask the rotation rule to free a slot. Hand it
                # today's price for each open position so it can score distance-to-target.
                prices_now = {
                    s: _price_on(close_series.get(s), d)
                    for s in pf.positions
                    if _price_on(close_series.get(s), d) is not None
                }
                freed = rules["rotation"].free_capital(pf, size, prices_now, d)
                for s in freed:
                    _close_priced(pf, costs, s, prices_now[s], d, "rotated")
                    counters["rotations_triggered"] += 1
                # Re-test capacity now that rotation may have freed cash AND a slot.
                if pf.can_afford(size) and len(pf.positions) < policy.max_concurrent:
                    _open_priced(pf, costs, t, size, price, d)
                    pf.positions[t.symbol].fill_price = price   # dynamic-exit anchor
                else:
                    counters["signals_skipped_no_cash"] += 1

        # (c) MARK — snapshot end-of-day equity. Skip symbols with no bar today; the
        # Portfolio falls back to entry price for any holding we omit (see mark()).
        marks = {
            s: _price_on(close_series.get(s), d)
            for s in pf.positions
            if _price_on(close_series.get(s), d) is not None
        }
        pf.mark(marks, d)

    # Close any position still open at the end of the data at its last known close, so
    # the equity curve and trade ledger are complete. outcome "open_at_end" tells
    # metrics/report this exit was forced by the data ending, not by a V2 signal.
    for sym, pos in list(pf.positions.items()):
        s = close_series[sym]
        inside = s[s.index <= dates[-1]]       # window_end-safe: never price beyond the window
        last = float(inside.iloc[-1]) if len(inside) else float(s.iloc[-1])
        _close_priced(pf, costs, sym, last, dates[-1], "open_at_end")

    return Result(
        policy_name=policy.name,
        equity_curve=pf.equity_curve,
        closed=pf.closed,
        counters=counters,
        metrics=metrics.summarize(
            pf.equity_curve, pf.closed, policy.total_capital, counters
        ),
    )
