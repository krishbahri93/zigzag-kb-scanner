"""
US Stocks data layer for the ZigZag KB Fib Dual Trade scanner
=============================================================

This module adapts the scanner to the US market WITHOUT touching the Indian
scanner. The strategy logic in `zigzag_kb_engine.py` is market-agnostic and
data-driven, so we *import and reuse* it here and only provide:

  - a US universe loader (Polygon "Tickers" reference endpoint)
  - a bulk data layer (Polygon "Grouped Daily" — one call returns every ticker's
    OHLCV for a single date) with free-tier throttling + resumable checkpointing
  - thin scan/backtest wrappers that feed cached DataFrames into the imported
    `analyze_one` / `backtest_history`

Nothing in `zigzag_kb_engine.py`, `run_scan.py`, `scan.yml`, `results.json`, or
`performance.json` is modified. US output goes to results_us.json /
performance_us.json (written by run_scan_us.py).

Data source: Polygon.io (now "Massive"). Free tier is enough for EOD backfill +
scanning (5 calls/min, 2 yr history, end-of-day only). Live intraday signals and
a 5-min cadence require the Starter tier (Phase 2).

Environment:
    POLYGON_API_KEY   = Polygon API key (free tier OK for EOD)
"""
import os
import time
import json
import datetime as dt

import requests
import pandas as pd

# ---- Strategy logic ----
# Pine-faithful engine (new). The old zigzag_kb_engine is left untouched; we only
# borrow its pure daily->weekly resampler (read-only, no Indian behavior change).
import pine_engine
# pure read-only utils from the Indian engine (NOT modified)
from zigzag_kb_engine import _resample_weekly, _aggregate_performance

DEV_PCT_DEFAULT = pine_engine.DEV_PCT_DEFAULT

# ============================================================================
# CONFIG
# ============================================================================

POLY = "https://api.polygon.io"
US_EXCHANGES = {"XNYS", "XNAS", "XASE"}   # NYSE, NASDAQ, NYSE American
CACHE_DIR = "us_cache"                     # one parquet per date (resumable)
UNIVERSE_FILE = "us_universe.json"         # cached liquid-universe selection

# Free tier = 5 calls/min. 13s spacing ≈ 4.6/min — a safe margin.
RATE_SLEEP = float(os.environ.get("US_RATE_SLEEP", "13"))

_session = requests.Session()


def _api_key():
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
        print(f"  universe: loaded {len(d['symbols'])} symbols from {UNIVERSE_FILE}")
        return d["symbols"], d["sectors"]

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
    json.dump({"symbols": symbols, "sectors": sectors}, open(UNIVERSE_FILE, "w"))
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
        pd.DataFrame(keep, columns=cols).to_parquet(fp, index=False)  # empty on holidays
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
        df = pd.read_parquet(os.path.join(CACHE_DIR, fn))
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
        return _resample_weekly(d)
    raise ValueError(f"Unsupported tf: {tf}")


# ============================================================================
# SCAN + BACKTEST — feed cached DataFrames into the imported strategy
# ============================================================================

def scan_us(symbols, cache, timeframes=("1D", "1W"), dev_pct=DEV_PCT_DEFAULT,
            partials=None):
    """US scan via the Pine-faithful engine: iterate symbols against the cache and
    call pine_engine.evaluate(df=...). Returns (DataFrame, stats).

    partials: optional {symbol: 1-row today-partial DataFrame} (Phase 2, from
      _snapshot_all). Only the 1D timeframe uses it; supplying it makes signals
      fire intraday (flagged provisional). None → EOD only.
    """
    rows = []
    stats = {"attempted": 0, "fetched_ok": 0, "setups": 0, "sample_errors": []}
    for s in symbols:
        for tf in timeframes:
            stats["attempted"] += 1
            try:
                df = us_get_tf(s, tf, cache)
                if df is None or len(df) < 30:
                    continue
                stats["fetched_ok"] += 1
                tp = partials.get(s) if (partials and tf == "1D") else None
                r = pine_engine.evaluate(s, tf, df, today_partial=tp, dev_pct=dev_pct)
                if r:
                    rows.append(r)
                    stats["setups"] += 1
            except Exception as e:
                if len(stats["sample_errors"]) < 3:
                    stats["sample_errors"].append(f"{s}/{tf}: {str(e)[:120]}")
    return (pd.DataFrame(rows) if rows else pd.DataFrame()), stats


def backtest_us(symbols, cache, timeframes=("1D", "1W"), dev_pct=DEV_PCT_DEFAULT,
                window_days=365, sectors=None):
    """Completed historical trades from the cache, via the Pine-faithful engine."""
    all_trades = []
    for s in symbols:
        for tf in timeframes:
            try:
                df = us_get_tf(s, tf, cache)
                if df is None or len(df) < 30:
                    continue
                trades = pine_engine.backtest(df, dev_pct=dev_pct, window_days=window_days)
                for t in trades:
                    t["sym"] = s
                    t["tf"] = tf
                    if sectors:
                        t["sector"] = sectors.get(s, "-")
                all_trades.extend(trades)
            except Exception:
                continue
    return all_trades


# ============================================================================
# OUTPUT — US dashboard/performance writers (ET timestamps + in_band/approaching)
# ============================================================================
# Mirror the Indian engine's schema but (a) add the derived in_band/approaching
# flags and (b) stamp ET. Kept here so zigzag_kb_engine.save_* stays untouched.

def _clean(v):
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    return v


def save_dashboard_us(df, path="results_us.json", deviation=DEV_PCT_DEFAULT,
                      sectors=None, stats=None):
    rows = []
    if not df.empty:
        for _, r in df.iterrows():
            sym = r["sym"]
            rows.append({
                "sym": sym, "sector": (sectors.get(sym, "-") if sectors else "-"),
                "tf": r["tf"], "signal": r["signal"], "active_trade": r["active_trade"],
                "action": _clean(r.get("action")), "provisional": bool(r["provisional"]),
                "in_band": bool(r.get("in_band", False)),
                "approaching": bool(r.get("approaching", False)),
                "A": _clean(r["A"]), "B": _clean(r["B"]), "drop_pct": _clean(r["drop_pct"]),
                "ltp": _clean(r["ltp"]),
                "t1_entry_lo": _clean(r["t1_entry_lo"]), "t1_entry_hi": _clean(r["t1_entry_hi"]),
                "t1_tp_lo": _clean(r["t1_tp_lo"]), "t1_tp_hi": _clean(r["t1_tp_hi"]),
                "t1_sl": _clean(r["t1_sl"]),
                "t2_entry_lo": _clean(r["t2_entry_lo"]), "t2_entry_hi": _clean(r["t2_entry_hi"]),
                "t2_tp_lo": _clean(r["t2_tp_lo"]), "t2_tp_hi": _clean(r["t2_tp_hi"]),
                "t2_sl": _clean(r["t2_sl"]),
                "ema_ok": bool(r["ema_ok"]), "vol_ok": bool(r["vol_ok"]),
                "vol_x": _clean(r["vol_x"]), "rr": _clean(r["rr"]),
                "confirmed_at": _clean(r["confirmed_at"]),
                "macro_a": _clean(r["macro_a"]), "macro_b": _clean(r["macro_b"]),
            })

    if stats is None:
        data_status = "ok" if rows else "no_setups"
        stats_clean = None
    else:
        attempted = int(stats.get("attempted", 0))
        fetched_ok = int(stats.get("fetched_ok", 0))
        setups = int(stats.get("setups", len(rows)))
        if attempted == 0:
            data_status = "empty_universe"
        elif fetched_ok / max(attempted, 1) < 0.10:
            data_status = "no_data"
        elif setups == 0:
            data_status = "no_setups"
        else:
            data_status = "ok"
        stats_clean = {"attempted": attempted, "fetched_ok": fetched_ok,
                       "setups": setups, "sample_errors": list(stats.get("sample_errors", []))[:3]}

    now_et = pd.Timestamp.now(tz="America/New_York")
    data = {
        "generated_at": now_et.floor("s").isoformat(),
        "generated_label": now_et.strftime("%H:%M ET · %d %b"),
        "deviation": deviation, "data_status": data_status,
        "stats": stats_clean, "rows": rows,
    }
    with open(path, "w") as f:
        json.dump(data, f, indent=2, allow_nan=False)
    return path


def save_performance_us(trades, path="performance_us.json", window_days=365):
    aggs = _aggregate_performance(trades)
    now_et = pd.Timestamp.now(tz="America/New_York")
    data = {"generated_at": now_et.floor("s").isoformat(),
            "generated_label": now_et.strftime("%H:%M ET · %d %b"),
            "window_days": window_days, **aggs}
    with open(path, "w") as f:
        json.dump(data, f, indent=2, allow_nan=False)
    return path
