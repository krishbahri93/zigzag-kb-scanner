"""
US (Polygon) market data — liquid universe + per-date daily OHLCV cache.

Data-fetching only (the dual-trade strategy that used to live alongside this was
dropped in the Phase-1 restructure). Polygon "Grouped Daily" returns every ticker's
OHLCV for one date in a single call, so backfilling 1000 symbols costs the same
~N-trading-day calls as backfilling 50; results cache one parquet per date under
data/cache/us (resumable). Free tier (5 calls/min, ~2yr history, EOD) is enough for
scanning + backtesting; intraday needs the paid tier.

Environment:
    POLYGON_API_KEY   Polygon API key (free tier OK for EOD)
"""
import os
import time
import json
import datetime as dt

import requests
import pandas as pd

from .base import resample_weekly
from .. import io_safe

# ============================================================================
# CONFIG
# ============================================================================

POLY = "https://api.polygon.io"
US_EXCHANGES = {"XNYS", "XNAS", "XASE"}   # NYSE, NASDAQ, NYSE American
CACHE_DIR = "data/cache/us"                # one parquet per date (resumable)
UNIVERSE_FILE = "data/cache/us/universe.json"   # cached liquid-universe selection

# Benchmark tickers the backtest study measures each strategy against (buy-&-hold). SPY ≈
# S&P 500, QQQ ≈ Nasdaq-100. These are ETFs, NOT in the type=CS scan universe, so
# fetch_benchmark_daily pulls them straight from Polygon's single-ticker aggregates rather
# than the per-date stock cache. Mirrors india.INDEX_IDS on the Dhan side.
US_BENCHMARKS = {"S&P 500 (SPY)": "SPY", "Nasdaq-100 (QQQ)": "QQQ"}

# Free tier = 5 calls/min. 13s spacing ≈ 4.6/min — a safe margin.
RATE_SLEEP = float(os.environ.get("US_RATE_SLEEP", "13"))

_session = requests.Session()


def ensure_api_key(path=None):
    """Make sure POLYGON_API_KEY is in os.environ, loading it from a local, git-ignored
    `.polygon_key` file (a single line) if it isn't already set. Returns True if a key is
    present afterwards.

    This is the ONE place the `.polygon_key` convention lives, so every entry point (scanner
    refresh, backtest benchmark) loads it the same way — _api_key() calls it lazily, so callers
    usually don't need to. `path` overrides the search (default: ./.polygon_key, then
    ~/.polygon_key). Mirrors india.ensure_dhan_creds on the Dhan side.
    """
    if os.environ.get("POLYGON_API_KEY"):
        return True
    for p in ([path] if path else [".polygon_key", os.path.expanduser("~/.polygon_key")]):
        if p and os.path.exists(p):
            key = open(p, encoding="utf-8").read().strip()
            if key:
                os.environ["POLYGON_API_KEY"] = key
                print(f"  loaded POLYGON_API_KEY from {p}")
                return True
    return bool(os.environ.get("POLYGON_API_KEY"))


def _api_key():
    """Return the Polygon API key, auto-loading `.polygon_key` via ensure_api_key() first so any
    entry point works without wiring the key itself; raise if none is available anywhere."""
    ensure_api_key()
    try:
        return os.environ["POLYGON_API_KEY"]
    except KeyError:
        raise RuntimeError("POLYGON_API_KEY environment variable is not set")


def _get(url, params=None, max_retries=6):
    """GET a Polygon endpoint with apiKey + 429 backoff. Caller controls pacing."""
    p = dict(params or {})
    p["apiKey"] = _api_key()
    last = None
    for attempt in range(max_retries):
        r = _session.get(url, params=p, timeout=40)
        if r.status_code == 429:
            time.sleep(RATE_SLEEP * (attempt + 2))   # exponential-ish backoff
            last = r
            continue
        r.raise_for_status()
        return r.json()
    if last is not None:
        last.raise_for_status()
    raise RuntimeError(f"GET failed after {max_retries} retries: {url}")


# ============================================================================
# UNIVERSE — active US common stocks, filtered to a liquid subset
# ============================================================================

def load_cs_tickers():
    """Page the Tickers reference endpoint → {ticker: {name, exch}} for active
    US common stocks (type=CS) on NYSE/NASDAQ/AMEX."""
    out = {}
    url = f"{POLY}/v3/reference/tickers"
    params = {"market": "stocks", "active": "true", "type": "CS",
              "limit": 1000, "sort": "ticker"}
    page = 0
    while True:
        j = _get(url, params)
        for r in j.get("results", []):
            if (r.get("primary_exchange") in US_EXCHANGES
                    and r.get("type") == "CS" and r.get("active")):
                out[r["ticker"]] = {"name": r.get("name", ""),
                                    "exch": r.get("primary_exchange")}
        page += 1
        nxt = j.get("next_url")
        if not nxt:
            break
        url, params = nxt, {}     # next_url carries its own cursor/query
        time.sleep(RATE_SLEEP)
    print(f"  reference: {len(out)} active US common stocks across {page} pages")
    return out


def _grouped_daily(date_str):
    """One Grouped-Daily call → list of {T,o,h,l,c,v,t,...} for every ticker on
    that date. Empty list on weekends/holidays."""
    url = f"{POLY}/v2/aggs/grouped/locale/us/market/stocks/{date_str}"
    j = _get(url, {"adjusted": "true"})
    return j.get("results") or []


def _recent_weekday(offset_back=1):
    d = dt.date.today() - dt.timedelta(days=offset_back)
    while d.weekday() >= 5:        # skip Sat/Sun
        d -= dt.timedelta(days=1)
    return d


def select_liquid_universe(n=1000, min_price=5.0, force=False):
    """Pick the top-`n` liquid common stocks by dollar-volume (close*volume) from
    the most recent completed trading day. Cached to UNIVERSE_FILE so the smoke
    test and the full run select the SAME symbols.

    Returns (symbols_list, {symbol: sector_label}).
    """
    if not force and os.path.exists(UNIVERSE_FILE):
        d = json.load(open(UNIVERSE_FILE))
        if d.get("symbols"):                  # an EMPTY cached selection is a failed selection
            print(f"  universe: loaded {len(d['symbols'])} symbols from {UNIVERSE_FILE}")
            return d["symbols"], d["sectors"]
        print("  universe: cached selection is EMPTY (failed run) — re-selecting …")

    cs = load_cs_tickers()
    day = _recent_weekday()
    print(f"  ranking liquidity from grouped bar {day} …")
    rows = _grouped_daily(day.isoformat())
    cand = []
    for r in rows:
        t = r.get("T")
        c, v = r.get("c"), r.get("v")
        if t not in cs or not c or not v or c < min_price:
            continue
        cand.append((t, c * v))
    cand.sort(key=lambda x: x[1], reverse=True)
    symbols = [t for t, _ in cand[:n]]
    # Sector: the reference endpoint doesn't carry SIC; use "-" for now
    # (dashboard tolerates it). Real sector mapping is a later enhancement.
    sectors = {t: "-" for t in symbols}
    if not symbols:
        # never PERSIST a failed selection — the next caller must retry, not inherit zero
        print("  universe: selection came back EMPTY (throttle/outage?) — NOT caching it")
        return symbols, sectors
    os.makedirs(os.path.dirname(UNIVERSE_FILE), exist_ok=True)   # data/ is gitignored: create on first run
    io_safe.atomic_write_text(UNIVERSE_FILE, json.dumps({"symbols": symbols, "sectors": sectors}))
    print(f"  universe: selected {len(symbols)} liquid names (>= ${min_price}, "
          f"by $-volume), saved to {UNIVERSE_FILE}")
    return symbols, sectors


# ============================================================================
# BACKFILL — grouped-daily per date, resumable, free-tier throttled
# ============================================================================

def _weekdays(days):
    """List of weekday dates from (today-days) .. yesterday, newest first."""
    end = dt.date.today() - dt.timedelta(days=1)
    start = dt.date.today() - dt.timedelta(days=days)
    out = []
    d = start
    while d <= end:
        if d.weekday() < 5:
            out.append(d)
        d += dt.timedelta(days=1)
    out.reverse()                 # newest first → most useful data lands first
    return out


def backfill(symbols, days=730, progress_every=10):
    """Fetch grouped-daily for each weekday in the window, keep only `symbols`,
    and write one parquet per date in CACHE_DIR. Resumable: dates whose parquet
    already exists are skipped, so an interrupted run continues where it left off.

    Grouped is billed PER DATE (one call = all tickers), so 1,000 vs 50 symbols
    costs the same ~N-trading-day calls.
    """
    os.makedirs(CACHE_DIR, exist_ok=True)
    symset = set(symbols)
    dates = _weekdays(days)
    total = len(dates)
    done = fetched = 0
    print(f"  backfill window: {total} weekdays, ~{RATE_SLEEP:.0f}s/call "
          f"(≈ {total * RATE_SLEEP / 60:.0f} min if none cached)")
    for d in dates:
        done += 1
        fp = os.path.join(CACHE_DIR, f"{d.isoformat()}.parquet")
        if os.path.exists(fp):
            continue
        try:
            rows = _grouped_daily(d.isoformat())
        except Exception as e:
            print(f"    {d}: error {str(e)[:90]} — will retry on resume")
            time.sleep(RATE_SLEEP)
            continue
        keep = [{"T": r["T"], "o": r.get("o"), "h": r.get("h"), "l": r.get("l"),
                 "c": r.get("c"), "v": r.get("v"), "t": r.get("t")}
                for r in rows if r.get("T") in symset]
        cols = ["T", "o", "h", "l", "c", "v", "t"]
        io_safe.atomic_to_parquet(pd.DataFrame(keep, columns=cols), fp, index=False)  # crash-safe; empty on holidays
        fetched += 1
        if done % progress_every == 0 or done == total:
            print(f"    backfill {done}/{total} ({fetched} fetched) … {d} "
                  f"[{len(keep)} symbols]")
        time.sleep(RATE_SLEEP)
    print(f"  backfill complete: {total} dates scanned, {fetched} fetched this run")


def load_cache(symbols):
    """Read all per-date parquet files → {symbol: daily DataFrame} with columns
    Open/High/Low/Close/Volume, indexed by America/New_York date."""
    if not os.path.isdir(CACHE_DIR):
        return {}
    symset = set(symbols)
    frames = []
    for fn in sorted(os.listdir(CACHE_DIR)):
        if not fn.endswith(".parquet"):
            continue
        fp = os.path.join(CACHE_DIR, fn)
        df = io_safe.read_parquet_safe(fp)
        if df is None:                    # corrupt (e.g. a pre-fix crash) → drop it; next refresh refetches
            try:
                os.remove(fp)
            except OSError:
                pass
            continue
        if df.empty:
            continue
        frames.append(df[df["T"].isin(symset)])
    if not frames:
        return {}
    allrows = pd.concat(frames, ignore_index=True)
    allrows = allrows.dropna(subset=["t", "c"])
    allrows["date"] = (pd.to_datetime(allrows["t"], unit="ms", utc=True)
                       .dt.tz_convert("America/New_York"))
    cache = {}
    for sym, g in allrows.groupby("T"):
        g = g.sort_values("date")
        cache[sym] = pd.DataFrame(
            {"Open": g["o"].to_numpy(float), "High": g["h"].to_numpy(float),
             "Low": g["l"].to_numpy(float), "Close": g["c"].to_numpy(float),
             "Volume": g["v"].to_numpy(float)},
            index=pd.DatetimeIndex(g["date"].to_numpy()),
        )
    return cache


def us_get_tf(sym, tf, cache):
    """Cache-backed equivalent of the engine's get_tf (no network in the loop)."""
    d = cache.get(sym)
    if d is None or len(d) == 0:
        return None
    if tf == "1D":
        return d
    if tf == "1W":
        return resample_weekly(d)
    raise ValueError(f"Unsupported tf: {tf}")


def fetch_benchmark_daily(ticker, days=760):
    """Daily OHLCV for one benchmark ticker (e.g. 'SPY', 'QQQ') via Polygon's single-ticker
    aggregates endpoint. Returns a DataFrame indexed by America/New_York date (so it lines up
    with load_cache's stock frames), or None if Polygon returns nothing.

    Used by the backtest study as the buy-&-hold benchmark each strategy is measured against
    (see US_BENCHMARKS). SPY/QQQ are ETFs, excluded from the type=CS scan universe, so they're
    pulled directly here rather than read from the per-date cache. Free Polygon serves ~2y of
    history, so a `days` beyond that simply returns what's available. Reuses _get (apiKey + 429
    backoff); mirrors india.fetch_index_daily on the Dhan side.
    """
    end = dt.date.today()
    start = end - dt.timedelta(days=days)
    url = f"{POLY}/v2/aggs/ticker/{ticker}/range/1/day/{start.isoformat()}/{end.isoformat()}"
    j = _get(url, {"adjusted": "true", "sort": "asc", "limit": 50000})
    rows = j.get("results") or []
    if not rows:
        return None
    df = pd.DataFrame(rows)
    idx = pd.to_datetime(df["t"], unit="ms", utc=True).dt.tz_convert("America/New_York")
    out = pd.DataFrame({
        "Open": df["o"].to_numpy(float), "High": df["h"].to_numpy(float),
        "Low": df["l"].to_numpy(float), "Close": df["c"].to_numpy(float),
        "Volume": df["v"].to_numpy(float),
    }, index=pd.DatetimeIndex(idx.to_numpy()))
    return out.sort_index()
