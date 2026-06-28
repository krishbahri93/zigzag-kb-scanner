"""
run_strategy_matrix.py — backtest 5 colloquial strategies x N timeframes, per market.
=====================================================================================

Produces one detailed per-run report for every (strategy, window) plus a cross-run synthesis,
all under the market's reports dir. Works for either market via --market:

    python scripts/run_strategy_matrix.py                  # india (default) -> reports/
    python scripts/run_strategy_matrix.py --market us      # US             -> reports/us/
    python scripts/run_strategy_matrix.py --market us --capital 50000   # override capital

WHAT'S FIXED vs CONFIGURABLE
  * Capital + per-trade size live in each policy JSON (india: backtest/policies/, us:
    backtest/policies/us/). `--capital N` overrides the starting capital for ALL policies at
    runtime, scaling fixed-amount sizing proportionally so each strategy keeps its fractional
    shape (percent-of-capital sizing auto-scales).
  * Timeframes are the per-market WINDOWS below.

HOW A WINDOW WORKS
  The V2 engine detects setups on each symbol's FULL history (so the signals are correct), but
  each run only TRADES inside its window via engine.run_backtest(window_start=...). So even the
  shortest window is meaningful — it has full warmup but only counts entries from the window on.

PERF: the V2 signals are identical across every policy and window, so we detect them ONCE for the
whole universe and pass them to all runs via `trades=`.

MARKETS (DRY): the only things that differ by market — data source, benchmark, currency, policy
dir, output dir, windows — live in the small Market configs below (_india_market / _us_market).
Everything else (detect-once, the window loop, the detail report, the synthesis) is shared. The US
cache load reuses the backtester's own pinescan.backtest.run._load_market, and the benchmark math
is one generic helper fed each market's index/ETF close series.
"""
import os
import sys
import glob
import argparse
from dataclasses import dataclass

import pandas as pd

# Windows consoles default to cp1252; force UTF-8 so the Rs / $ / box-drawing glyphs print.
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

from pinescan.backtest.rules.registry import load_policy
from pinescan.backtest import engine, events, report as rpt
from pinescan.backtest import run as bt_run
from pinescan.markets import india, us

MIN_BARS = 60                       # skip thinly-listed symbols the engine can't warm up

STRATEGIES = ["s1_equal_weight", "s2_capital_rotation", "s3_concentrated",
              "s4_diversified", "s5_fractional_rotation"]

# (label, offset back from the last bar). Order = longest -> shortest. India has ~5y of Dhan
# history; US (free Polygon) has ~2y, so its windows are scaled to fit. Both are 6 windows.
INDIA_WINDOWS = [
    ("5y", pd.DateOffset(years=5)), ("3y", pd.DateOffset(years=3)),
    ("1y", pd.DateOffset(years=1)), ("6mo", pd.DateOffset(months=6)),
    ("3mo", pd.DateOffset(months=3)), ("6wk", pd.DateOffset(weeks=6)),
]
US_WINDOWS = [
    ("2y", pd.DateOffset(years=2)), ("18mo", pd.DateOffset(months=18)),
    ("1y", pd.DateOffset(years=1)), ("6mo", pd.DateOffset(months=6)),
    ("3mo", pd.DateOffset(months=3)), ("6wk", pd.DateOffset(weeks=6)),
]


# ---------------------------------------------------------------------------
# Market config — the only place the two markets differ (see module header).
# ---------------------------------------------------------------------------
@dataclass
class Market:
    """Everything the shared study loop needs that differs by market.

    load_cache() -> {symbol: daily df}; bench_series(last, windows) -> {benchmark name: Close
    series or None}. money_sym is the detail-report currency prefix ('Rs ' / '$'); tree_currency
    is the glyph passed to report.english_tree ('₹' / '$'). To add a market, add a builder below
    and register it in _MARKETS — nothing downstream changes.
    """
    key: str
    title: str
    capital_label: str
    money_sym: str
    tree_currency: str
    policy_dir: str
    out_dir: str
    windows: list
    load_cache: object
    bench_series: object


def _india_market():
    """India: NSE Nifty-500 stocks + Nifty/Sensex benchmark, both from Dhan."""
    def load():
        # Use the cache dir itself as the universe (the source of truth) — don't re-fetch the
        # Nifty-500 list over the network, which can fall back to a 20-stock shortlist.
        syms = [os.path.splitext(os.path.basename(f))[0]
                for f in glob.glob(f"{india.CACHE_DIR}/*.parquet")]
        cache = india.load_cache(syms)
        # Dhan occasionally returns a duplicate date; dedupe (keep last) + sort so the simulator's
        # price-by-date lookup returns a scalar, not a Series. (MIN_BARS filter is applied in main.)
        return {s: df[~df.index.duplicated(keep="last")].sort_index()
                for s, df in cache.items() if df is not None}

    def bench(last, windows):
        days = _lookback_days(last, windows)
        out = {}
        for name, sid in india.INDEX_IDS.items():
            try:
                df = india.fetch_index_daily(sid, days=days)
            except Exception:
                df = None
            out[name] = df["Close"] if (df is not None and len(df)) else None
        return out

    return Market("india", "India (NSE Nifty-500)", "Rs 20,00,000", "Rs ", "₹",
                  "pinescan/backtest/policies", "reports", INDIA_WINDOWS, load, bench)


def _us_market():
    """US: Polygon liquid-1000 stocks + SPY/QQQ benchmark, both from Polygon."""
    def load():
        # Reuse the backtester's own loader (universe.json + load_cache + MIN_BARS filter + trim);
        # us.select_liquid_universe reads the cached universe.json, so this is network-free. Free
        # Polygon caps history at ~2y; years=3 keeps all of it (the windows slice from there).
        return bt_run._load_market("us", years=3)

    def bench(last, windows):
        days = _lookback_days(last, windows)
        out = {}
        for name, tkr in us.US_BENCHMARKS.items():
            try:
                df = us.fetch_benchmark_daily(tkr, days=days)
            except Exception:
                df = None
            out[name] = df["Close"] if (df is not None and len(df)) else None
        return out

    return Market("us", "US (Polygon liquid-1000)", "$20,000", "$", "$",
                  "pinescan/backtest/policies/us", "reports/us", US_WINDOWS, load, bench)


_MARKETS = {"india": _india_market, "us": _us_market}


# ---------------------------------------------------------------------------
# formatting helpers (None-safe — a metric undefined on a run prints "N/A")
# ---------------------------------------------------------------------------
def _money(v, sym):
    return "N/A" if v is None else f"{sym}{v:,.0f}"


def _pct(v, signed=True):
    if v is None:
        return "N/A"
    return f"{v:+.2f}%" if signed else f"{v:.2f}%"


def _num(v, nd=2):
    if v is None:
        return "N/A"
    return f"{v:.{nd}f}" if isinstance(v, float) else f"{v}"


def _rescale_capital(policy, new_total):
    """Override a policy's starting capital and scale fixed_amount sizing proportionally, so one
    --capital knob resizes the whole study while preserving each strategy's fractional structure.
    percent_of_capital sizes off the new total automatically, so it's left untouched."""
    old = policy.total_capital
    policy.total_capital = new_total
    if old and "amount" in policy.sizing_params:
        policy.sizing_params["amount"] = policy.sizing_params["amount"] * new_total / old


# ---------------------------------------------------------------------------
# one detailed markdown report for a single (strategy, window) run
# ---------------------------------------------------------------------------
def _detail_md(strat, policy, wlabel, ws, last, result, mkt):
    """Render EVERY stat the run produced — nothing skimped — as markdown, in the market's
    currency (mkt.money_sym for amounts, mkt.tree_currency for the english_tree)."""
    m = result.metrics
    cur = mkt.money_sym
    final_eq = result.equity_curve[-1][1] if result.equity_curve else policy.total_capital
    win_rate_pct = None if m["win_rate"] is None else m["win_rate"] * 100.0

    L = [
        f"# {strat}  —  {wlabel} timeframe",
        "",
        f"_Window: {ws.date()} -> {last.date()}  ·  starting capital {_money(policy.total_capital, cur)}_",
        "",
        "## Strategy (plain English — generated from the rules that ran)",
        "```",
        rpt.english_tree(policy, mkt.tree_currency),
        "```",
        "",
        "## Headline",
        f"- Capital: {_money(policy.total_capital, cur)}  ->  **{_money(final_eq, cur)}**",
        f"- Total return: **{_pct(m['total_return_pct'])}**   ·   CAGR: {_pct(m['cagr'])}",
        f"- Max drawdown: {_num(m['max_drawdown_pct'])}%",
        "",
        "## Trade outcomes",
        f"- Total trades: **{m['num_trades']}**",
        f"- Hit TARGET: **{m['n_target_hit']}**   ·   Hit STOP: **{m['n_stop_hit']}**   ·   "
        f"Rotated out: {m['n_rotated_out']}   ·   Still open at end: {m['n_open_at_end']}",
        f"- Win rate: {_num(win_rate_pct, 1)}%   ·   Avg R: {_num(m['avg_r'])}   ·   "
        f"Profit factor: {_num(m['profit_factor'])}",
        f"- Expectancy / trade: {_money(m['expectancy'], cur)}   ·   Avg holding: {_num(m['avg_holding_days'], 1)} days",
        "",
        "## P&L detail",
        f"- Net P&L: {_money(m['total_pnl'], cur)}",
        f"- Gross profit: {_money(m['gross_profit'], cur)}   ·   Gross loss: {_money(m['gross_loss'], cur)}",
        f"- Avg win: {_money(m['avg_win'], cur)}   ·   Avg loss: {_money(m['avg_loss'], cur)}",
        f"- Best trade: {_money(m['best_trade'], cur)}   ·   Worst trade: {_money(m['worst_trade'], cur)}",
        "",
        "## What the money-management rules did",
        f"- Rotations triggered: {m.get('rotations_triggered', 0)}",
        f"- Signals skipped (no cash / no slot): {m.get('signals_skipped_no_cash', 0)}",
        "",
    ]
    return "\n".join(L)


# ---------------------------------------------------------------------------
# benchmark — buy-&-hold % per window for each index/ETF (shared across markets)
# ---------------------------------------------------------------------------
def _lookback_days(last, windows):
    """Calendar days of benchmark history to fetch: the longest window + 1y head-room, so
    asof(last - longest_window) lands on a real bar instead of underflowing the series."""
    last_ts = pd.Timestamp(last)
    longest = max((last_ts - (last_ts - off)).days for _, off in windows)
    return longest + 365


def _benchmark_returns(close_by_name, last, windows):
    """Per-window buy-&-hold % for each benchmark close series — the benchmark each strategy is
    measured against. close_by_name = {label: Close Series or None}. For window W:
    (close.asof(last) / close.asof(last - W) - 1) * 100. If last - W predates the series (free-tier
    history shorter than the window, e.g. US 2y), anchor at the FIRST available close instead of
    going N/A — an honest 'over the data we have' benchmark. Returns {label: {wlabel: pct or None}};
    a label whose series is missing is dropped, so the synthesis simply omits its row."""
    out = {}
    last_ts = pd.Timestamp(last)
    for name, c in close_by_name.items():
        if c is None or len(c) == 0:
            continue
        c = c[~c.index.duplicated(keep="last")].sort_index()   # defensive: dedupe duplicate dates
        end_px = c.asof(last_ts)                                # last close on/before the run's end
        first_px = float(c.iloc[0])
        rets = {}
        for wlabel, off in windows:
            start_px = c.asof(last_ts - off)
            if start_px is None or pd.isna(start_px):
                start_px = first_px            # window older than available history -> anchor at start
            rets[wlabel] = (float((end_px / start_px - 1) * 100)
                            if (start_px and start_px > 0 and not pd.isna(end_px)) else None)
        out[name] = rets
    return out


# ---------------------------------------------------------------------------
# the cross-run synthesis (one table per key metric + best-per-window)
# ---------------------------------------------------------------------------
def _write_synthesis(synth, last, mkt, bench=None):
    wlabels = [w for w, _ in mkt.windows]
    L = ["# Strategy x Timeframe — Synthesis",
         "",
         f"_{mkt.title}, data through {last.date()}, capital {mkt.capital_label} fixed for all runs._",
         "",
         "Five colloquial money-management strategies over the same V2 signals, each run on six",
         "trailing windows. Capital and signals are identical across the board — only the sizing",
         "and position-management rules differ, so any difference is the strategy's doing.",
         ""]

    # What each strategy does — pulled from the policy `description` so it never drifts from the
    # rules that actually ran.
    L.append("## The strategies")
    for s in STRATEGIES:
        L.append(f"- **{s}** — {load_policy(f'{mkt.policy_dir}/{s}.json').description}")
    L.append("")

    def table(metric, title, fmt, extra=None):
        L.append(f"## {title}")
        L.append("| Strategy | " + " | ".join(wlabels) + " |")
        L.append("|" + "---|" * (len(wlabels) + 1))
        for s in STRATEGIES:
            row = [s]
            for w in wlabels:
                v = synth[(s, w)].get(metric)
                row.append("N/A" if v is None else fmt(v))
            L.append("| " + " | ".join(row) + " |")
        # benchmark rows under the strategies (e.g. the index/ETF buy-&-hold return per window)
        for label, vals in (extra or []):
            row = [f"_{label}_"] + ["N/A" if vals.get(w) is None else fmt(vals.get(w)) for w in wlabels]
            L.append("| " + " | ".join(row) + " |")
        L.append("")

    # Total return with the benchmark buy-&-hold rows appended, so each strategy's return sits
    # directly above the index/ETF for the same window.
    bench_rows = [(f"{name} (buy & hold)", rets) for name, rets in (bench or {}).items()]
    table("total_return_pct", "Total return %", lambda v: f"{v:+.1f}", extra=bench_rows)
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
    open(f"{mkt.out_dir}/SYNTHESIS.md", "w", encoding="utf-8").write("\n".join(L))


def main():
    ap = argparse.ArgumentParser(
        description="5-strategy x N-window V2 backtest study + synthesis, per market.")
    ap.add_argument("--market", choices=["india", "us"], default="india",
                    help="which market to study (default: india)")
    ap.add_argument("--capital", type=float, default=None,
                    help="override starting capital for ALL policies (scales fixed sizing "
                         "proportionally); default = each policy's JSON value")
    args = ap.parse_args()
    mkt = _MARKETS[args.market]()
    if args.capital is not None:
        mkt.capital_label = _money(args.capital, mkt.money_sym)   # reflect the override in the subtitle

    print(f"Loading {args.market} cache ...")
    cache = mkt.load_cache()
    cache = {s: df for s, df in cache.items() if df is not None and len(df) >= MIN_BARS}
    print(f"  {len(cache)} symbols with >= {MIN_BARS} bars")

    print("Detecting V2 setups across the universe (once, reused for all runs) ...")
    all_trades = []
    for sym, df in cache.items():
        all_trades += events.trades_for(sym, df)
    print(f"  {len(all_trades)} V2 entry signals total")

    last = max(df.index.max() for df in cache.values())
    os.makedirs(mkt.out_dir, exist_ok=True)

    synth = {}
    for strat in STRATEGIES:
        policy = load_policy(f"{mkt.policy_dir}/{strat}.json")
        if args.capital is not None:
            _rescale_capital(policy, args.capital)
        for wlabel, off in mkt.windows:
            ws = last - off
            result = engine.run_backtest(cache, policy, window_start=ws, trades=all_trades)
            open(f"{mkt.out_dir}/{strat}__{wlabel}.md", "w", encoding="utf-8").write(
                _detail_md(strat, policy, wlabel, ws, last, result, mkt))
            synth[(strat, wlabel)] = result.metrics
            m = result.metrics
            print(f"  {strat:24s} {wlabel:4s}  ret {_pct(m['total_return_pct']):>9s}  "
                  f"{m['num_trades']:4d} trades  ({m['n_target_hit']} tp / {m['n_stop_hit']} sl)")

    print(f"Fetching benchmark returns ({args.market}) ...")
    bench = _benchmark_returns(mkt.bench_series(last, mkt.windows), last, mkt.windows)
    if not bench:
        # bench_series swallows fetch errors and returns None series; the usual cause is a missing
        # /expired provider key. Make that loud, not silent — otherwise the synthesis quietly loses
        # its benchmark rows and looks fine.
        print("  WARNING: no benchmark fetched — check the provider key/token (Dhan .dhan_creds "
              "or Polygon .polygon_key). The synthesis will omit the benchmark rows.")
    _write_synthesis(synth, last, mkt, bench)
    nrep = len(STRATEGIES) * len(mkt.windows)
    tail = "with benchmark" if bench else "WITHOUT benchmark (provider key/token missing?)"
    print(f"\nWrote {nrep} reports + SYNTHESIS.md ({tail}) to {mkt.out_dir}/")


if __name__ == "__main__":
    main()
