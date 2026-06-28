"""
India (NSE) market data — Nifty 500 universe + daily/intraday OHLCV.

Two sources, chosen by env var `KWM_DATA_SOURCE`:
  - "yahoo" (default): yfinance EOD — fine for daily history / backtesting.
  - "dhan": Dhan broker API — daily + today's intraday partial bar (live use).

Salvaged verbatim from the old Indian-strategy engine; all strategy/output logic
was dropped — this module is data-fetching only.

Env:
  KWM_DATA_SOURCE   "yahoo" (default) | "dhan"
  DHAN_CLIENT_ID, DHAN_ACCESS_TOKEN   Dhan credentials (token refreshes daily)
  DHAN_SCRIP_URL    Dhan scrip master CSV (optional override)
  ZIGZAG_INTRADAY   "true"/"false" — append today's intraday partial bar (Dhan only)
"""
import os
import datetime as dt

import pandas as pd

from .base import resample_weekly

# ---- config ----
DATA_SOURCE = os.environ.get("KWM_DATA_SOURCE", "yahoo").lower()
DHAN_SCRIP_URL = os.environ.get(
    "DHAN_SCRIP_URL", "https://images.dhan.co/api-data/api-scrip-master.csv"
)
ENABLE_INTRADAY = os.environ.get("ZIGZAG_INTRADAY", "true").lower() in ("1", "true", "yes")
INTRADAY_INTERVAL = 15  # minutes per intraday bar


# ============================================================================
# UNIVERSE — NSE Nifty 500
# ============================================================================

def load_nifty500():
    """Fetch NSE's official Nifty 500 list with sector labels.

    Returns (symbols_list, {symbol: sector_name}).
    Falls back to a 20-stock shortlist if NSE blocks the request.
    """
    import io
    import requests
    try:
        url = "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
        txt = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=25).text
        d = pd.read_csv(io.StringIO(txt))
        sym = d["Symbol"].astype(str).str.strip()
        ind = d["Industry"].astype(str).str.strip()
        return sym.tolist(), dict(zip(sym, ind))
    except Exception as e:
        print(f"Could not fetch NSE Nifty 500 list ({e}); using shortlist.")
        fb = ["RELIANCE", "TCS", "HDFCBANK", "ICICIBANK", "INFY", "SBIN", "BHARTIARTL",
              "ITC", "LT", "HINDUNILVR", "KOTAKBANK", "AXISBANK", "BAJFINANCE", "MARUTI",
              "SUNPHARMA", "TATAMOTORS", "TITAN", "ULTRACEMCO", "ASIANPAINT", "NESTLEIND"]
        return fb, {}


# ============================================================================
# DATA FETCHERS — Yahoo (default) and Dhan (real-time)
# ============================================================================

def _fetch_yahoo(symbol, interval, period):
    """OHLCV via yfinance for NSE symbols. Symbol like 'RELIANCE' (no .NS)."""
    import yfinance as yf
    df = yf.download(symbol + ".NS", interval=interval, period=period,
                     progress=False, auto_adjust=False)
    if df is None or len(df) == 0:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()
    if df.index.tz is not None:
        df.index = df.index.tz_convert("Asia/Kolkata")
    return df


# Dhan client cache (created once per session)
_dhan = None
_secid = {}


def _dhan_client():
    """Create Dhan client (v2.1+ with fallback) and load NSE-equity ID map."""
    global _dhan, _secid
    if _dhan is None:
        cid = os.environ["DHAN_CLIENT_ID"]
        tok = os.environ["DHAN_ACCESS_TOKEN"]
        try:
            from dhanhq import DhanContext, dhanhq
            _dhan = dhanhq(DhanContext(cid, tok))
        except Exception:
            from dhanhq import dhanhq
            _dhan = dhanhq(cid, tok)
        df = pd.read_csv(DHAN_SCRIP_URL, low_memory=False)
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


def _fetch_dhan_daily(symbol, days=1100):
    """Dhan daily OHLCV. Returns DataFrame indexed by Asia/Kolkata datetime."""
    import time
    dh = _dhan_client()
    sid = _secid.get(symbol.upper())
    if not sid:
        return None
    time.sleep(0.15)  # gentle throttle for big scans
    to_d = dt.date.today()
    from_d = to_d - dt.timedelta(days=days)
    r = dh.historical_daily_data(
        security_id=sid, exchange_segment="NSE_EQ",
        instrument_type="EQUITY", expiry_code=0,
        from_date=str(from_d), to_date=str(to_d)
    )
    d = r.get("data") if isinstance(r, dict) else None
    if not d or "close" not in d:
        return None
    out = pd.DataFrame({
        "Open": d["open"], "High": d["high"], "Low": d["low"],
        "Close": d["close"], "Volume": d.get("volume", [0] * len(d["close"]))
    })
    ts = d.get("timestamp") or d.get("start_Time") or d.get("time")
    if ts is not None:
        idx = pd.to_datetime(pd.Series(ts), unit="s", errors="coerce")
        out.index = idx
        try:
            out.index = out.index.tz_localize("UTC").tz_convert("Asia/Kolkata")
        except Exception:
            pass
    return out.dropna()


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
    """Fetch OHLCV for one symbol at one timeframe ('1D'/'1W'). Returns DataFrame or None.

    For 1D + Dhan with intraday enabled, appends today's intraday-aggregated partial
    bar so the engine sees live price action before Dhan's daily endpoint updates.
    """
    src = os.environ.get("KWM_DATA_SOURCE", DATA_SOURCE).lower()
    if src == "dhan":
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
    # Yahoo (default) — no intraday integration; yfinance intraday is unreliable
    if tf == "1D":
        return _fetch_yahoo(symbol, "1d", "3y")
    if tf == "1W":
        return _fetch_yahoo(symbol, "1wk", "5y")
    raise ValueError(f"Unsupported tf: {tf}")


# ============================================================================
# Interface the scanner / backtester depend on (see markets/base.py)
# ============================================================================

def get_universe():
    """(symbols, {symbol: sector}) for the NSE Nifty 500."""
    return load_nifty500()


def get_daily(symbol):
    """Daily OHLCV for one NSE symbol (source per KWM_DATA_SOURCE)."""
    return get_tf(symbol, "1D")


def get_intraday(symbol):
    """Today's intraday-aggregated partial bar (Dhan only; None otherwise)."""
    return _fetch_today_partial(symbol)
