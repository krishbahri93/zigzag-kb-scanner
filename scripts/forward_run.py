"""
forward_run.py — advance the paper (forward) test by one day, per market.
=========================================================================

Forward testing = run the validated backtester from a FROZEN start date on a cache that grows by
one bar each day. The V2 engine is fully causal (no lookahead past the last bar), so a backtest
over data[FORWARD_START : today] IS a faithful, no-lookahead forward test — we reuse
engine.run_backtest verbatim, so forward and back are the SAME code. There is NO separate live-exit
logic and NO persistent portfolio: each run is a pure, idempotent function of the cache.

WHAT ONE RUN DOES (per market, all 5 strategies = 5 paper accounts)
  1. Refresh today's final daily bar into the cache (us.backfill / india.refresh_recent).
  2. Detect V2 signals ONCE across the (sorted, frozen) universe — reused for all 5 policies.
  3. Per policy: engine.run_backtest(window_start=FORWARD_START). The engine force-closes still-open
     positions as outcome "open_at_end" (marked to last close), so the OPEN BOOK is just those
     closed rows; REALIZED stats come from re-summarizing the non-open_at_end trades (reusing
     metrics.summarize — no new stats code).
  4. Fetch the benchmark (SPY/QQQ or Nifty/Sensex) over [FORWARD_START, today].
  5. Render reports/forward/{market}.md and update data/forward/{market}/state.json.

STATE (the ONLY thing persisted — everything else recomputes from the cache)
  data/forward/{market}/state.json = {forward_start, last_run_date}. forward_start is set from
  --start on the FIRST run, then LOCKED, so each account's history is stable. Re-running on the same
  data is safe and produces identical output (the engine is deterministic).

USAGE
  python scripts/forward_run.py --market us                 # daily run (warm ~6mo on first init)
  python scripts/forward_run.py --market us --start today   # pure forward (first init only)
  python scripts/forward_run.py --market us --start 2026-01-15
  python scripts/forward_run.py --market us --no-refresh    # use the cache as-is (no network)

HOW TO EXTEND
  * change what the dashboard shows -> _write_dashboard (it reads only the Result + benchmark).
  * the per-market data/benchmark/currency wiring lives in pinescan.study, shared with the backtest
    matrix — change a market there, both studies pick it up.
"""
import os
import sys
import json
import glob
import argparse
import datetime as dt

import pandas as pd

# Windows consoles default to cp1252; force UTF-8 so the Rs / $ glyphs print.
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

from pinescan.backtest.rules.registry import load_policy
from pinescan.backtest import engine, events, metrics
from pinescan import study
from pinescan.markets import india, us

FORWARD_DIR = "data/forward"        # per-market state lives here (git-ignored under data/)
REPORT_DIR = "reports/forward"      # rendered dashboards
WARM_MONTHS = 6                     # how far back "warm" start seeds the account


def _refresh(market):
    """Pull today's FINAL daily bar into the cache. US: us.backfill is per-DATE and resumable, so
    days=5 just adds any missing recent dates incl. today. India: backfill SKIPS cached symbols, so
    it never appends today's bar — use india.refresh_recent to re-fetch + merge each symbol."""
    if market == "us":
        us.ensure_api_key()
        syms, _ = us.select_liquid_universe()
        us.backfill(syms, days=5)
    else:
        india.ensure_dhan_creds()
        syms = [os.path.splitext(os.path.basename(f))[0]
                for f in glob.glob(f"{india.CACHE_DIR}/*.parquet")]
        india.refresh_recent(syms, days=15)


def _state_path(market):
    return os.path.join(FORWARD_DIR, market, "state.json")


def _load_state(market):
    p = _state_path(market)
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else None


def _save_state(market, state):
    os.makedirs(os.path.dirname(_state_path(market)), exist_ok=True)
    json.dump(state, open(_state_path(market), "w", encoding="utf-8"), indent=2)


def _resolve_start(start_arg, last):
    """Turn --start into a concrete (tz-aware) FORWARD_START — first init only. 'warm' seeds
    ~WARM_MONTHS back so the dashboard shows history immediately; 'today' starts empty; a
    YYYY-MM-DD string is localized to the cache's timezone so it compares with the bar index."""
    last_ts = pd.Timestamp(last)
    if start_arg in (None, "warm"):
        return last_ts - pd.DateOffset(months=WARM_MONTHS)
    if start_arg == "today":
        return last_ts
    ws = pd.Timestamp(start_arg)
    if last_ts.tz is not None and ws.tz is None:
        ws = ws.tz_localize(last_ts.tz)
    return ws


def _px(v, sym):
    """Per-share price with 2 decimals (study.money rounds to whole units — too coarse for a quote)."""
    return "N/A" if v is None else f"{sym}{v:,.2f}"


def _write_dashboard(market, mkt, ws, last, accounts, bench):
    """Render reports/forward/{market}.md from the 5 Results + benchmark. Open positions are the
    'open_at_end' closed rows (marked to last close); realized stats were summarized on the rest."""
    cur = mkt.money_sym
    L = [f"# Forward test — {mkt.title}",
         "",
         f"_Paper trading since **{pd.Timestamp(ws).date()}** · data through "
         f"{pd.Timestamp(last).date()} · starting capital {mkt.capital_label} per account · all 5 "
         f"strategies on the same V2 signals._",
         "",
         "## Standings",
         "| Strategy | Equity | Return | Realized win% | PF | Open | Closed |",
         "|---|---|---|---|---|---|---|"]
    for strat, policy, result in accounts:
        m = result.metrics
        eq = result.equity_curve[-1][1] if result.equity_curve else policy.total_capital
        opens = [c for c in result.closed if c.outcome == "open_at_end"]
        realized = [c for c in result.closed if c.outcome != "open_at_end"]
        rstats = metrics.summarize(result.equity_curve, realized, policy.total_capital, result.counters)
        wr = rstats["win_rate"]
        L.append(f"| {strat} | {study.money(eq, cur)} | {study.pct(m['total_return_pct'])} | "
                 f"{study.num(None if wr is None else wr * 100, 0)}% | "
                 f"{study.num(rstats['profit_factor'])} | {len(opens)} | {len(realized)} |")
    # Benchmark buy-&-hold over the same [FORWARD_START, today] span, for direct comparison.
    for name, rets in (bench or {}).items():
        L.append(f"| _{name} (buy & hold)_ |  | {study.pct(rets.get('since_start'))} |  |  |  |")
    L.append("")

    L.append("## Open positions (marked to last close)")
    any_open = False
    for strat, policy, result in accounts:
        opens = [c for c in result.closed if c.outcome == "open_at_end"]
        if not opens:
            continue
        any_open = True
        L.append(f"### {strat} — {len(opens)} open")
        L.append("| Symbol | Entry | Now | Unrealized P&L | Days held | Swing |")
        L.append("|---|---|---|---|---|---|")
        for c in sorted(opens, key=lambda c: c.pnl, reverse=True):
            days = (pd.Timestamp(c.exit_date) - pd.Timestamp(c.entry_date)).days
            L.append(f"| {c.symbol} | {_px(c.entry_price, cur)} | {_px(c.exit_price, cur)} | "
                     f"{study.money(c.pnl, cur)} | {days} | {c.swing} |")
        L.append("")
    if not any_open:
        L.append("_None yet — no funded positions are open._")
        L.append("")

    os.makedirs(REPORT_DIR, exist_ok=True)
    open(os.path.join(REPORT_DIR, f"{market}.md"), "w", encoding="utf-8").write("\n".join(L))


def main():
    ap = argparse.ArgumentParser(description="Advance the paper forward-test by one day, per market.")
    ap.add_argument("--market", choices=["us", "india"], required=True)
    ap.add_argument("--start", default=None,
                    help="warm (default ~6mo) | today | YYYY-MM-DD — FIRST init only, then locked")
    ap.add_argument("--no-refresh", action="store_true",
                    help="skip the data fetch and use the cache as-is (no network)")
    args = ap.parse_args()
    market = args.market
    mkt = study.MARKETS[market]()

    # Refresh today's bar (weekdays only — no new EOD bar on weekends). Failures are non-fatal:
    # fall back to the existing cache so a transient data outage can't break the always-on loop.
    if not args.no_refresh and dt.date.today().weekday() < 5:
        print(f"Refreshing {market} data ...")
        try:
            _refresh(market)
        except Exception as e:
            print(f"  WARNING: data refresh failed ({str(e)[:140]}); using the existing cache.")
    else:
        print("  (skipping data refresh — weekend or --no-refresh)")

    print(f"Loading {market} cache ...")
    cache = mkt.load_cache()
    cache = {s: df for s, df in cache.items() if df is not None and len(df) >= study.MIN_BARS}
    if not cache:
        sys.exit("No cached symbols — run the backfill first.")
    last = max(df.index.max() for df in cache.values())
    last_date = str(pd.Timestamp(last).date())

    # Lock FORWARD_START on first run; thereafter it is read from state and --start is ignored.
    state = _load_state(market)
    if state is None:
        ws = _resolve_start(args.start, last)
        state = {"forward_start": str(ws), "last_run_date": None}
        print(f"  initialised forward test: start = {pd.Timestamp(ws).date()} "
              f"(mode: {args.start or 'warm'})")
    else:
        if args.start is not None:
            print(f"  note: --start ignored — FORWARD_START is locked at {state['forward_start'][:10]}")
    ws = pd.Timestamp(state["forward_start"])
    if state.get("last_run_date") == last_date:
        print(f"  no new bar since last run ({last_date}) — re-rendering from the same data.")

    print("Detecting V2 setups once (sorted universe -> deterministic) ...")
    all_trades = []
    for sym in sorted(cache):
        all_trades += events.trades_for(sym, cache[sym])

    accounts = []
    for strat in study.STRATEGIES:
        policy = load_policy(f"{mkt.policy_dir}/{strat}.json")
        result = engine.run_backtest(cache, policy, window_start=ws, trades=all_trades)
        accounts.append((strat, policy, result))
        m = result.metrics
        n_open = sum(1 for c in result.closed if c.outcome == "open_at_end")
        print(f"  {strat:24s} ret {study.pct(m['total_return_pct']):>9s}  "
              f"{m['num_trades']:4d} trades  ({n_open} open)")

    # Benchmark over exactly [FORWARD_START, today] — a single window (offset = last - ws).
    fwd_window = [("since_start", pd.Timestamp(last) - ws)]
    bench = study.benchmark_returns(mkt.bench_series(last, fwd_window), last, fwd_window)
    if not bench:
        print("  WARNING: no benchmark fetched — check the provider key/token. Dashboard omits it.")

    _write_dashboard(market, mkt, ws, last, accounts, bench)
    state["last_run_date"] = last_date
    _save_state(market, state)
    print(f"\nWrote {REPORT_DIR}/{market}.md  (forward test since {pd.Timestamp(ws).date()}, "
          f"data through {last_date}).")


if __name__ == "__main__":
    main()
