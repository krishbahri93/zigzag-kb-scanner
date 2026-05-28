"""
KWM Auto Screener — scanning engine
Ports the dominant-swing / golden-zone logic from the Pine indicator to Python.
Free data via yfinance (lazy-imported). Designed to run in Google Colab.
"""
import os
import numpy as np
import pandas as pd

# ───────────────────────── Config ──────────────────────────
GOLDEN = (0.618, 0.68)          # entry pocket edges (KB's golden zone)
VOL_AVG = 20                    # bars for average-volume baseline
VOL_SPIKE = 1.8                 # ×avg that counts as a spike
PROX = 0.03                     # within 3% below the pocket = "Approaching"

# pivot strength (left/right bars) and dominant-swing lookback, per timeframe
PIV   = {"15m":5, "1H":8, "75m":5, "4H":6, "1D":10, "1W":6}
LOOK  = {"15m":120,"1H":160,"75m":120,"4H":120,"1D":450,"1W":160}
TF_MIN = {"15m":15,"1H":60,"75m":75,"4H":240,"1D":375,"1W":1875}  # minutes per bar (D/W approx session)

# yfinance (interval, period) for natively-supported TFs; 75m & 4H are resampled
YF_NATIVE = {"15m":("15m","60d"), "1H":("60m","730d"), "1D":("1d","3y"), "1W":("1wk","5y")}

# Data source: "yahoo" (free, ~15-min delayed) or "dhan" (paid real-time). Set via env.
DATA_SOURCE = os.environ.get("KWM_DATA_SOURCE", "yahoo").lower()
DHAN_SCRIP_URL = os.environ.get("DHAN_SCRIP_URL", "https://images.dhan.co/api-data/api-scrip-master.csv")


def load_nifty500():
    """Fetch NSE's official Nifty 500 list -> (symbols, {symbol: sector}). Falls back to a shortlist."""
    import io
    try:
        import requests
        url = "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
        txt = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=25).text
        d = pd.read_csv(io.StringIO(txt))
        sym = d["Symbol"].astype(str).str.strip()
        ind = d["Industry"].astype(str).str.strip()
        return sym.tolist(), dict(zip(sym, ind))
    except Exception as e:
        print("Could not fetch the NSE Nifty 500 list (", e, "); using a built-in shortlist instead.")
        fb = ["RELIANCE","TCS","HDFCBANK","ICICIBANK","INFY","SBIN","BHARTIARTL","ITC","LT","HINDUNILVR",
              "KOTAKBANK","AXISBANK","BAJFINANCE","MARUTI","SUNPHARMA","TATAMOTORS","TITAN","ULTRACEMCO","ASIANPAINT","NESTLEIND"]
        return fb, {}


# ───────────────────────── Data fetch / resample ──────────────────────────
def fetch(symbol, interval, period):
    """Download OHLCV for one NSE symbol via yfinance. symbol like 'RELIANCE'."""
    import yfinance as yf  # lazy: only needed when actually fetching
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


def _bucket_resample(df, n):
    """Group every n intraday bars within each trading day into one bar."""
    if df is None or len(df) == 0:
        return None
    d = df.copy()
    d["__day"] = pd.Series(d.index.date, index=d.index)
    out = []
    for _, g in d.groupby("__day"):
        g = g.sort_index().reset_index()
        tcol = g.columns[0]                      # original datetime column
        g["__b"] = g.index // n
        agg = g.groupby("__b").agg(
            Open=("Open", "first"), High=("High", "max"), Low=("Low", "min"),
            Close=("Close", "last"), Volume=("Volume", "sum"), t=(tcol, "first"))
        out.append(agg.set_index("t"))
    return pd.concat(out).sort_index() if out else None


# ───────────────────────── Dhan live data (READ-ONLY) ──────────────────────────
# This adapter ONLY reads candles. It never imports or calls any order function.
_dhan = None
_secid = {}

def _dhan_client():
    """Create the Dhan client (v2.1 DhanContext, with fallback) and load the NSE-equity map. Creds from env."""
    global _dhan, _secid
    if _dhan is None:
        cid = os.environ["DHAN_CLIENT_ID"]
        tok = os.environ["DHAN_ACCESS_TOKEN"]
        try:
            from dhanhq import DhanContext, dhanhq          # v2.1+
            _dhan = dhanhq(DhanContext(cid, tok))
        except Exception:
            from dhanhq import dhanhq                       # older versions
            _dhan = dhanhq(cid, tok)
        df = pd.read_csv(DHAN_SCRIP_URL, low_memory=False)
        if "SEM_EXM_EXCH_ID" in df.columns:
            df = df[df["SEM_EXM_EXCH_ID"].astype(str).str.upper() == "NSE"]
        if "SEM_SERIES" in df.columns:
            df = df[df["SEM_SERIES"].astype(str).str.upper().isin(["EQ", "BE"])]
        elif "SEM_INSTRUMENT_NAME" in df.columns:
            df = df[df["SEM_INSTRUMENT_NAME"].astype(str).str.upper().str.contains("EQUITY", na=False)]
        for _, r in df.iterrows():
            _secid[str(r["SEM_TRADING_SYMBOL"]).strip().upper()] = str(r["SEM_SMST_SECURITY_ID"]).split(".")[0].strip()
    return _dhan

def _dhan_candles(symbol, interval, days):
    import datetime as dt, time
    if interval != "1D":
        days = min(days, 88)            # Dhan intraday allows ~90 days per request
    dh = _dhan_client()
    sid = _secid.get(symbol.upper())
    if not sid:
        return None
    time.sleep(0.15)                    # gentle throttle so big scans don't hit rate limits
    to_d = dt.date.today()
    from_d = to_d - dt.timedelta(days=days)
    if interval == "1D":
        r = dh.historical_daily_data(security_id=sid, exchange_segment="NSE_EQ",
                                     instrument_type="EQUITY", expiry_code=0,
                                     from_date=str(from_d), to_date=str(to_d))
    else:
        r = dh.intraday_minute_data(security_id=sid, exchange_segment="NSE_EQ",
                                    instrument_type="EQUITY", interval=interval,
                                    from_date=str(from_d), to_date=str(to_d))
    d = r.get("data") if isinstance(r, dict) else None
    if not d or "close" not in d:
        return None
    ts = d.get("timestamp") or d.get("start_Time") or d.get("time")
    out = pd.DataFrame({"Open": d["open"], "High": d["high"], "Low": d["low"],
                        "Close": d["close"], "Volume": d.get("volume", [0]*len(d["close"]))})
    if ts is not None:
        idx = pd.to_datetime(pd.Series(ts), unit="s", errors="coerce")
        out.index = idx
        try:
            out.index = out.index.tz_localize("UTC").tz_convert("Asia/Kolkata")
        except Exception:
            pass
    return out.dropna()

def _to_weekly(d):
    if d is None or len(d) == 0:
        return None
    return d.resample("W-FRI").agg({"Open":"first","High":"max","Low":"min",
                                    "Close":"last","Volume":"sum"}).dropna()


def get_tf(symbol, tf):
    """Return an OHLCV DataFrame for symbol at the requested timeframe."""
    src = os.environ.get("KWM_DATA_SOURCE", DATA_SOURCE).lower()
    if src == "dhan":
        if tf == "15m": return _dhan_candles(symbol, "15", 60)
        if tf == "1H":  return _dhan_candles(symbol, "60", 120)
        if tf == "75m": return _bucket_resample(_dhan_candles(symbol, "15", 60), 5)
        if tf == "4H":  return _bucket_resample(_dhan_candles(symbol, "60", 120), 4)
        if tf == "1D":  return _dhan_candles(symbol, "1D", 1100)
        if tf == "1W":  return _to_weekly(_dhan_candles(symbol, "1D", 1800))
        raise ValueError(tf)
    # ---- Yahoo (default, free) ----
    if tf in YF_NATIVE:
        iv, pr = YF_NATIVE[tf]
        return fetch(symbol, iv, pr)
    if tf == "75m":
        return _bucket_resample(fetch(symbol, "15m", "60d"), 5)
    if tf == "4H":
        return _bucket_resample(fetch(symbol, "60m", "730d"), 4)
    raise ValueError(tf)


# ───────────────────────── Core analytics ──────────────────────────
def find_pivots(arr, left, right):
    """Indices of confirmed pivot highs and lows (need `right` bars to the right)."""
    n = len(arr)
    highs, lows = [], []
    for i in range(left, n - right):
        c = arr[i]
        win_l = arr[i - left:i]
        win_r = arr[i + 1:i + right + 1]
        if c > win_l.max() and c >= win_r.max():
            highs.append(i)
        if c < win_l.min() and c <= win_r.min():
            lows.append(i)
    return highs, lows


def analyze(df, tf, src="close"):
    """Run the dominant-swing / golden-zone logic on one OHLCV frame."""
    need = max(PIV[tf] * 2 + 5, VOL_AVG + 2)
    if df is None or len(df) < need:
        return None

    high = df["High"].to_numpy(float)
    low  = df["Low"].to_numpy(float)
    close = df["Close"].to_numpy(float)
    vol  = df["Volume"].to_numpy(float)
    n = len(close)
    piv = PIV[tf]

    sh = (close if src == "close" else high)
    sl = (close if src == "close" else low)
    ph_all, _ = find_pivots(sh, piv, piv)
    _, pl_all = find_pivots(sl, piv, piv)
    if not ph_all or not pl_all:
        return None

    # dominant swing within the lookback window
    lb = LOOK[tf]
    ph = [i for i in ph_all if n - i <= lb] or ph_all
    pl = [i for i in pl_all if n - i <= lb] or pl_all
    hi_i = max(ph, key=lambda i: sh[i]);  hi_p = sh[hi_i]
    lo_i = min(pl, key=lambda i: sl[i]);  lo_p = sl[lo_i]
    if hi_p <= lo_p:
        return None

    is_up = hi_i >= lo_i               # more recent extreme sets trend
    rng = hi_p - lo_p

    def level(r):                      # price at a fib ratio (same formula as Pine)
        return hi_p - rng * r if is_up else lo_p + rng * r

    g_a, g_b = level(GOLDEN[0]), level(GOLDEN[1])
    z_lo, z_hi = min(g_a, g_b), max(g_a, g_b)     # entry pocket band

    last = close[-1]
    if last > z_hi:
        signal = "Triggered"
    elif z_lo <= last <= z_hi:
        signal = "In Zone"
    elif last < z_lo and last >= z_lo * (1 - PROX):
        signal = "Approaching"
    else:
        return None                    # outside our interest band

    # volume spike
    base = vol[-VOL_AVG - 1:-1]
    volx = round(float(vol[-1] / base.mean()), 1) if base.mean() > 0 else 0.0

    # since-trigger %, and how many bars ago it confirmed
    since = None
    conf_bars = 0
    if signal == "Triggered":
        cross = None
        for k in range(n - 1, max(n - lb, 0) - 1, -1):
            if close[k] > z_hi and (k == 0 or close[k - 1] <= z_hi):
                cross = k
                break
        if cross is not None:
            since = round((last / close[cross] - 1) * 100, 2)
            conf_bars = n - 1 - cross

    # target = touch of the upper (reversed) pocket — first contact counts
    t_a = (lo_p + rng * GOLDEN[0]) if is_up else (hi_p - rng * GOLDEN[0])
    t_b = (lo_p + rng * GOLDEN[1]) if is_up else (hi_p - rng * GOLDEN[1])
    tgt_near = min(t_a, t_b) if last < min(t_a, t_b) else max(t_a, t_b)

    return dict(
        tf=tf, trend=("up" if is_up else "down"), signal=signal,
        zlow=round(z_lo, 2), zhigh=round(z_hi, 2), ltp=round(last, 2),
        since=since, volx=volx, spike=volx >= VOL_SPIKE,
        conf_min=conf_bars * TF_MIN[tf], target=round(tgt_near, 2),
    )


# ───────────────────────── Scan + export ──────────────────────────
def scan(symbols, timeframes, src="close", verbose=True):
    rows = []
    for s in symbols:
        for tf in timeframes:
            try:
                r = analyze(get_tf(s, tf), tf, src)
                if r:
                    r["symbol"] = s
                    rows.append(r)
            except Exception as e:
                if verbose:
                    print("skip", s, tf, "—", e)
    cols = ["symbol", "tf", "trend", "signal", "zlow", "zhigh", "ltp",
            "since", "volx", "spike", "conf_min", "target"]
    return pd.DataFrame(rows, columns=cols)


def tradingview_string(df, sectioned=True):
    """Build a TradingView import string: NSE: comma list, optional ### TF sections."""
    if df.empty:
        return ""
    if not sectioned or df["tf"].nunique() == 1:
        return ",".join("NSE:" + s for s in dict.fromkeys(df["symbol"]))
    parts = []
    for tf in ["15m", "1H", "75m", "4H", "1D", "1W"]:
        syms = list(dict.fromkeys(df[df["tf"] == tf]["symbol"]))
        if syms:
            parts.append(f"###{tf}," + ",".join("NSE:" + s for s in syms))
    return ",".join(parts)


# ───────────────────────── Dashboard feed (results.json) ──────────────────────────
def _fnum(v, d=0.0):
    try: return float(v) if pd.notna(v) else d
    except Exception: return d

def _inum(v, d=0):
    try: return int(v) if pd.notna(v) else d
    except Exception: return d

def rows_for_dashboard(df):
    out = []
    for _, r in df.iterrows():
        out.append(dict(
            sym=r["symbol"], sector=(r["sector"] if "sector" in r else "-"), tf=r["tf"],
            up=(r["trend"] == "up"), sig=r["signal"],
            zLow=_fnum(r["zlow"]), zHigh=_fnum(r["zhigh"]), ltp=_fnum(r["ltp"]),
            sinceTrig=(None if pd.isna(r["since"]) else _fnum(r["since"])),
            volX=_fnum(r["volx"]), spike=bool(r["spike"]), confMin=_inum(r["conf_min"])))
    return out

def save_dashboard_json(df, path="results.json"):
    """Write the scan as results.json in the dashboard's row schema."""
    import json, datetime
    data = {"generated_at": datetime.datetime.now().strftime("%H:%M %d %b"),
            "rows": rows_for_dashboard(df)}
    with open(path, "w") as f:
        json.dump(data, f)
    return path
