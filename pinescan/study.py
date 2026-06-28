"""
pinescan/study.py — shared per-market study machinery (data source + benchmark + currency).
============================================================================================

Used by BOTH the backtest matrix (`scripts/run_strategy_matrix.py`) and the forward-test runner
(`scripts/forward_run.py`), so the per-market wiring lives in exactly ONE place — no duplication.

A `Market` bundles how to load that market's universe cache and its benchmark close-series, plus
the currency labels for reports. **Windows and output dirs are the CONSUMER's concern** (a backtest
sweeps several timeframes into `reports/`; the forward runner uses one growing window into
`reports/forward/`), so they are deliberately NOT stored on `Market`.

To add a market: write a `_<name>_market()` builder and register it in `MARKETS`; everything
downstream (both the matrix and the forward runner) picks it up — nothing else changes.
"""
import os
import glob
from dataclasses import dataclass

import pandas as pd

from pinescan.backtest import run as bt_run
from pinescan.markets import india, us

# Drop symbols with fewer than this many daily bars — too little to warm up a V2 setup. The
# consumer applies this filter after load_cache(); it lives here so both studies use one cutoff.
MIN_BARS = 60

# The five colloquial strategies (policy file stems), shared by every study.
STRATEGIES = ["s1_equal_weight", "s2_capital_rotation", "s3_concentrated",
              "s4_diversified", "s5_fractional_rotation"]


@dataclass
class Market:
    """Per-market wiring shared by every study.

    Fields:
      load_cache()                 -> {symbol: daily OHLCV df} for the market's frozen universe
      bench_series(last, windows)  -> {benchmark name: Close Series or None} (index/ETF closes)
      money_sym                    report currency prefix for amounts ('Rs ' / '$')
      tree_currency                glyph passed to report.english_tree ('₹' / '$')
      policy_dir                   where this market's policy JSONs live
      title / capital_label        report subtitle text

    Windows and output dirs are intentionally NOT here — they are the caller's concern (see the
    module header), so the same Market serves both the timeframe sweep and the forward runner.
    """
    key: str
    title: str
    capital_label: str
    money_sym: str
    tree_currency: str
    policy_dir: str
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
        # price-by-date lookup returns a scalar, not a Series. (MIN_BARS filter applied by caller.)
        return {s: df[~df.index.duplicated(keep="last")].sort_index()
                for s, df in cache.items() if df is not None}

    def bench(last, windows):
        days = lookback_days(last, windows)
        out = {}
        for name, sid in india.INDEX_IDS.items():
            try:
                df = india.fetch_index_daily(sid, days=days)
            except Exception:
                df = None
            out[name] = df["Close"] if (df is not None and len(df)) else None
        return out

    return Market("india", "India (NSE Nifty-500)", "Rs 20,00,000", "Rs ", "₹",
                  "pinescan/backtest/policies", load, bench)


def _us_market():
    """US: Polygon liquid-1000 stocks + SPY/QQQ benchmark, both from Polygon."""
    def load():
        # Reuse the backtester's own loader (universe.json + load_cache + MIN_BARS filter + trim);
        # us.select_liquid_universe reads the cached universe.json, so this is network-free. Free
        # Polygon caps history at ~2y; years=3 keeps all of it.
        return bt_run._load_market("us", years=3)

    def bench(last, windows):
        days = lookback_days(last, windows)
        out = {}
        for name, tkr in us.US_BENCHMARKS.items():
            try:
                df = us.fetch_benchmark_daily(tkr, days=days)
            except Exception:
                df = None
            out[name] = df["Close"] if (df is not None and len(df)) else None
        return out

    return Market("us", "US (Polygon liquid-1000)", "$20,000", "$", "$",
                  "pinescan/backtest/policies/us", load, bench)


MARKETS = {"india": _india_market, "us": _us_market}


# ---------------------------------------------------------------------------
# formatting helpers (None-safe — a metric undefined on a run prints "N/A")
# ---------------------------------------------------------------------------
def money(v, sym):
    return "N/A" if v is None else f"{sym}{v:,.0f}"


def pct(v, signed=True):
    if v is None:
        return "N/A"
    return f"{v:+.2f}%" if signed else f"{v:.2f}%"


def num(v, nd=2):
    if v is None:
        return "N/A"
    return f"{v:.{nd}f}" if isinstance(v, float) else f"{v}"


def rescale_capital(policy, new_total):
    """Override a policy's starting capital and scale fixed_amount sizing proportionally, so one
    capital knob resizes the whole study while preserving each strategy's fractional structure.
    percent_of_capital sizes off the new total automatically, so it's left untouched."""
    old = policy.total_capital
    policy.total_capital = new_total
    if old and "amount" in policy.sizing_params:
        policy.sizing_params["amount"] = policy.sizing_params["amount"] * new_total / old


# ---------------------------------------------------------------------------
# benchmark — buy-&-hold % per window for each index/ETF (shared across markets)
# ---------------------------------------------------------------------------
def lookback_days(last, windows):
    """Calendar days of benchmark history to fetch: the longest window + 1y head-room, so
    asof(last - longest_window) lands on a real bar instead of underflowing the series."""
    last_ts = pd.Timestamp(last)
    longest = max((last_ts - (last_ts - off)).days for _, off in windows)
    return longest + 365


def benchmark_returns(close_by_name, last, windows):
    """Per-window buy-&-hold % for each benchmark close series — the benchmark each strategy is
    measured against. close_by_name = {label: Close Series or None}. For window W:
    (close.asof(last) / close.asof(last - W) - 1) * 100. If last - W predates the series (free-tier
    history shorter than the window, e.g. US 2y), anchor at the FIRST available close instead of
    going N/A — an honest 'over the data we have' benchmark. Returns {label: {wlabel: pct or None}};
    a label whose series is missing is dropped, so the caller simply omits its row."""
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
