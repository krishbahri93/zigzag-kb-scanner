"""
ZigZag KB Fib Dual Trade — scanning engine
============================================

Python port of the Pine indicator (ZigZag KB Fib Dual Trade).
Detects A->B down-swings via ZigZag deviation logic, then classifies
each stock through a dual-trade state machine.

Output: results.json for the dashboard.

Environment:
    KWM_DATA_SOURCE  = "dhan" (real-time) or "yahoo" (delayed/free)
    DHAN_CLIENT_ID   = Dhan credential
    DHAN_ACCESS_TOKEN = Dhan token (daily refresh)
    DHAN_SCRIP_URL   = Dhan scrip master CSV (optional override)

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


def _resample_weekly(d):
    """Aggregate daily bars into weekly (Friday close)."""
    if d is None or len(d) == 0:
        return None
    return d.resample("W-FRI").agg({
        "Open":"first","High":"max","Low":"min","Close":"last","Volume":"sum"
    }).dropna()


def get_tf(symbol, tf):
    """Fetch OHLCV for one symbol at one timeframe. Returns DataFrame or None."""
    src = os.environ.get("KWM_DATA_SOURCE", DATA_SOURCE).lower()
    if src == "dhan":
        if tf == "1D":
            return _fetch_dhan_daily(symbol, days=1100)
        if tf == "1W":
            return _resample_weekly(_fetch_dhan_daily(symbol, days=1800))
        raise ValueError(f"Unsupported tf: {tf}")
    # Yahoo (default)
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

def detect_zigzag_pivots(df, dev_pct):
    """Detect ZigZag pivots using percentage-deviation algorithm.

    Returns list of (bar_index, price, kind) tuples in chronological order,
    where kind is 'H' (pivot high) or 'L' (pivot low).

    Algorithm: maintain a "running extreme" in the current trend direction.
    A pivot confirms when price moves >= dev_pct against the trend from the
    running extreme. Only confirmed pivots are returned (the unconfirmed
    running extreme at the end is excluded).
    """
    if df is None or len(df) < 10:
        return []

    high = df["High"].to_numpy(float)
    low  = df["Low"].to_numpy(float)
    n = len(high)
    threshold = dev_pct / 100.0

    pivots = []  # list of (bar_idx, price, 'H'|'L')

    # Phase 1 — establish initial direction.
    # Track BOTH the running highest high and the running lowest low until we
    # see a move large enough to flip direction. Whichever extreme came first
    # becomes the first pivot.
    hi_idx, hi_price = 0, high[0]
    lo_idx, lo_price = 0, low[0]
    direction = None

    i = 1
    while i < n and direction is None:
        if high[i] > hi_price:
            hi_idx, hi_price = i, high[i]
        if low[i] < lo_price:
            lo_idx, lo_price = i, low[i]
        # Did the running high drop enough to confirm direction = down?
        if low[i] <= hi_price * (1 - threshold) and hi_idx < i:
            # The high was set BEFORE this drop. Confirm hi as first pivot.
            pivots.append((hi_idx, hi_price, 'H'))
            direction = 'down'
            ext_idx, ext_price = lo_idx, lo_price
            # Continue from here in phase 2
        # Or did the running low rise enough to confirm direction = up?
        elif high[i] >= lo_price * (1 + threshold) and lo_idx < i:
            pivots.append((lo_idx, lo_price, 'L'))
            direction = 'up'
            ext_idx, ext_price = hi_idx, hi_price
        i += 1

    # If we never established direction, no confirmed pivots
    if direction is None:
        return []

    # Phase 2 — track the running extreme in current direction; flip on reversal
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
      "Triggered T2"     — last close > 0.68, less than recent_bars old (or current bar provisional)
      "Triggered T1"     — last close > 0.382, less than recent_bars old (or current bar provisional)
      "Active T2"        — In T2, triggered older than recent_bars
      "Active T1"        — In T1, triggered older than recent_bars
      "In Zone T2"       — between 0.618 and 0.68 (T1 played, waiting for T2 entry)
      "In Zone T1"       — between 0.32 and 0.382 (waiting for T1 entry)
      "Approaching T1"   — below 0.32, within APPROACH_BAND_PCT
      None               — outside our band of interest, or fully played

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

    # Active trade context
    if state == 2:
        # In T1
        bars_since = bar_idx - sim["t1_entry_bar"] if sim["t1_entry_bar"] is not None else 999
        if bars_since < recent_bars:
            return ("Triggered T1", "T1", False, sim["t1_entry_bar"], ltp)
        return ("Active T1", "T1", False, sim["t1_entry_bar"], ltp)

    if state == 4:
        bars_since = bar_idx - sim["t2_entry_bar"] if sim["t2_entry_bar"] is not None else 999
        if bars_since < recent_bars:
            return ("Triggered T2", "T2", False, sim["t2_entry_bar"], ltp)
        return ("Active T2", "T2", False, sim["t2_entry_bar"], ltp)

    if state == 5:
        # Fully played — not surfaced in scanner (only Performance tab)
        return None

    # Waiting states (1 or 3) — check provisional triggers + zone position
    if state == 3:
        # Waiting T2 entry
        if ltp > t1_hi:
            # Provisional T2 trigger (bar still forming, price above 0.68)
            return ("Triggered T2", "T2", True, bar_idx, ltp)
        if t1_lo <= ltp <= t1_hi:
            return ("In Zone T2", "T2", False, None, ltp)
        # Below 0.618 — Approaching T2? Not in spec, skip.
        return None

    if state == 1:
        # Waiting T1 entry. But price might have raced higher without triggering
        # (e.g. weak volume on the breakout, so state machine didn't advance).
        # Classify based on where price currently sits.
        if ltp > t1_hi:
            # Provisional T2 trigger via jump-in
            return ("Triggered T2", "T2", True, bar_idx, ltp)
        if t1_lo <= ltp <= t1_hi:
            # Price is in T2 entry zone (provisional — T1 didn't formally trigger)
            return ("In Zone T2", "T2", False, None, ltp)
        if ltp > e1_hi:
            # Provisional T1 trigger
            return ("Triggered T1", "T1", True, bar_idx, ltp)
        if e1_lo <= ltp <= e1_hi:
            return ("In Zone T1", "T1", False, None, ltp)
        if ltp < e1_lo and ltp >= e1_lo * (1 - APPROACH_BAND_PCT):
            return ("Approaching T1", "T1", False, None, ltp)
        return None

    return None


# ============================================================================
# PER-STOCK ANALYSIS
# ============================================================================

def analyze_one(symbol, tf, dev_pct=DEV_PCT_DEFAULT):
    """Analyze one symbol at one timeframe. Returns row dict or None."""
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

    return dict(
        sym=symbol, tf=tf,
        signal=signal, active_trade=active_trade, provisional=provisional,
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
# SCANNING — iterate over the universe
# ============================================================================

def scan(symbols, timeframes=("1D", "1W"), dev_pct=DEV_PCT_DEFAULT, verbose=False):
    """Scan a list of symbols across given timeframes. Returns DataFrame."""
    rows = []
    for s in symbols:
        for tf in timeframes:
            try:
                r = analyze_one(s, tf, dev_pct=dev_pct)
                if r:
                    rows.append(r)
            except Exception as e:
                if verbose:
                    print(f"skip {s} {tf} - {e}")
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


# ============================================================================
# OUTPUT — results.json for the dashboard
# ============================================================================

def save_dashboard_json(df, path="results.json", deviation=DEV_PCT_DEFAULT, sectors=None):
    """Write the scan results in the dashboard's expected schema."""
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
    data = {
        "generated_at": now_ist.isoformat(timespec="seconds"),
        "generated_label": now_ist.strftime("%H:%M IST · %d %b"),
        "deviation": deviation,
        "rows": rows,
    }
    # allow_nan=False so any NaN that sneaks through fails loudly rather than producing invalid JSON
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

