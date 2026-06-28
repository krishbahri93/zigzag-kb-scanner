"""
run_strategy_matrix.py — backtest 5 colloquial strategies x 6 timeframes (India).
=================================================================================

Produces 30 detailed per-run reports + 1 synthesis, all under reports/.

WHAT'S FIXED vs CONFIGURABLE
  * Capital is FIXED at the value in each policy JSON (Rs 20,00,000 for all five), per
    the study's rule.
  * The configurable knobs are: per-trade size (an absolute amount or a % of capital,
    set in the policy's `sizing` block) and the timeframe (the 6 windows below).

HOW A WINDOW WORKS
  The V2 engine detects setups on each symbol's FULL history (so the signals are
  correct), but each run only TRADES inside its window via
  engine.run_backtest(window_start=...). So even the 6-week run is meaningful — it has
  full warmup but only counts entries from the last 6 weeks. The 5y window uses
  whatever history Dhan provided (~5 years).

PERF: the V2 signals are identical across every policy and window, so we detect them
ONCE for the whole universe and pass them to all 30 runs via `trades=`.

Usage:  python scripts/run_strategy_matrix.py
"""
import os
import sys

import pandas as pd

# Windows consoles default to cp1252; force UTF-8 so the Rs / box-drawing glyphs print.
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

from pinescan.backtest.rules.registry import load_policy
from pinescan.backtest import engine, events, report as rpt
from pinescan.markets import india

POLICY_DIR = "pinescan/backtest/policies"
OUT_DIR = "reports"
MIN_BARS = 60                       # skip thinly-listed symbols the engine can't warm up

STRATEGIES = ["s1_equal_weight", "s2_capital_rotation", "s3_concentrated",
              "s4_diversified", "s5_fractional_rotation"]

# (label, offset back from the last bar). Order = longest -> shortest.
WINDOWS = [
    ("5y", pd.DateOffset(years=5)), ("3y", pd.DateOffset(years=3)),
    ("1y", pd.DateOffset(years=1)), ("6mo", pd.DateOffset(months=6)),
    ("3mo", pd.DateOffset(months=3)), ("6wk", pd.DateOffset(weeks=6)),
]


# ---------------------------------------------------------------------------
# formatting helpers (None-safe — a metric undefined on a run prints "N/A")
# ---------------------------------------------------------------------------
def _money(v):
    return "N/A" if v is None else f"Rs {v:,.0f}"


def _pct(v, signed=True):
    if v is None:
        return "N/A"
    return f"{v:+.2f}%" if signed else f"{v:.2f}%"


def _num(v, nd=2):
    if v is None:
        return "N/A"
    return f"{v:.{nd}f}" if isinstance(v, float) else f"{v}"


# ---------------------------------------------------------------------------
# one detailed markdown report for a single (strategy, window) run
# ---------------------------------------------------------------------------
def _detail_md(strat, policy, wlabel, ws, last, result):
    """Render EVERY stat the run produced — nothing skimped — as markdown."""
    m = result.metrics
    final_eq = result.equity_curve[-1][1] if result.equity_curve else policy.total_capital
    win_rate_pct = None if m["win_rate"] is None else m["win_rate"] * 100.0

    L = [
        f"# {strat}  —  {wlabel} timeframe",
        "",
        f"_Window: {ws.date()} -> {last.date()}  ·  starting capital {_money(policy.total_capital)}_",
        "",
        "## Strategy (plain English — generated from the rules that ran)",
        "```",
        rpt.english_tree(policy),
        "```",
        "",
        "## Headline",
        f"- Capital: {_money(policy.total_capital)}  ->  **{_money(final_eq)}**",
        f"- Total return: **{_pct(m['total_return_pct'])}**   ·   CAGR: {_pct(m['cagr'])}",
        f"- Max drawdown: {_num(m['max_drawdown_pct'])}%",
        "",
        "## Trade outcomes",
        f"- Total trades: **{m['num_trades']}**",
        f"- Hit TARGET: **{m['n_target_hit']}**   ·   Hit STOP: **{m['n_stop_hit']}**   ·   "
        f"Rotated out: {m['n_rotated_out']}   ·   Still open at end: {m['n_open_at_end']}",
        f"- Win rate: {_num(win_rate_pct, 1)}%   ·   Avg R: {_num(m['avg_r'])}   ·   "
        f"Profit factor: {_num(m['profit_factor'])}",
        f"- Expectancy / trade: {_money(m['expectancy'])}   ·   Avg holding: {_num(m['avg_holding_days'], 1)} days",
        "",
        "## P&L detail",
        f"- Net P&L: {_money(m['total_pnl'])}",
        f"- Gross profit: {_money(m['gross_profit'])}   ·   Gross loss: {_money(m['gross_loss'])}",
        f"- Avg win: {_money(m['avg_win'])}   ·   Avg loss: {_money(m['avg_loss'])}",
        f"- Best trade: {_money(m['best_trade'])}   ·   Worst trade: {_money(m['worst_trade'])}",
        "",
        "## What the money-management rules did",
        f"- Rotations triggered: {m.get('rotations_triggered', 0)}",
        f"- Signals skipped (no cash / no slot): {m.get('signals_skipped_no_cash', 0)}",
        "",
    ]
    return "\n".join(L)


# ---------------------------------------------------------------------------
# the cross-run synthesis (one table per key metric + best-per-window)
# ---------------------------------------------------------------------------
def _write_synthesis(synth, last):
    wlabels = [w for w, _ in WINDOWS]
    L = ["# Strategy x Timeframe — Synthesis",
         "",
         f"_India (NSE Nifty-500), data through {last.date()}, capital Rs 20,00,000 fixed for all runs._",
         "",
         "Five colloquial money-management strategies over the same V2 signals, each run on six",
         "trailing windows. Capital and signals are identical across the board — only the sizing",
         "and position-management rules differ, so any difference is the strategy's doing.",
         ""]

    def table(metric, title, fmt):
        L.append(f"## {title}")
        L.append("| Strategy | " + " | ".join(wlabels) + " |")
        L.append("|" + "---|" * (len(wlabels) + 1))
        for s in STRATEGIES:
            row = [s]
            for w in wlabels:
                v = synth[(s, w)].get(metric)
                row.append("N/A" if v is None else fmt(v))
            L.append("| " + " | ".join(row) + " |")
        L.append("")

    table("total_return_pct", "Total return %", lambda v: f"{v:+.1f}")
    table("cagr", "CAGR %", lambda v: f"{v:+.0f}")
    table("max_drawdown_pct", "Max drawdown %", lambda v: f"{v:.1f}")
    table("num_trades", "Trades taken", lambda v: f"{v}")
    table("n_target_hit", "Hit target", lambda v: f"{v}")
    table("n_stop_hit", "Hit stop", lambda v: f"{v}")
    table("win_rate", "Win rate %", lambda v: f"{v * 100:.0f}")
    table("rotations_triggered", "Rotations", lambda v: f"{v}")
    table("signals_skipped_no_cash", "Signals skipped", lambda v: f"{v}")

    L.append("## Best strategy per timeframe (by total return)")
    for w in wlabels:
        best = max(STRATEGIES, key=lambda s: (synth[(s, w)].get("total_return_pct") or -1e18))
        L.append(f"- **{w}**: {best}  ({(synth[(best, w)].get('total_return_pct')):+.1f}%)")
    L.append("")
    open(f"{OUT_DIR}/SYNTHESIS.md", "w", encoding="utf-8").write("\n".join(L))


def main():
    import glob
    print("Loading India cache ...")
    # Load whatever was backfilled (don't re-fetch the universe over the network — NSE
    # can block and fall back to a 20-stock shortlist; the cache is the source of truth).
    syms = [os.path.splitext(os.path.basename(f))[0]
            for f in glob.glob(f"{india.CACHE_DIR}/*.parquet")]
    cache = india.load_cache(syms)
    cache = {s: df for s, df in cache.items() if df is not None and len(df) >= MIN_BARS}
    # Dhan occasionally returns a duplicate date for a symbol; dedupe (keep last) and sort
    # so the simulator's price-by-date lookup returns a scalar, not a Series.
    cache = {s: df[~df.index.duplicated(keep="last")].sort_index() for s, df in cache.items()}
    print(f"  {len(cache)} symbols with >= {MIN_BARS} bars")

    print("Detecting V2 setups across the universe (once, reused for all 30 runs) ...")
    all_trades = []
    for sym, df in cache.items():
        all_trades += events.trades_for(sym, df)
    print(f"  {len(all_trades)} V2 entry signals total")

    last = max(df.index.max() for df in cache.values())
    os.makedirs(OUT_DIR, exist_ok=True)

    synth = {}
    for strat in STRATEGIES:
        policy = load_policy(f"{POLICY_DIR}/{strat}.json")
        for wlabel, off in WINDOWS:
            ws = last - off
            result = engine.run_backtest(cache, policy, window_start=ws, trades=all_trades)
            open(f"{OUT_DIR}/{strat}__{wlabel}.md", "w", encoding="utf-8").write(
                _detail_md(strat, policy, wlabel, ws, last, result))
            synth[(strat, wlabel)] = result.metrics
            m = result.metrics
            print(f"  {strat:24s} {wlabel:4s}  ret {_pct(m['total_return_pct']):>9s}  "
                  f"{m['num_trades']:4d} trades  ({m['n_target_hit']} tp / {m['n_stop_hit']} sl)")

    _write_synthesis(synth, last)
    print(f"\nWrote 30 reports + SYNTHESIS.md to {OUT_DIR}/")


if __name__ == "__main__":
    main()
