"""
ZigZag KB Fib Dual Trade — scanning engine
============================================

Python port of the Pine indicator (ZigZag KB Fib Dual Trade).
Detects A->B down-swings via ZigZag deviation logic, then classifies
each stock through a dual-trade state machine.

Output: results.json for the dashboard.

INTRADAY MODE (default ON for Dhan):
  When ENABLE_INTRADAY is True and the data source is Dhan, the engine
  fetches today's intraday bars and appends them as a "today partial daily
  bar" to the daily series. This lets signals fire in real time during
  market hours — matching the Pine indicator's behavior on TradingView.

  Signals fired on today's partial bar are flagged provisional=True
  (may revert before daily close). Signals on closed daily bars are
  provisional=False (locked in).

Environment:
    KWM_DATA_SOURCE   = "dhan" (real-time) or "yahoo" (delayed/free)
    DHAN_CLIENT_ID    = Dhan credential
    DHAN_ACCESS_TOKEN = Dhan token (daily refresh required)
    DHAN_SCRIP_URL    = Dhan scrip master CSV (optional override)
    ZIGZAG_INTRADAY   = "true"/"false" (default true) — disable intraday integration

Designed to run in Google Colab or as a GitHub Actions job.
"""
import os
import numpy as np
import pandas as pd
import datetime as dt

# ============================================================================
# CONFIG — match the Pine indicator defaults
# ============================================================================

# Fibonacci levels (measured B -> A as fraction of A-B)
FIB_SL1     = 0.236   # Trade 1 stop loss line
FIB_E1_LO   = 0.32    # Trade 1 Entry Zone bottom
FIB_E1_HI   = 0.382   # Trade 1 Entry Zone top (the trigger level)
FIB_T1_LO   = 0.618   # T1 TP / T2 Entry bottom
FIB_T1_HI   = 0.68    # T1 TP / T2 Entry top (the T2 trigger level)
FIB_T2_LO   = 1.00    # T2 TP bottom (= A)
FIB_T2_HI   = 1.05    # T2 TP top (5% above A)

# Filters
EMA_FAST = 9
EMA_SLOW = 21
VOL_AVG  = 20
VOL_MULT = 1.2

# ZigZag detection
DEV_PCT_DEFAULT = 35.0     # deviation percentage for swing confirmation
MIN_BARS_BETWEEN = 10      # minimum bars between pivots

# "Approaching" zone: how far below 0.32 we still flag as approaching
APPROACH_BAND_PCT = 0.05   # 5% below 0.32 level

# Recency: how many trading bars old before "Triggered" -> "Active"
RECENT_BARS = 1            # last 1 trading bar = "Triggered"

# Timeframe metadata (only Daily and Weekly per spec)
TF_LIST = ["1D", "1W"]
TF_MIN  = {"1D": 375, "1W": 1875}      # minutes per bar (D = session, W = 5*D)

# Data source defaults
DATA_SOURCE = os.environ.get("KWM_DATA_SOURCE", "yahoo").lower()
DHAN_SCRIP_URL = os.environ.get(
    "DHAN_SCRIP_URL",
    "https://images.dhan.co/api-data/api-scrip-master.csv"
)

# Intraday data integration — appends today's partial bar to the daily series
# so that intraday price action triggers signals in real-time, like the Pine indicator.
# Set to False to fall back to "yesterday-close-only" behavior.
ENABLE_INTRADAY = os.environ.get("ZIGZAG_INTRADAY", "true").lower() in ("1", "true", "yes")
INTRADAY_INTERVAL = 15  # minutes per intraday bar (15 = good balance of responsiveness vs API load)


# ============================================================================
# UNIVERSE LOADER (carried forward from the previous scanner)
# ============================================================================

def load_nifty500():
    """Fetch NSE's official Nifty 500 list with sector labels.

    Returns (symbols_list, {symbol: sector_name}).
    Falls back to a 20-stock shortlist if NSE blocks the request.
    """
    import io, requests
    try:
        url = "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
        txt = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=25).text
        d = pd.read_csv(io.StringIO(txt))
        sym = d["Symbol"].astype(str).str.strip()
        ind = d["Industry"].astype(str).str.strip()
        return sym.tolist(), dict(zip(sym, ind))
    except Exception as e:
        print(f"Could not fetch NSE Nifty 500 list ({e}); using shortlist.")
        fb = ["RELIANCE","TCS","HDFCBANK","ICICIBANK","INFY","SBIN","BHARTIARTL","ITC","LT","HINDUNILVR",
              "KOTAKBANK","AXISBANK","BAJFINANCE","MARUTI","SUNPHARMA","TATAMOTORS","TITAN","ULTRACEMCO","ASIANPAINT","NESTLEIND"]
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
        "Close": d["close"], "Volume": d.get("volume", [0]*len(d["close"]))
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
    "today's partial daily bar" with combined OHLCV. Returns a 1-row
    DataFrame indexed by today's date in Asia/Kolkata, or None if no
    intraday data is available (pre-market, weekend, holiday, error).

    This is the heart of intraday signal detection: by appending this
    bar to the daily series, the engine sees today's high/low/close
    in real time and fires signals when intraday price crosses fib levels.
    """
    today = dt.date.today()
    # No intraday data on weekends
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

    # Try the standard intraday method (dhanhq v2+). Falls back gracefully.
    r = None
    try:
        if hasattr(dh, 'intraday_minute_data'):
            r = dh.intraday_minute_data(
                security_id=sid,
                exchange_segment="NSE_EQ",
                instrument_type="EQUITY",
                from_date=str(today),
                to_date=str(today),
                interval=INTRADAY_INTERVAL,
            )
        elif hasattr(dh, 'historical_minute_data'):
            # Older method name in some dhanhq versions
            r = dh.historical_minute_data(
                security_id=sid,
                exchange_segment="NSE_EQ",
                instrument_type="EQUITY",
                from_date=str(today),
                to_date=str(today),
                interval=INTRADAY_INTERVAL,
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

    # Aggregate the intraday bars into a single daily-equivalent bar.
    try:
        today_open   = float(d["open"][0])
        today_high   = float(max(d["high"]))
        today_low    = float(min(d["low"]))
        today_close  = float(d["close"][-1])  # last intraday close ≈ current LTP
        today_volume = float(sum(d.get("volume", [0] * len(closes))))
    except (KeyError, IndexError, TypeError, ValueError):
        return None

    # Index by today's date in Asia/Kolkata for consistency with daily data
    try:
        ts = pd.Timestamp(today).tz_localize("Asia/Kolkata")
    except Exception:
        ts = pd.Timestamp(today)

    return pd.DataFrame({
        "Open":   [today_open],
        "High":   [today_high],
        "Low":    [today_low],
        "Close":  [today_close],
        "Volume": [today_volume],
    }, index=[ts])


def _resample_weekly(d):
    """Aggregate daily bars into weekly (Friday close)."""
    if d is None or len(d) == 0:
        return None
    return d.resample("W-FRI").agg({
        "Open":"first","High":"max","Low":"min","Close":"last","Volume":"sum"
    }).dropna()


def get_tf(symbol, tf):
    """Fetch OHLCV for one symbol at one timeframe. Returns DataFrame or None.

    For 1D + Dhan: if today's daily bar isn't yet in Dhan's daily API
    (which it usually isn't until post-close), we append today's
    intraday-aggregated partial bar so the engine sees live price action.
    """
    src = os.environ.get("KWM_DATA_SOURCE", DATA_SOURCE).lower()
    if src == "dhan":
        if tf == "1D":
            df = _fetch_dhan_daily(symbol, days=1100)
            if df is None or len(df) == 0:
                return df
            if not ENABLE_INTRADAY:
                return df
            # Check if today is already represented in the daily series.
            # (Post-close, Dhan eventually updates the daily endpoint with today's bar.)
            today = dt.date.today()
            try:
                last_date = df.index[-1].date()
            except Exception:
                last_date = None
            if last_date is not None and last_date >= today:
                return df  # today's daily bar already present, no need for intraday
            if today.weekday() >= 5:
                return df  # weekend, no intraday available anyway
            # Append today's partial bar from intraday data
            partial = _fetch_today_partial(symbol)
            if partial is not None and len(partial) > 0:
                df = pd.concat([df, partial])
            return df
        if tf == "1W":
            # Weekly: keep using only completed weekly bars for now.
            # Intraday-into-weekly aggregation is a future enhancement.
            return _resample_weekly(_fetch_dhan_daily(symbol, days=1800))
        raise ValueError(f"Unsupported tf: {tf}")
    # Yahoo (default) — no intraday integration; yfinance intraday is rate-limited and unreliable
    if tf == "1D":
        return _fetch_yahoo(symbol, "1d", "3y")
    if tf == "1W":
        return _fetch_yahoo(symbol, "1wk", "5y")
    raise ValueError(f"Unsupported tf: {tf}")


# ============================================================================
# ZIGZAG DETECTION — port of TradingView's ZigZag library logic
# ============================================================================
#
# Algorithm: walk through bars. Track "last extreme" (a high or a low) and the
# direction we're currently looking for. When price moves >= deviation_pct
# AGAINST the current direction from the last extreme, confirm a new pivot at
# that extreme and flip direction. The first pivot is established by whichever
# direction the price moves enough from the start.

def detect_zigzag_pivots(df, dev_pct, include_tentative=True):
    """Detect ZigZag pivots using percentage-deviation algorithm.

    Returns list of (bar_index, price, kind) tuples in chronological order,
    where kind is 'H' (pivot high) or 'L' (pivot low).

    Algorithm:
      Phase 1: walk forward tracking running highest high AND lowest low
               until one of them is exceeded by a `dev_pct` move in the
               opposite direction — that establishes the first confirmed
               pivot and the trend direction.
      Phase 2: track the running extreme in the trend direction. A pivot
               is confirmed when price moves >= dev_pct against the trend.

    `include_tentative` (default True): also append the current running
    extreme as a "tentative" pivot at the end. This matters for the
    strategy because:

      - The Pine ZigZag library only returns CONFIRMED pivots (those
        where the reversal already happened). For a still-forming swing
        low, you wouldn't see anything until price has rallied 35%.
      - But for Fibonacci-based setups, the swing low IS the swing low
        the moment it forms — we don't need the rally to confirm it
        before drawing fib levels off it.
      - The 0.382 retracement trigger fires at a 28% rally from B (less
        than the 35% ZigZag threshold), so a confirmed trigger CAN fire
        on a tentative B.
      - By exposing the tentative pivot, the scanner surfaces setups
        days or weeks earlier — Approaching T1, In Zone T1 zones become
        visible while the bounce is still forming, not only after the
        explosive day that confirms B.

    Set include_tentative=False to get the strict Pine-library behavior
    (only confirmed pivots).
    """
    if df is None or len(df) < 10:
        return []

    high = df["High"].to_numpy(float)
    low  = df["Low"].to_numpy(float)
    n = len(high)
    threshold = dev_pct / 100.0

    pivots = []  # list of (bar_idx, price, 'H'|'L')

    # Phase 1 — establish initial direction
    hi_idx, hi_price = 0, high[0]
    lo_idx, lo_price = 0, low[0]
    direction = None

    i = 1
    while i < n and direction is None:
        if high[i] > hi_price:
            hi_idx, hi_price = i, high[i]
        if low[i] < lo_price:
            lo_idx, lo_price = i, low[i]
        if low[i] <= hi_price * (1 - threshold) and hi_idx < i:
            pivots.append((hi_idx, hi_price, 'H'))
            direction = 'down'
            ext_idx, ext_price = lo_idx, lo_price
        elif high[i] >= lo_price * (1 + threshold) and lo_idx < i:
            pivots.append((lo_idx, lo_price, 'L'))
            direction = 'up'
            ext_idx, ext_price = hi_idx, hi_price
        i += 1

    if direction is None:
        return []

    # Phase 2 — track running extreme; flip on reversal
    while i < n:
        if direction == 'up':
            if high[i] > ext_price:
                ext_idx, ext_price = i, high[i]
            elif low[i] <= ext_price * (1 - threshold):
                pivots.append((ext_idx, ext_price, 'H'))
                direction = 'down'
                ext_idx, ext_price = i, low[i]
        else:  # 'down'
            if low[i] < ext_price:
                ext_idx, ext_price = i, low[i]
            elif high[i] >= ext_price * (1 + threshold):
                pivots.append((ext_idx, ext_price, 'L'))
                direction = 'up'
                ext_idx, ext_price = i, high[i]
        i += 1

    # Phase 3 — append the still-forming running extreme as a tentative pivot.
    # Direction 'down' = we're tracking a low (potential L pivot, not yet
    # confirmed by a 35% rally). Direction 'up' = tracking a high.
    if include_tentative:
        kind = 'L' if direction == 'down' else 'H'
        # Only add if it's a different bar from the last confirmed pivot
        if not pivots or pivots[-1][0] != ext_idx:
            pivots.append((ext_idx, ext_price, kind))

    return pivots


# ============================================================================
# SWING SELECTION — find Recent A->B and Macro A->B
# ============================================================================

def find_recent_downswing(pivots):
    """Return (A_idx, A_price, B_idx, B_price) of most recent A->B down-swing.

    A down-swing is a 'H' pivot immediately followed by an 'L' pivot.
    Returns None if no down-swing exists.
    """
    if len(pivots) < 2:
        return None
    # Walk from the end backward, find the most recent H followed by L
    for j in range(len(pivots) - 1, 0, -1):
        if pivots[j][2] == 'L' and pivots[j-1][2] == 'H':
            ai, ap, _ = pivots[j-1]
            bi, bp, _ = pivots[j]
            return (ai, ap, bi, bp)
    return None


def find_macro_downswing(pivots):
    """Return (A_idx, A_price, B_idx, B_price) of macro down-swing.

    A_macro = highest pivot in the series.
    B_macro = lowest pivot that comes AFTER A_macro.
    """
    if len(pivots) < 2:
        return None
    # Find highest pivot
    a_idx = max(range(len(pivots)), key=lambda i: pivots[i][1])
    ai, ap, _ = pivots[a_idx]
    # Find lowest pivot after a_idx
    after = [(i, p) for (i, p, k) in pivots[a_idx+1:]]
    if not after:
        return None
    bi, bp = min(after, key=lambda x: x[1])
    return (ai, ap, bi, bp)


# ============================================================================
# STATE MACHINE — port from Pine v2.0
# ============================================================================
#
# Walks through bars from B forward, simulates the dual-trade lifecycle, and
# returns the final state plus context about when transitions happened.

def simulate_trade_state(df, ai, ap, bi, bp):
    """Run the state machine bar-by-bar from B forward through to the latest bar.

    States:
      1 = Waiting T1 entry
      2 = In Trade 1
      3 = T1 played -> Waiting T2 entry
      4 = In Trade 2
      5 = Fully played (T2 hit TP)
      6 = Target Hit Recent (T1 or T2 hit TP, used for Performance tab)

    Returns dict:
      state, t1_entry_bar, t1_tp_bar, t1_sl_bar,
      t2_entry_bar, t2_tp_bar, t2_sl_bar,
      t1_ever_triggered, t1_ever_played, t2_ever_played
    """
    rng = ap - bp
    if rng <= 0:
        return None

    sl1   = bp + FIB_SL1   * rng
    e1_lo = bp + FIB_E1_LO * rng
    e1_hi = bp + FIB_E1_HI * rng
    t1_lo = bp + FIB_T1_LO * rng
    t1_hi = bp + FIB_T1_HI * rng
    t2_lo = bp + FIB_T2_LO * rng
    t2_hi = bp + FIB_T2_HI * rng

    close = df["Close"].to_numpy(float)
    high  = df["High"].to_numpy(float)
    vol   = df["Volume"].to_numpy(float)
    n = len(close)

    # EMAs
    ema9  = pd.Series(close).ewm(span=EMA_FAST, adjust=False).mean().to_numpy()
    ema21 = pd.Series(close).ewm(span=EMA_SLOW, adjust=False).mean().to_numpy()

    # Rolling volume average
    vol_sma = pd.Series(vol).rolling(VOL_AVG, min_periods=1).mean().to_numpy()

    state = 1
    t1_ever_triggered = False
    t1_ever_played    = False
    t2_ever_played    = False
    t1_entry_bar = t1_tp_bar = t1_sl_bar = None
    t2_entry_bar = t2_tp_bar = t2_sl_bar = None

    for k in range(bi + 1, n):
        c_now  = close[k]
        c_prev = close[k-1] if k > 0 else c_now
        h_now  = high[k]
        ema_ok = (c_now > ema9[k]) and (c_now > ema21[k])
        vol_ok = vol[k] > vol_sma[k] * VOL_MULT

        crossed_382 = c_now > e1_hi and c_prev <= e1_hi
        crossed_68  = c_now > t1_hi and c_prev <= t1_hi

        if state == 1:
            # Jump-in to T2 if price closes above 0.68 while T1 never fired
            if crossed_68 and ema_ok and vol_ok:
                state = 4
                t2_entry_bar = k
                t1_ever_played = True  # T1 skipped/considered done
            elif crossed_382 and ema_ok and vol_ok:
                state = 2
                t1_entry_bar = k
                t1_ever_triggered = True

        elif state == 2:
            if h_now >= t1_lo:  # touched T1 TP zone
                state = 3
                t1_tp_bar = k
                t1_ever_played = True
            elif c_now < sl1:
                state = 1
                t1_sl_bar = k

        elif state == 3:
            if crossed_68 and ema_ok and vol_ok:
                state = 4
                t2_entry_bar = k

        elif state == 4:
            if h_now >= t2_lo:  # touched T2 TP zone
                state = 5
                t2_tp_bar = k
                t2_ever_played = True
            elif c_now < t1_lo:
                state = 3 if t1_ever_triggered else 1
                t2_sl_bar = k

    return dict(
        state=state,
        t1_entry_bar=t1_entry_bar, t1_tp_bar=t1_tp_bar, t1_sl_bar=t1_sl_bar,
        t2_entry_bar=t2_entry_bar, t2_tp_bar=t2_tp_bar, t2_sl_bar=t2_sl_bar,
        t1_ever_triggered=t1_ever_triggered,
        t1_ever_played=t1_ever_played,
        t2_ever_played=t2_ever_played,
        sl1=sl1, e1_lo=e1_lo, e1_hi=e1_hi,
        t1_lo=t1_lo, t1_hi=t1_hi, t2_lo=t2_lo, t2_hi=t2_hi,
    )


# ============================================================================
# SIGNAL CLASSIFICATION — the 7-category taxonomy
# ============================================================================

def classify_signal(sim, df, recent_bars=RECENT_BARS):
    """Pick the single most-relevant signal category for the scanner.

    Categories (priority order — most actionable first):
      "Triggered T2"     — close > 0.68 (intraday or recent close)
      "Triggered T1"     — close > 0.382 (intraday or recent close)
      "Active T2"        — In T2, triggered on a CLOSED daily bar more than recent_bars ago
      "Active T1"        — In T1, triggered on a CLOSED daily bar more than recent_bars ago
      "In Zone T2"       — between 0.618 and 0.68
      "In Zone T1"       — between 0.32 and 0.382
      "Approaching T1"   — below 0.32, within APPROACH_BAND_PCT
      None               — outside our band of interest, or fully played

    PROV flag semantics:
      True  = signal evaluated on TODAY's intraday partial bar (may revert before close)
      False = signal confirmed on a CLOSED daily bar (locked in, won't change)

    Returns (signal_str, active_trade, provisional_bool, confirmed_bar, ltp).
    """
    state = sim["state"]
    close = df["Close"].to_numpy(float)
    n = len(close)
    if n == 0:
        return None
    ltp = float(close[-1])
    bar_idx = n - 1

    e1_hi = sim["e1_hi"]
    t1_lo = sim["t1_lo"]
    t1_hi = sim["t1_hi"]
    e1_lo = sim["e1_lo"]

    # Detect if the latest bar is today's intraday partial AND market is still open.
    # After 3:30 PM IST on a weekday, today's intraday data reflects the day's close
    # (market is shut, no more updates) → treat as confirmed, drop PROV.
    try:
        last_bar_date = df.index[-1].date()
        ist = dt.timezone(dt.timedelta(hours=5, minutes=30))
        now_ist = dt.datetime.now(ist)
        today_ist = now_ist.date()
        # Market hours: 9:15 AM - 3:30 PM IST. Use 3:30 PM as the "session over" threshold.
        is_after_close = (now_ist.hour > 15) or (now_ist.hour == 15 and now_ist.minute >= 30)
        is_intraday = (
            last_bar_date == today_ist
            and today_ist.weekday() < 5
            and not is_after_close
        )
    except Exception:
        is_intraday = False

    # ----- Active states (state machine fired entry on some past bar) -----
    if state == 2:
        # In T1 — engine processed a bar where close crossed 0.382 with confirmation
        entry_bar = sim["t1_entry_bar"]
        bars_since = bar_idx - entry_bar if entry_bar is not None else 999
        # If entry happened on today's intraday partial bar → PROV (entry may not survive close)
        entered_today_intraday = (is_intraday and entry_bar == bar_idx)
        if entered_today_intraday:
            return ("Triggered T1", "T1", True, entry_bar, ltp)
        if bars_since < recent_bars:
            return ("Triggered T1", "T1", False, entry_bar, ltp)
        return ("Active T1", "T1", False, entry_bar, ltp)

    if state == 4:
        # In T2 — engine processed a bar where close crossed 0.68 with confirmation
        entry_bar = sim["t2_entry_bar"]
        bars_since = bar_idx - entry_bar if entry_bar is not None else 999
        entered_today_intraday = (is_intraday and entry_bar == bar_idx)
        if entered_today_intraday:
            return ("Triggered T2", "T2", True, entry_bar, ltp)
        if bars_since < recent_bars:
            return ("Triggered T2", "T2", False, entry_bar, ltp)
        return ("Active T2", "T2", False, entry_bar, ltp)

    if state == 5:
        # Fully played — not surfaced in scanner (Performance tab handles)
        return None

    # ----- Waiting states — state machine never fired, classify by LTP. -----
    # PROV here = today's bar still forming (is_intraday). After market close it's False:
    # the daily bar is locked, even if filters didn't pass the signal is what it is.
    if state == 3:
        # Waiting T2 entry (T1 already played)
        if ltp > t1_hi:
            return ("Triggered T2", "T2", is_intraday, bar_idx, ltp)
        if t1_lo <= ltp <= t1_hi:
            return ("In Zone T2", "T2", is_intraday, None, ltp)
        return None

    if state == 1:
        # Waiting T1 entry
        if ltp > t1_hi:
            return ("Triggered T2", "T2", is_intraday, bar_idx, ltp)
        if t1_lo <= ltp <= t1_hi:
            return ("In Zone T2", "T2", is_intraday, None, ltp)
        if ltp > e1_hi:
            return ("Triggered T1", "T1", is_intraday, bar_idx, ltp)
        if e1_lo <= ltp <= e1_hi:
            return ("In Zone T1", "T1", is_intraday, None, ltp)
        if ltp < e1_lo and ltp >= e1_lo * (1 - APPROACH_BAND_PCT):
            return ("Approaching T1", "T1", is_intraday, None, ltp)
        return None

    return None


# ============================================================================
# PER-STOCK ANALYSIS
# ============================================================================

def analyze_one(symbol, tf, dev_pct=DEV_PCT_DEFAULT, df=None):
    """Analyze one symbol at one timeframe. Returns row dict or None.

    df: optional pre-fetched DataFrame. If None, get_tf() is called.
    """
    if df is None:
        df = get_tf(symbol, tf)
    if df is None or len(df) < 30:
        return None

    pivots = detect_zigzag_pivots(df, dev_pct)
    if len(pivots) < 2:
        return None

    recent = find_recent_downswing(pivots)
    if recent is None:
        return None
    ai, ap, bi, bp = recent

    sim = simulate_trade_state(df, ai, ap, bi, bp)
    if sim is None:
        return None

    cls = classify_signal(sim, df)
    if cls is None:
        return None
    signal, active_trade, provisional, conf_bar, ltp = cls

    # Final values
    close = df["Close"].to_numpy(float)
    n = len(close)
    bar_idx = n - 1

    # EMAs and volume status for the latest bar
    ema9_last  = pd.Series(close).ewm(span=EMA_FAST, adjust=False).mean().iloc[-1]
    ema21_last = pd.Series(close).ewm(span=EMA_SLOW, adjust=False).mean().iloc[-1]
    ema_ok = bool(ltp > ema9_last and ltp > ema21_last)

    vol = df["Volume"].to_numpy(float)
    vol_avg = pd.Series(vol).rolling(VOL_AVG, min_periods=1).mean().iloc[-1]
    vol_ratio = float(vol[-1] / vol_avg) if vol_avg > 0 else 0.0
    vol_ok = bool(vol_ratio > VOL_MULT)

    # Drop %
    drop_pct = (ap - bp) / ap * 100.0

    # R:R — depends on which trade is active
    rr = None
    if active_trade == "T1":
        # T1: risk = entry_hi - sl1, reward = t1_lo - entry_hi (touching TP zone)
        risk = sim["e1_hi"] - sim["sl1"]
        reward = sim["t1_lo"] - sim["e1_hi"]
        if risk > 0:
            rr = round(reward / risk, 2)
    elif active_trade == "T2":
        risk = sim["t1_hi"] - sim["t1_lo"]   # T2 SL = close < 0.618
        reward = sim["t2_lo"] - sim["t1_hi"]
        if risk > 0:
            rr = round(reward / risk, 2)

    # Confirmed time — timestamp of the conf_bar if applicable
    confirmed_iso = None
    if conf_bar is not None and conf_bar < n:
        try:
            confirmed_iso = df.index[conf_bar].isoformat()
        except Exception:
            confirmed_iso = None

    # Macro context (optional, for expanded row detail)
    macro = find_macro_downswing(pivots)
    macro_a = macro_b = None
    if macro is not None and (macro[0] != ai or macro[2] != bi):
        macro_a = float(macro[1])
        macro_b = float(macro[3])

    # Map detailed signal to a coarser "action" the trader actually takes
    if signal in ("Approaching T1", "In Zone T1", "In Zone T2"):
        action = "Watch"
    elif signal in ("Triggered T1", "Triggered T2"):
        action = "Enter"
    elif signal in ("Active T1", "Active T2"):
        action = "Holding"
    else:
        action = None

    return dict(
        sym=symbol, tf=tf,
        signal=signal,                # detailed 7-category (kept for backwards compat)
        action=action,                # NEW: Watch / Enter / Holding
        active_trade=active_trade, provisional=provisional,
        A=round(float(ap), 2), B=round(float(bp), 2),
        drop_pct=round(drop_pct, 2),
        ltp=round(ltp, 2),
        t1_entry_lo=round(float(sim["e1_lo"]), 2),
        t1_entry_hi=round(float(sim["e1_hi"]), 2),
        t1_tp_lo=round(float(sim["t1_lo"]), 2),
        t1_tp_hi=round(float(sim["t1_hi"]), 2),
        t1_sl=round(float(sim["sl1"]), 2),
        t2_entry_lo=round(float(sim["t1_lo"]), 2),  # same as T1 TP
        t2_entry_hi=round(float(sim["t1_hi"]), 2),
        t2_tp_lo=round(float(sim["t2_lo"]), 2),
        t2_tp_hi=round(float(sim["t2_hi"]), 2),
        t2_sl=round(float(sim["t1_lo"]), 2),         # T2 SL = 0.618
        ema_ok=ema_ok, vol_ok=vol_ok,
        vol_x=round(vol_ratio, 1),
        rr=rr,
        confirmed_at=confirmed_iso,
        macro_a=round(macro_a, 2) if macro_a else None,
        macro_b=round(macro_b, 2) if macro_b else None,
    )


# ============================================================================
# BACKTEST — walk every historical swing and tally completed trades
# ============================================================================
#
# For each H→L pair in the ZigZag pivot list (each is a historical down-swing),
# we run the dual-trade state machine forward from B until either:
#   - T1 + T2 both resolve (TP hit or SL out)
#   - A new lower L appears (B invalidated → swing dead)
#   - End of data
#
# Each completed T1 or T2 trade is recorded with its R multiple, entry/exit
# dates, and outcome. These records feed the Performance tab.

def _backtest_one_swing(df, ai, ap, bi, bp, end_bar):
    """Run state machine from B forward; collect completed trades up to end_bar.

    Returns list of trade dicts with keys:
      trade_type, entry_bar, entry_date, entry_price,
      exit_bar, exit_date, exit_price, outcome ('win'/'loss'), r_multiple
    """
    rng = ap - bp
    if rng <= 0:
        return []

    sl1   = bp + FIB_SL1   * rng
    e1_hi = bp + FIB_E1_HI * rng       # T1 entry trigger
    t1_lo = bp + FIB_T1_LO * rng       # T1 TP level (also T2 SL)
    t1_hi = bp + FIB_T1_HI * rng       # T2 entry trigger
    t2_lo = bp + FIB_T2_LO * rng       # T2 TP level

    close = df["Close"].to_numpy(float)
    high  = df["High"].to_numpy(float)
    vol   = df["Volume"].to_numpy(float)
    n = min(len(close), end_bar + 1)

    if n <= bi + 1:
        return []

    ema9  = pd.Series(close).ewm(span=EMA_FAST, adjust=False).mean().to_numpy()
    ema21 = pd.Series(close).ewm(span=EMA_SLOW, adjust=False).mean().to_numpy()
    vol_sma = pd.Series(vol).rolling(VOL_AVG, min_periods=1).mean().to_numpy()

    trades = []
    state = 1
    t1_entry_bar = None
    t2_entry_bar = None

    for k in range(bi + 1, n):
        c_now = close[k]
        c_prev = close[k - 1] if k > 0 else c_now
        h_now = high[k]
        ema_ok = (c_now > ema9[k]) and (c_now > ema21[k])
        vol_ok = vol[k] > vol_sma[k] * VOL_MULT
        crossed_382 = c_now > e1_hi and c_prev <= e1_hi
        crossed_68  = c_now > t1_hi and c_prev <= t1_hi

        if state == 1:
            if crossed_68 and ema_ok and vol_ok:
                state = 4
                t2_entry_bar = k
            elif crossed_382 and ema_ok and vol_ok:
                state = 2
                t1_entry_bar = k

        elif state == 2:
            if h_now >= t1_lo:
                # T1 TP hit
                trades.append({
                    "trade_type": "T1",
                    "entry_bar":   t1_entry_bar,
                    "entry_date":  df.index[t1_entry_bar].isoformat() if t1_entry_bar is not None else None,
                    "entry_price": round(e1_hi, 2),
                    "exit_bar":    k,
                    "exit_date":   df.index[k].isoformat(),
                    "exit_price":  round(t1_lo, 2),
                    "outcome":     "win",
                    "r_multiple":  round((t1_lo - e1_hi) / (e1_hi - sl1), 2) if (e1_hi - sl1) > 0 else 0.0,
                    "A": round(ap, 2), "B": round(bp, 2),
                })
                state = 3
            elif c_now < sl1:
                trades.append({
                    "trade_type": "T1",
                    "entry_bar":   t1_entry_bar,
                    "entry_date":  df.index[t1_entry_bar].isoformat() if t1_entry_bar is not None else None,
                    "entry_price": round(e1_hi, 2),
                    "exit_bar":    k,
                    "exit_date":   df.index[k].isoformat(),
                    "exit_price":  round(sl1, 2),
                    "outcome":     "loss",
                    "r_multiple":  -1.0,
                    "A": round(ap, 2), "B": round(bp, 2),
                })
                state = 1
                t1_entry_bar = None

        elif state == 3:
            if crossed_68 and ema_ok and vol_ok:
                state = 4
                t2_entry_bar = k

        elif state == 4:
            if h_now >= t2_lo:
                # T2 TP hit
                trades.append({
                    "trade_type": "T2",
                    "entry_bar":   t2_entry_bar,
                    "entry_date":  df.index[t2_entry_bar].isoformat() if t2_entry_bar is not None else None,
                    "entry_price": round(t1_hi, 2),
                    "exit_bar":    k,
                    "exit_date":   df.index[k].isoformat(),
                    "exit_price":  round(t2_lo, 2),
                    "outcome":     "win",
                    "r_multiple":  round((t2_lo - t1_hi) / (t1_hi - t1_lo), 2) if (t1_hi - t1_lo) > 0 else 0.0,
                    "A": round(ap, 2), "B": round(bp, 2),
                })
                state = 5
                break  # T2 done, no more trades from this swing
            elif c_now < t1_lo:
                # T2 SL = close < 0.618
                trades.append({
                    "trade_type": "T2",
                    "entry_bar":   t2_entry_bar,
                    "entry_date":  df.index[t2_entry_bar].isoformat() if t2_entry_bar is not None else None,
                    "entry_price": round(t1_hi, 2),
                    "exit_bar":    k,
                    "exit_date":   df.index[k].isoformat(),
                    "exit_price":  round(t1_lo, 2),
                    "outcome":     "loss",
                    "r_multiple":  -1.0,
                    "A": round(ap, 2), "B": round(bp, 2),
                })
                state = 3
                t2_entry_bar = None

        elif state == 5:
            break  # fully played

    return trades


def backtest_history(df, dev_pct=DEV_PCT_DEFAULT, window_days=None):
    """For one stock's full history, return all completed historical trades.

    window_days: if set, only count trades whose entry was within the last N days.
    """
    if df is None or len(df) < 30:
        return []

    # Use confirmed pivots only (no tentative) — backtesting should reflect
    # only fully realized historical swings.
    pivots = detect_zigzag_pivots(df, dev_pct, include_tentative=False)
    if len(pivots) < 2:
        return []

    all_trades = []
    n = len(df)
    # Walk every H→L pair as a separate swing
    for j in range(1, len(pivots)):
        if pivots[j][2] != 'L' or pivots[j-1][2] != 'H':
            continue
        ai, ap, _ = pivots[j-1]
        bi, bp, _ = pivots[j]

        # End the simulation when a subsequent L makes a new low (B invalidated)
        # or when the next H confirms (this swing's window has closed for new trades).
        end_bar = n - 1
        for k in range(j + 1, len(pivots)):
            if pivots[k][2] == 'L' and pivots[k][1] < bp:
                end_bar = pivots[k][0] - 1
                break
            # The next H pivot means this swing was a tradeable lifecycle; keep walking
            # to capture trades that complete after the new H formed. The state machine
            # will handle its own exit conditions.

        swing_trades = _backtest_one_swing(df, ai, ap, bi, bp, end_bar)
        all_trades.extend(swing_trades)

    # Apply window filter
    if window_days is not None and all_trades:
        cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=window_days)
        # Compare without timezone if needed
        def _within_window(t):
            try:
                d = dt.datetime.fromisoformat(t["entry_date"].replace("Z", "+00:00"))
                if d.tzinfo is None:
                    d = d.replace(tzinfo=dt.timezone.utc)
                return d >= cutoff
            except Exception:
                return True  # keep if we can't parse
        all_trades = [t for t in all_trades if _within_window(t)]

    return all_trades


# ============================================================================
# SCANNING — iterate over the universe
# ============================================================================

def scan(symbols, timeframes=("1D", "1W"), dev_pct=DEV_PCT_DEFAULT, verbose=False, return_stats=False):
    """Scan a list of symbols across given timeframes.

    Returns DataFrame by default. If return_stats=True, returns (DataFrame, stats_dict).
    The stats_dict has keys: attempted, fetched_ok, setups, sample_errors.
    """
    rows = []
    stats = {"attempted": 0, "fetched_ok": 0, "setups": 0, "sample_errors": []}
    for s in symbols:
        for tf in timeframes:
            stats["attempted"] += 1
            try:
                # Fetch step (this is what fails on Dhan auth issues)
                df = get_tf(s, tf)
                if df is None or len(df) < 30:
                    continue
                stats["fetched_ok"] += 1
                # Analysis step (this is what produces a setup, or not)
                r = analyze_one(s, tf, dev_pct=dev_pct, df=df)
                if r:
                    rows.append(r)
                    stats["setups"] += 1
            except Exception as e:
                # Keep a tiny sample of errors for diagnostics (cap at 3)
                if len(stats["sample_errors"]) < 3:
                    stats["sample_errors"].append(f"{s}/{tf}: {str(e)[:120]}")
                if verbose:
                    print(f"skip {s} {tf} - {e}")
    df_out = pd.DataFrame(rows) if rows else pd.DataFrame()
    if return_stats:
        return df_out, stats
    return df_out


# ============================================================================
# OUTPUT — results.json for the dashboard
# ============================================================================

def save_dashboard_json(df, path="results.json", deviation=DEV_PCT_DEFAULT, sectors=None, stats=None):
    """Write the scan results in the dashboard's expected schema.

    stats: optional dict from scan(return_stats=True) used to classify run health:
      - 'ok'        : setups found, normal
      - 'no_data'   : <10% of fetches succeeded — almost certainly auth/API failure
      - 'no_setups' : fetches succeeded but no qualifying setups (rare but legitimate)
      - 'empty_universe' : no symbols to scan
    """
    import json

    def _clean(v):
        """Convert pandas NaN/NaT to None so the JSON is valid (NaN is NOT valid JSON)."""
        if v is None:
            return None
        try:
            if pd.isna(v):
                return None
        except (TypeError, ValueError):
            pass
        return v

    rows = []
    if not df.empty:
        for _, r in df.iterrows():
            sym = r["sym"]
            sector = sectors.get(sym, "-") if sectors else "-"
            rows.append({
                "sym": sym, "sector": sector, "tf": r["tf"],
                "signal": r["signal"], "active_trade": r["active_trade"],
                "action": _clean(r.get("action", None)) if "action" in r else None,
                "provisional": bool(r["provisional"]),
                "A": _clean(r["A"]), "B": _clean(r["B"]),
                "drop_pct": _clean(r["drop_pct"]),
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

    now_ist = dt.datetime.now(dt.timezone(dt.timedelta(hours=5, minutes=30)))

    # Classify run health based on stats (if available)
    if stats is None:
        data_status = "ok" if rows else "no_setups"
        stats_clean = None
    else:
        attempted   = int(stats.get("attempted", 0))
        fetched_ok  = int(stats.get("fetched_ok", 0))
        setups      = int(stats.get("setups", len(rows)))
        if attempted == 0:
            data_status = "empty_universe"
        elif fetched_ok / max(attempted, 1) < 0.10:
            data_status = "no_data"
        elif setups == 0:
            data_status = "no_setups"
        else:
            data_status = "ok"
        stats_clean = {
            "attempted": attempted,
            "fetched_ok": fetched_ok,
            "setups": setups,
            "sample_errors": list(stats.get("sample_errors", []))[:3],
        }

    data = {
        "generated_at": now_ist.isoformat(timespec="seconds"),
        "generated_label": now_ist.strftime("%H:%M IST · %d %b"),
        "deviation": deviation,
        "data_status": data_status,
        "stats": stats_clean,
        "rows": rows,
    }
    # allow_nan=False so any NaN that sneaks through fails loudly rather than producing invalid JSON
    with open(path, "w") as f:
        json.dump(data, f, indent=2, allow_nan=False)
    return path


# ============================================================================
# PERFORMANCE — aggregate backtest results across all stocks
# ============================================================================

def backtest_all(symbols, timeframes=("1D", "1W"), dev_pct=DEV_PCT_DEFAULT,
                 window_days=365, sectors=None, verbose=False):
    """Run backtest across a universe. Returns flat list of trades with sym/tf attached."""
    all_trades = []
    for s in symbols:
        for tf in timeframes:
            try:
                df = get_tf(s, tf)
                if df is None or len(df) < 30:
                    continue
                # Drop today's partial bar from backtest (only completed bars count for history)
                today = dt.date.today()
                try:
                    last_date = df.index[-1].date()
                    if last_date == today:
                        df = df.iloc[:-1]
                except Exception:
                    pass
                trades = backtest_history(df, dev_pct=dev_pct, window_days=window_days)
                for t in trades:
                    t["sym"] = s
                    t["tf"] = tf
                    if sectors:
                        t["sector"] = sectors.get(s, "—")
                all_trades.extend(trades)
            except Exception as e:
                if verbose:
                    print(f"backtest skip {s} {tf}: {e}")
    return all_trades


def _aggregate_performance(trades):
    """Aggregate a list of trade records into Performance-tab statistics."""
    if not trades:
        return {
            "summary": {"total_trades": 0, "wins": 0, "losses": 0,
                        "win_rate": 0.0, "avg_r": 0.0, "total_r": 0.0},
            "breakdown": [],
            "monthly": [],
            "top_performers": [],
            "worst_performers": [],
            "distribution": {"buckets": [], "counts": []},
        }

    total = len(trades)
    wins = sum(1 for t in trades if t["outcome"] == "win")
    losses = total - wins
    total_r = sum(t["r_multiple"] for t in trades)
    avg_r = total_r / total if total else 0.0

    summary = {
        "total_trades": total,
        "wins": wins,
        "losses": losses,
        "win_rate": round(wins / total, 3) if total else 0.0,
        "avg_r": round(avg_r, 2),
        "total_r": round(total_r, 1),
    }

    # Breakdown by (trade_type, tf)
    bd = {}
    for t in trades:
        key = (t["trade_type"], t["tf"])
        b = bd.setdefault(key, {"trades": 0, "wins": 0, "total_r": 0.0})
        b["trades"] += 1
        if t["outcome"] == "win":
            b["wins"] += 1
        b["total_r"] += t["r_multiple"]
    breakdown = []
    for (tt, tf), v in sorted(bd.items()):
        breakdown.append({
            "trade_type": tt, "tf": tf,
            "trades": v["trades"], "wins": v["wins"],
            "win_rate": round(v["wins"] / v["trades"], 3) if v["trades"] else 0.0,
            "avg_r": round(v["total_r"] / v["trades"], 2) if v["trades"] else 0.0,
            "total_r": round(v["total_r"], 1),
        })

    # Monthly aggregation (by entry date)
    monthly = {}
    for t in trades:
        try:
            entry_d = dt.datetime.fromisoformat(t["entry_date"].replace("Z", "+00:00"))
            key = entry_d.strftime("%Y-%m")
        except Exception:
            continue
        m = monthly.setdefault(key, {"trades": 0, "wins": 0, "total_r": 0.0})
        m["trades"] += 1
        if t["outcome"] == "win":
            m["wins"] += 1
        m["total_r"] += t["r_multiple"]
    monthly_list = []
    for month in sorted(monthly.keys()):
        v = monthly[month]
        monthly_list.append({
            "month": month,
            "trades": v["trades"], "wins": v["wins"],
            "total_r": round(v["total_r"], 1),
        })

    # Best and worst performers (by total R across all trades on that stock)
    by_sym = {}
    for t in trades:
        sym = t["sym"]
        s = by_sym.setdefault(sym, {"trades": 0, "total_r": 0.0, "tf": t["tf"]})
        s["trades"] += 1
        s["total_r"] += t["r_multiple"]
    perfs = [{"sym": k, "trades": v["trades"], "total_r": round(v["total_r"], 1), "tf": v["tf"]}
             for k, v in by_sym.items()]
    perfs_sorted = sorted(perfs, key=lambda x: x["total_r"], reverse=True)
    top_performers = perfs_sorted[:10]
    worst_performers = sorted(perfs_sorted[-10:], key=lambda x: x["total_r"])

    # Distribution (R-multiple buckets)
    buckets_def = [
        ("≤ -1R",   lambda r: r <= -0.99),
        ("-1 to 0", lambda r: -0.99 < r <= 0),
        ("0 to 1",  lambda r: 0 < r <= 1.0),
        ("1 to 2",  lambda r: 1.0 < r <= 2.0),
        ("2 to 3",  lambda r: 2.0 < r <= 3.0),
        ("> 3R",    lambda r: r > 3.0),
    ]
    counts = [sum(1 for t in trades if fn(t["r_multiple"])) for _, fn in buckets_def]
    distribution = {
        "buckets": [b[0] for b in buckets_def],
        "counts": counts,
    }

    return {
        "summary": summary,
        "breakdown": breakdown,
        "monthly": monthly_list,
        "top_performers": top_performers,
        "worst_performers": worst_performers,
        "distribution": distribution,
    }


def save_performance_json(trades, path="performance.json", window_days=365):
    """Compute aggregate stats from trades and write to performance.json."""
    import json
    aggs = _aggregate_performance(trades)
    now_ist = dt.datetime.now(dt.timezone(dt.timedelta(hours=5, minutes=30)))
    data = {
        "generated_at": now_ist.isoformat(timespec="seconds"),
        "generated_label": now_ist.strftime("%H:%M IST · %d %b"),
        "window_days": window_days,
        **aggs,
    }
    with open(path, "w") as f:
        json.dump(data, f, indent=2, allow_nan=False)
    return path


# ============================================================================
# QUICK SELF-TEST (run only if executed directly)
# ============================================================================

if __name__ == "__main__":
    # Smoke test with a few well-known symbols on yfinance
    syms = ["DEEPAKNTR", "TEGA", "CDSL"]
    print(f"Smoke test on {syms}")
    df = scan(syms, timeframes=["1D"], dev_pct=35.0, verbose=True)
    if df.empty:
        print("No setups found — try lowering deviation %")
    else:
        print(df[["sym","tf","signal","A","B","drop_pct","ltp","rr"]])
        save_dashboard_json(df, path="/tmp/results_test.json")
        print("Saved /tmp/results_test.json")

