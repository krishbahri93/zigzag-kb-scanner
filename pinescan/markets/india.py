"""
India (NSE) market data — Nifty Total Market (750) universe + daily/intraday OHLCV.

Single source: the Dhan broker API. Equities (NSE_EQ) and the benchmark indices
(IDX_I, e.g. Nifty 50 / Sensex) both come from the one authenticated Dhan account,
so the whole India side uses ONE authenticated provider — no second EOD source.
  - daily history → _fetch_dhan_daily (equities) / fetch_index_daily (indices)
  - today's partial bar → _fetch_today_partial (appended to 1D when live)

Salvaged from the old Indian-strategy engine; all strategy/output logic was dropped —
this module is data-fetching only.

Env:
  DHAN_CLIENT_ID, DHAN_ACCESS_TOKEN   Dhan credentials (token refreshes daily)
  DHAN_SCRIP_URL    Dhan scrip master CSV (optional override)
  ZIGZAG_INTRADAY   "true"/"false" — append today's intraday partial bar to 1D
"""
import os
import datetime as dt

import pandas as pd

from .base import resample_weekly
from .. import io_safe

# ---- config ----
DHAN_SCRIP_URL = os.environ.get(
    "DHAN_SCRIP_URL", "https://images.dhan.co/api-data/api-scrip-master.csv"
)
ENABLE_INTRADAY = os.environ.get("ZIGZAG_INTRADAY", "true").lower() in ("1", "true", "yes")
INTRADAY_INTERVAL = 15  # minutes per intraday bar

# Daily-bar cache: ONE parquet per symbol (Dhan is fetched per-symbol, unlike the
# US grouped endpoint which caches one parquet per date). Module-level so tests can
# monkeypatch it to a tmp dir; data/ is git-ignored, created lazily on first backfill.
CACHE_DIR = "data/cache/india"

# Well-known Dhan INDEX security ids (exchange_segment "IDX_I", instrument "INDEX"). Indices
# aren't in the equity _secid map (_dhan_client filters to EQ/BE), so their ids are listed here
# for the backtest's benchmark — same authenticated provider as the stocks, no second source.
INDEX_IDS = {"Nifty 50": "13", "Sensex": "51"}


# ============================================================================
# UNIVERSE — NSE Nifty Total Market (~750: large + mid + small + microcaps,
# including recent IPOs like ENVIRO/EIEL that the old Nifty 500 list missed)
# ============================================================================

def load_total_market():
    """Fetch NSE's official Nifty Total Market list with sector labels.

    Returns (symbols_list, {symbol: sector_name}).
    Falls back to a 20-stock shortlist if NSE blocks the request.
    """
    import io
    import requests
    try:
        url = "https://archives.nseindia.com/content/indices/ind_niftytotalmarket_list.csv"
        txt = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=25).text
        d = pd.read_csv(io.StringIO(txt))
        sym = d["Symbol"].astype(str).str.strip()
        ind = d["Industry"].astype(str).str.strip()
        nm = (d["Company Name"].astype(str).str.strip()
              if "Company Name" in d.columns else sym)
        return sym.tolist(), dict(zip(sym, ind)), dict(zip(sym, nm))
    except Exception as e:
        print(f"Could not fetch the NSE Nifty Total Market list ({e}); using shortlist.")
        fb = ["RELIANCE", "TCS", "HDFCBANK", "ICICIBANK", "INFY", "SBIN", "BHARTIARTL",
              "ITC", "LT", "HINDUNILVR", "KOTAKBANK", "AXISBANK", "BAJFINANCE", "MARUTI",
              "SUNPHARMA", "TATAMOTORS", "TITAN", "ULTRACEMCO", "ASIANPAINT", "NESTLEIND"]
        return fb, {}, {}


# ============================================================================
# DATA FETCHERS — Dhan (daily history for equities + indices, live intraday)
# ============================================================================

# Dhan client cache (created once per session)
_dhan = None
_secid = {}
_creds_mtime = None          # mtime of the .dhan_creds we built _dhan from (token-rotation guard)

# The two creds Dhan needs: client id + a daily-refreshed access token.
_DHAN_CRED_KEYS = ("DHAN_CLIENT_ID", "DHAN_ACCESS_TOKEN")


def _creds_file():
    """Path of the .dhan_creds actually in use (cwd first, then ~), or None if neither exists."""
    for p in (".dhan_creds", os.path.expanduser("~/.dhan_creds")):
        if os.path.exists(p):
            return p
    return None


def _reload_token_if_changed():
    """Pick up a freshly-minted token in a LONG-LIVED process (the web app).

    Dhan tokens expire every 24h; the 08:30 mint rewrites .dhan_creds in a SEPARATE process, and
    ensure_dhan_creds() uses setdefault (env wins), so a long-running process would otherwise keep
    the stale token in os.environ + the cached _dhan client forever — a browser Refresh would then
    fetch nothing and silently serve stale data. Here we watch the file's mtime: when it changes,
    read the token straight from disk, overwrite os.environ, and drop the cached client so the next
    _dhan_client() rebuilds with the fresh token. Fresh oneshot jobs (the 15:55 close run) never hit
    this — they start with a clean env — so this only heals the long-lived path."""
    global _dhan, _creds_mtime
    p = _creds_file()
    if not p:
        return
    try:
        m = os.stat(p).st_mtime
    except OSError:
        return
    if _creds_mtime is not None and m <= _creds_mtime:
        return                                   # unchanged since we last built the client
    tok = None
    try:
        for line in open(p, encoding="utf-8"):
            line = line.strip()
            if line.startswith("DHAN_ACCESS_TOKEN="):
                tok = line.split("=", 1)[1].strip()
    except OSError:
        return
    if tok and tok != os.environ.get("DHAN_ACCESS_TOKEN"):
        os.environ["DHAN_ACCESS_TOKEN"] = tok    # authoritative: the file's token wins after a mint
        _dhan = None                             # force a rebuild with the fresh token
    _creds_mtime = m


def ensure_dhan_creds(path=None):
    """Make sure DHAN_CLIENT_ID + DHAN_ACCESS_TOKEN are in os.environ, loading them from a local,
    git-ignored `.dhan_creds` file (KEY=VALUE lines) if they aren't already set. Existing env values
    win (setdefault). Returns True if both creds are present afterwards, else False — the caller
    decides whether that's fatal (the scanner/backtest can still run on cached parquet with no token).

    This is the ONE place the `.dhan_creds` convention lives, so every entry point (live scanner,
    backfill, backtest matrix) loads creds the same way — _dhan_client() calls it lazily, so callers
    usually don't need to. `path` overrides the search (default: ./.dhan_creds, then ~/.dhan_creds).
    """
    if all(os.environ.get(k) for k in _DHAN_CRED_KEYS):
        return True
    for p in ([path] if path else [".dhan_creds", os.path.expanduser("~/.dhan_creds")]):
        if not p or not os.path.exists(p):
            continue
        for line in open(p, encoding="utf-8"):
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())     # env wins over the file
        print(f"  loaded Dhan creds from {p}")
        break
    return all(os.environ.get(k) for k in _DHAN_CRED_KEYS)


def _dhan_client():
    """Create Dhan client (v2.1+ with fallback) and load NSE-equity ID map.

    Auto-loads creds from `.dhan_creds` via ensure_dhan_creds() so any entry point works without
    wiring creds itself; raises KeyError if no creds are available anywhere (env or file).
    """
    global _dhan, _secid
    _reload_token_if_changed()                  # heal a stale token before reusing the cached client
    if _dhan is None:
        ensure_dhan_creds()                     # pull creds from .dhan_creds if not already in env
        cid = os.environ["DHAN_CLIENT_ID"]
        tok = os.environ["DHAN_ACCESS_TOKEN"]
        try:
            from dhanhq import DhanContext, dhanhq
            _dhan = dhanhq(DhanContext(cid, tok))
        except Exception:
            from dhanhq import dhanhq
            _dhan = dhanhq(cid, tok)
    if not _secid:                              # the scrip master rarely changes — don't re-download
        df = pd.read_csv(DHAN_SCRIP_URL, low_memory=False)  # it on a mere token rotation
        if "SEM_EXM_EXCH_ID" in df.columns:
            df = df[df["SEM_EXM_EXCH_ID"].astype(str).str.upper() == "NSE"]
        if "SEM_SERIES" in df.columns:
            df = df[df["SEM_SERIES"].astype(str).str.upper().isin(["EQ", "BE"])]
        elif "SEM_INSTRUMENT_NAME" in df.columns:
            df = df[df["SEM_INSTRUMENT_NAME"].astype(str).str.upper().str.contains("EQUITY", na=False)]
        for _, r in df.iterrows():
            _secid[str(r["SEM_TRADING_SYMBOL"]).strip().upper()] = \
                str(r["SEM_SMST_SECURITY_ID"]).split(".")[0].strip()
    return _dhan


# Why the last fetch returned no frame — set by _dhan_daily_ohlcv/_fetch_dhan_daily on EVERY
# call so refresh_recent can tell a rate-limited symbol from a genuinely empty one (Dhan
# started enforcing DH-904 rate limits ~2026-07-24; before this, both read as "no data").
#   None = data returned · "rate_limited" (DH-904 survived retries) · "empty" (success, no
#   rows) · "unmapped" (symbol absent from the scrip master) · "error:<code>" (other failure)
LAST_FETCH_ERROR = None

# Base spacing between history calls. 0.15s (~6.7 req/s) worked until Dhan's 2026-07-24
# enforcement change began rejecting the tail of every 752-symbol sweep; 0.35s stays under
# the observed limit with headroom, and the DH-904 backoff below catches transient buckets.
_THROTTLE_S = 0.35


def _classify_remarks(r):
    """Map a Dhan response dict to LAST_FETCH_ERROR vocabulary (pure; unit-tested).
    Returns None when the response carries data, else the failure class."""
    d = r.get("data") if isinstance(r, dict) else None
    if d and "close" in d and d["close"]:
        return None
    rem = r.get("remarks") if isinstance(r, dict) else None
    code = (rem or {}).get("error_code") if isinstance(rem, dict) else None
    if code == "DH-904":
        return "rate_limited"
    if code:
        return f"error:{code}"
    return "empty"


def _dhan_daily_ohlcv(security_id, exchange_segment, instrument_type, days):
    """Core Dhan daily-history fetch — the single place that calls Dhan's daily endpoint.

    Equities and indices differ ONLY in their (exchange_segment, instrument_type) pair and id,
    so both public fetchers below funnel through here instead of repeating the request + parse.
    Pulls `days` of history and returns an OHLCV DataFrame indexed by Asia/Kolkata datetime
    (Volume is 0 when Dhan reports none, e.g. for indices), or None if Dhan returns no data —
    in which case module-global LAST_FETCH_ERROR says WHY (see its comment above).

    Rate limits: throttles _THROTTLE_S per call, and a DH-904 rejection is retried twice with
    growing pauses (2s, 8s) before giving up — Dhan's limiter refills within seconds, so the
    sweep's tail survives instead of silently losing ~125 symbols (the 2026-07-28 diagnosis).
    """
    import time
    global LAST_FETCH_ERROR
    dh = _dhan_client()
    to_d = dt.date.today()
    from_d = to_d - dt.timedelta(days=days)
    r, why = None, "empty"
    for pause in (_THROTTLE_S, 2.0, 8.0):       # first try + two rate-limit retries
        time.sleep(pause)
        r = dh.historical_daily_data(
            security_id=str(security_id), exchange_segment=exchange_segment,
            instrument_type=instrument_type, expiry_code=0,
            from_date=str(from_d), to_date=str(to_d),
        )
        why = _classify_remarks(r)
        if why != "rate_limited":
            break
    LAST_FETCH_ERROR = why
    if why is not None:
        return None
    d = r["data"]
    out = pd.DataFrame({
        "Open": d["open"], "High": d["high"], "Low": d["low"],
        "Close": d["close"], "Volume": d.get("volume", [0] * len(d["close"])),
    })
    ts = d.get("timestamp") or d.get("start_Time") or d.get("time")
    if ts is not None:
        out.index = pd.to_datetime(pd.Series(ts), unit="s", errors="coerce")
        try:
            out.index = out.index.tz_localize("UTC").tz_convert("Asia/Kolkata")
        except Exception:
            pass
    return out.dropna()


def _fetch_dhan_daily(symbol, days=1100):
    """Dhan daily OHLCV for one NSE equity (NSE_EQ / EQUITY). Resolves the trading symbol to its
    Dhan security id via _secid, then delegates the actual fetch to _dhan_daily_ohlcv. Returns a
    DataFrame indexed by Asia/Kolkata datetime, or None if the symbol isn't in Dhan's equity map
    (LAST_FETCH_ERROR = "unmapped") or Dhan returned nothing (see LAST_FETCH_ERROR)."""
    global LAST_FETCH_ERROR
    _dhan_client()                          # ensure the client + _secid map are loaded BEFORE the lookup
    sid = _secid.get(symbol.upper())
    if not sid:
        LAST_FETCH_ERROR = "unmapped"
        return None
    return _dhan_daily_ohlcv(sid, "NSE_EQ", "EQUITY", days)


def fetch_index_daily(security_id, days=1825):
    """Daily OHLCV for an INDEX via Dhan's IDX_I segment (e.g. Nifty 50 = '13', Sensex = '51';
    see INDEX_IDS). Indices live in a different segment and aren't in the equity _secid map, so the
    caller passes the Dhan id directly. Same _dhan_daily_ohlcv core as the equity fetch — only the
    segment/instrument differ. Used for the backtest benchmark so the index comes from the SAME
    provider as the stocks (no second data source)."""
    return _dhan_daily_ohlcv(str(security_id), "IDX_I", "INDEX", days)


def _fetch_today_partial(symbol):
    """Fetch today's intraday bars from Dhan and aggregate into a single
    "today's partial daily bar" with combined OHLCV. Returns a 1-row DataFrame
    indexed by today's date in Asia/Kolkata, or None if no intraday data is
    available (pre-market, weekend, holiday, error)."""
    today = dt.date.today()
    if today.weekday() >= 5:
        return None

    import time
    try:
        dh = _dhan_client()
    except Exception:
        return None

    sid = _secid.get(symbol.upper())
    if not sid:
        return None

    time.sleep(0.15)  # throttle

    r = None
    try:
        if hasattr(dh, 'intraday_minute_data'):
            r = dh.intraday_minute_data(
                security_id=sid, exchange_segment="NSE_EQ", instrument_type="EQUITY",
                from_date=str(today), to_date=str(today), interval=INTRADAY_INTERVAL,
            )
        elif hasattr(dh, 'historical_minute_data'):
            r = dh.historical_minute_data(
                security_id=sid, exchange_segment="NSE_EQ", instrument_type="EQUITY",
                from_date=str(today), to_date=str(today), interval=INTRADAY_INTERVAL,
            )
    except Exception:
        return None

    if not r:
        return None
    d = r.get("data") if isinstance(r, dict) else None
    if not d:
        return None
    closes = d.get("close")
    if not closes or len(closes) == 0:
        return None

    try:
        today_open = float(d["open"][0])
        today_high = float(max(d["high"]))
        today_low = float(min(d["low"]))
        today_close = float(d["close"][-1])  # last intraday close ~ current LTP
        today_volume = float(sum(d.get("volume", [0] * len(closes))))
    except (KeyError, IndexError, TypeError, ValueError):
        return None

    try:
        ts = pd.Timestamp(today).tz_localize("Asia/Kolkata")
    except Exception:
        ts = pd.Timestamp(today)

    return pd.DataFrame({
        "Open": [today_open], "High": [today_high], "Low": [today_low],
        "Close": [today_close], "Volume": [today_volume],
    }, index=[ts])


def get_tf(symbol, tf):
    """Fetch OHLCV for one symbol at one timeframe ('1D'/'1W') from Dhan. Returns DataFrame or None.

    For 1D with intraday enabled (ZIGZAG_INTRADAY), appends today's intraday-aggregated partial
    bar so the engine sees live price action before Dhan's daily endpoint posts the official bar.
    """
    if tf == "1D":
        df = _fetch_dhan_daily(symbol, days=1100)
        if df is None or len(df) == 0:
            return df
        if not ENABLE_INTRADAY:
            return df
        today = dt.date.today()
        try:
            last_date = df.index[-1].date()
        except Exception:
            last_date = None
        if last_date is not None and last_date >= today:
            return df
        if today.weekday() >= 5:
            return df
        partial = _fetch_today_partial(symbol)
        if partial is not None and len(partial) > 0:
            df = pd.concat([df, partial])
        return df
    if tf == "1W":
        return resample_weekly(_fetch_dhan_daily(symbol, days=1800))
    raise ValueError(f"Unsupported tf: {tf}")


# ============================================================================
# Interface the scanner / backtester depend on (see markets/base.py)
# ============================================================================

_UNIVERSE_CACHE_FILE = "data/cache/india_universe.json"


def get_universe(max_age_days=7):
    """(symbols, {symbol: sector}) for the NSE Nifty Total Market (~750) — disk-cached for
    max_age_days. NSE archives is slow and sometimes blocks cloud IPs, so scans must never
    depend on it being reachable; the constituent list barely changes week to week."""
    import json
    import time
    try:
        if (time.time() - os.stat(_UNIVERSE_CACHE_FILE).st_mtime) < max_age_days * 86400:
            d = json.loads(open(_UNIVERSE_CACHE_FILE, encoding="utf-8").read())
            if d.get("symbols"):
                return d["symbols"], d.get("sectors", {})
    except Exception:
        pass
    syms, sectors, names = load_total_market()
    if sectors:                                   # never cache the 20-stock fallback
        try:
            os.makedirs(os.path.dirname(_UNIVERSE_CACHE_FILE), exist_ok=True)
            io_safe.atomic_write_text(_UNIVERSE_CACHE_FILE,
                                      json.dumps({"symbols": syms, "sectors": sectors,
                                                  "names": names}))
        except Exception:
            pass
    return syms, sectors


def get_names():
    """{symbol: company name} from the cached universe file ({} until the cache next
    refreshes with names). Display-only — callers must tolerate missing entries."""
    import json
    try:
        d = json.loads(open(_UNIVERSE_CACHE_FILE, encoding="utf-8").read())
        return d.get("names", {}) or {}
    except Exception:
        return {}


def get_daily(symbol):
    """Daily OHLCV for one NSE symbol (Dhan)."""
    return get_tf(symbol, "1D")


def get_intraday(symbol):
    """Today's intraday-aggregated partial bar (Dhan only; None otherwise)."""
    return _fetch_today_partial(symbol)


# ============================================================================
# DAILY CACHE — one parquet PER SYMBOL, resumable (mirrors markets/us.py)
# ============================================================================
# Dhan's historical endpoint is per-symbol, so — unlike the US grouped cache
# (one parquet per date) — we write one parquet per symbol. Backfill is
# resumable: a symbol whose parquet already exists is skipped, so an interrupted
# run continues where it left off. Throttling lives inside _fetch_dhan_daily.
#
# To extend: keep the per-symbol file layout (CACHE_DIR/{symbol}.parquet) so the
# skip-if-exists resume logic and load_cache stay in sync; bump `years` for more
# history. scripts/backfill_india.py drives this with real Dhan creds.

def backfill(symbols, years=5, progress_every=25):
    """Fetch `years` of daily OHLCV for each symbol and write one parquet per
    symbol under CACHE_DIR. Resumable: symbols whose parquet already exists are
    skipped (so re-running only fills the gaps). Symbols Dhan returns nothing for
    (None/empty) are left uncached and simply retried on the next run.

    Per-symbol (one Dhan call each) — contrast markets/us.py.backfill, which is
    per-date because Polygon's grouped endpoint returns all tickers at once. The
    inter-call throttle already lives in _fetch_dhan_daily, so we don't sleep here.
    """
    os.makedirs(CACHE_DIR, exist_ok=True)   # data/ is gitignored: create on first run
    total = len(symbols)
    done = fetched = 0
    print(f"  backfill: {total} symbols, ~{years}y daily each (resumable) …")
    for sym in symbols:
        done += 1
        fp = os.path.join(CACHE_DIR, f"{sym}.parquet")
        if not os.path.exists(fp):                       # resume: skip cached symbols
            df = _fetch_dhan_daily(sym, days=years * 365)
            if df is not None and len(df) > 0:
                io_safe.atomic_to_parquet(df, fp)        # index = Asia/Kolkata dates; crash-safe
                fetched += 1
        if done % progress_every == 0 or done == total:
            print(f"    backfill {done}/{total} ({fetched} fetched this run) … {sym}")
    print(f"  backfill complete: {total} symbols scanned, {fetched} fetched this run")


def refresh_recent(symbols, days=15, progress_every=50):
    """Append each symbol's LATEST daily bars to its cached parquet — UNLIKE backfill, which skips
    any symbol that's already cached and so never picks up today's bar.

    For each symbol: fetch the last `days` of daily history via _fetch_dhan_daily, concat with the
    existing parquet, dedupe by date (keep last, so a restated bar is corrected) + sort, and rewrite.
    This is the daily-refresh path the forward-tester uses to pull today's FINAL daily bar. One Dhan
    call per symbol (throttled + DH-904-retried inside _dhan_daily_ohlcv); symbols Dhan returns
    nothing for are left untouched. Mirrors the per-symbol cache layout backfill/load_cache use.

    Failures are CLASSIFIED (via LAST_FETCH_ERROR), not lumped: rate-limited symbols get one
    extra sweep at the end (the limiter has refilled by then), and the summary prints distinct
    counts so the job log can tell "Dhan throttled us" from "Dhan has no bar yet" — the
    2026-07-24..28 incident hid as ~125 'no data' symbols for four days because it couldn't.

    Returns a summary dict: {total, updated, latest_bar, on_latest, rate_limited, unmapped,
    empty} — callers use latest_bar/on_latest to decide whether today's bar has landed
    (the close-run publish-wait and the morning self-heal, see service/forward_run).
    """
    os.makedirs(CACHE_DIR, exist_ok=True)
    total = len(symbols)
    print(f"  refresh_recent: {total} symbols, last ~{days}d each …")

    updated, last_bar = {}, {}                   # sym -> True / sym -> last cached date
    failed = {"rate_limited": [], "unmapped": [], "empty": []}

    def _one(sym):
        recent = _fetch_dhan_daily(sym, days=days)
        if recent is None or len(recent) == 0:
            failed[LAST_FETCH_ERROR if LAST_FETCH_ERROR in failed else "empty"].append(sym)
            return
        fp = os.path.join(CACHE_DIR, f"{sym}.parquet")
        old = io_safe.read_parquet_safe(fp)          # None if absent OR corrupt -> treat as fresh
        if old is not None:
            merged = pd.concat([old, recent])
            merged = merged[~merged.index.duplicated(keep="last")].sort_index()
        else:
            merged = recent
        io_safe.atomic_to_parquet(merged, fp)        # crash-safe
        updated[sym] = True
        last_bar[sym] = str(merged.index.max().date())

    for done, sym in enumerate(symbols, 1):
        _one(sym)
        if done % progress_every == 0 or done == total:
            print(f"    refresh {done}/{total} ({len(updated)} updated) … {sym}")

    # Second chance for the rate-limited tail: by the time the sweep ends the limiter has
    # refilled, so one more paced pass usually clears every straggler.
    retry = list(failed["rate_limited"])
    if retry:
        print(f"  refresh_recent: retrying {len(retry)} rate-limited symbols …")
        failed["rate_limited"] = []
        for sym in retry:
            _one(sym)

    latest = max(last_bar.values()) if last_bar else None
    on_latest = sum(1 for v in last_bar.values() if v == latest) if latest else 0
    print(f"  refresh_recent complete: {len(updated)}/{total} symbols updated"
          + (f", newest bar {latest} on {on_latest} of them" if latest else ""))
    for kind, syms in failed.items():
        if syms:
            head = ", ".join(syms[:10])
            more = f" … +{len(syms) - 10} more" if len(syms) > 10 else ""
            print(f"  refresh_recent: {len(syms)} {kind.replace('_', '-')}: {head}{more}")
    return {"total": total, "updated": len(updated), "latest_bar": latest,
            "on_latest": on_latest, "rate_limited": len(failed["rate_limited"]),
            "unmapped": len(failed["unmapped"]), "empty": len(failed["empty"])}


def load_cache(symbols):
    """Read the cached per-symbol parquet files → {symbol: daily DataFrame}.

    Symbols with no parquet yet are silently skipped, so callers get only what's
    actually been backfilled. Each frame round-trips exactly what backfill wrote
    (OHLCV columns, Asia/Kolkata DatetimeIndex).
    """
    cache = {}
    for sym in symbols:
        fp = os.path.join(CACHE_DIR, f"{sym}.parquet")
        df = io_safe.read_parquet_safe(fp)
        if df is None:                      # absent or corrupt; drop a corrupt file so refresh refetches
            if os.path.exists(fp):
                try:
                    os.remove(fp)
                except OSError:
                    pass
            continue
        cache[sym] = df
    return cache
