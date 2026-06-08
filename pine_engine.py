"""
pine_engine.py — faithful Python replica of the Pine indicator
==============================================================

Reproduces the trade logic in `zigzag_kb_fib_dual_trade.pine` ("ZigZag KB Fib
Dual Trade"). Pivot detection is delegated to `tv_zigzag.py`, a faithful port of
the real `TradingView/ZigZag` library (the indicator imports
`TradingView/ZigZag/7`). This module then layers the indicator's own logic on top
of those confirmed pivots:

  * recent A->B down-swing selection (latest High->Low pivot pair),
  * the indicator's B-invalidation (lower B to a new low while pre-entry),
  * the dual-trade state machine (T1/T2 entries, TPs, SLs, jump-in),
  * EMA9/21 + 1.2x-volume + cross-from-below entry confirmation.

NO-LOOKAHEAD: a ZigZag pivot at bar i is only *confirmed* `eff_depth` bars later
(`eff_depth = max(2, floor(depth/2))`), so a swing's state machine is simulated
only from the bar B is confirmed — never earlier. This matches the live chart.

THE ONE INTENTIONAL DEVIATION FROM PINE — the kept scanner feature: Pine acts
only on confirmed (closed) bars. To notify a trade *before the daily close*,
`evaluate()` can append a live "today-so-far" bar and evaluate it; any event
fired on that bar is tagged `provisional=True` until the close locks it.

History: an earlier version of this file *reconstructed* the ZigZag from
assumptions (a running-extreme deviation tracker, `depth=10` as a min-bars gate)
and diverged from the chart. See PINE_PORTING_NOTES.md / PINE_PORTING.md.
"""
import math
import datetime as dt

import numpy as np
import pandas as pd

import tv_zigzag

# ============================================================================
# CONFIG — mirror the Pine inputs
# ============================================================================
FIB_SL1 = 0.236     # T1 stop-loss line
FIB_E1L = 0.32      # T1 entry zone low
FIB_E1H = 0.382     # T1 entry zone high  (the T1 trigger)
FIB_T1L = 0.618     # T1 TP / T2 entry low  (also T2 stop)
FIB_T1H = 0.68      # T1 TP / T2 entry high (the T2 trigger)
FIB_T2L = 1.00      # T2 TP low (= A)
FIB_T2H = 1.05      # T2 TP high

EMA_FAST = 9
EMA_SLOW = 21
VOL_AVG = 20
VOL_MULT = 1.2

DEV_PCT_DEFAULT = 35.0     # pricePctDeviation (US default overridden in run_scan_us.py)
ZIG_DEPTH = 10             # zigDepth input — HALVED internally by the library

USE_EMA_FILTER = True
USE_VOL_FILTER = True

APPROACH_BAND_PCT = 0.05   # how far below the entry zone still counts as "approaching"

EVENTS = ("t1_entry", "t1_tp", "t1_sl", "t2_entry", "t2_tp", "t2_sl")
_SIGNAL_LABEL = {
    "t1_entry": "T1 Entry", "t2_entry": "T2 Entry",
    "t1_tp": "T1 TP", "t2_tp": "T2 TP",
    "t1_sl": "T1 SL", "t2_sl": "T2 SL",
}
_STATE_LABEL = {1: "Waiting T1", 2: "In Trade 1", 3: "Waiting T2", 4: "In Trade 2"}


def _eff_depth(depth_setting):
    """The library halves the depth input (tradingview_zigzag_v9.pine:477)."""
    return max(2, math.floor(depth_setting / 2))


def _levels(a_price, b_price):
    """Fib levels off the (A - B) range, measured up from B."""
    rng = a_price - b_price
    return {
        "rng": rng,
        "sl1": b_price + FIB_SL1 * rng,
        "e1L": b_price + FIB_E1L * rng, "e1H": b_price + FIB_E1H * rng,
        "t1L": b_price + FIB_T1L * rng, "t1H": b_price + FIB_T1H * rng,
        "t2L": b_price + FIB_T2L * rng, "t2H": b_price + FIB_T2H * rng,
    }


def _recent_downswing(pivots):
    """Latest High->Low pivot pair → (a_idx, a_price, b_idx, b_price), or None.
    `pivots` is the tv_zigzag list of (bar_idx, price, is_high)."""
    for j in range(len(pivots) - 1, 0, -1):
        if (not pivots[j][2]) and pivots[j - 1][2]:
            return pivots[j - 1][0], pivots[j - 1][1], pivots[j][0], pivots[j][1]
    return None


def _macro(pivots, recent_b_idx):
    """Highest pivot → lowest pivot after it (context only)."""
    if not pivots:
        return None, None
    a_i = max(range(len(pivots)), key=lambda i: pivots[i][1])
    after = pivots[a_i + 1:]
    if not after:
        return None, None
    b = min(after, key=lambda p: p[1])
    if b[0] == recent_b_idx:
        return None, None
    return float(pivots[a_i][1]), float(b[1])


# ============================================================================
# STATE MACHINE — one swing, bar-by-bar (shared by scanner + backtest)
# ============================================================================

def _walk(close, high, low, vol, ema9, ema21, vol_sma,
          a_price, b_idx, b_price, eff_depth, end_bar, invalidate):
    """Run the dual-trade machine over ONE swing, from B-confirmation to end_bar.

    Returns dict: state, last_event, last_event_bar, entry_bar (open trade's),
    lv (final levels), b_eff (final B after any invalidation), trades (list of
    completed-trade dicts with bar indices — caller fills dates/sym/tf).
    """
    n = len(close)
    start = b_idx + eff_depth          # B is only known eff_depth bars later
    end_bar = min(end_bar, n - 1)
    state = 1
    t1_trig = False
    t1_entry_bar = t2_entry_bar = None
    b_eff = b_price
    lv = _levels(a_price, b_eff)
    trades = []
    last_event = last_event_bar = None

    def trade(tt, eb, ep, xb, xp, outcome, r):
        trades.append({"trade_type": tt, "entry_bar": eb, "entry_price": round(ep, 2),
                       "exit_bar": xb, "exit_price": round(xp, 2), "outcome": outcome,
                       "r_multiple": round(r, 2), "A": round(a_price, 2), "B": round(b_eff, 2)})

    if start > end_bar:
        return dict(state=0, last_event=None, last_event_bar=None, entry_bar=None,
                    lv=lv, b_eff=b_eff, trades=trades)

    for k in range(start, end_bar + 1):
        c = close[k]
        c_prev = close[k - 1] if k > 0 else c
        h = high[k]
        # B-invalidation (live indicator): lower B to today's low while pre-entry
        if invalidate and state <= 1 and c < b_eff and low[k] < b_eff:
            b_eff = low[k]
            lv = _levels(a_price, b_eff)
            state = 1
        ema_ok = (not USE_EMA_FILTER) or (c > ema9[k] and c > ema21[k])
        vol_ok = (not USE_VOL_FILTER) or (vol[k] > vol_sma[k] * VOL_MULT)   # NaN→False
        crossed_382 = c > lv["e1H"] and c_prev <= lv["e1H"]
        crossed_68 = c > lv["t1H"] and c_prev <= lv["t1H"]
        event = None

        if state == 1:
            if crossed_68 and ema_ok and vol_ok:           # jump-in straight to T2
                state = 4
                t2_entry_bar = k
                event = "t2_entry"
            elif crossed_382 and ema_ok and vol_ok:
                state = 2
                t1_trig = True
                t1_entry_bar = k
                event = "t1_entry"
        elif state == 2:
            if h >= lv["t1L"]:                              # T1 TP
                risk = lv["e1H"] - lv["sl1"]
                r = (lv["t1L"] - lv["e1H"]) / risk if risk > 0 else 0.0
                trade("T1", t1_entry_bar, lv["e1H"], k, lv["t1L"], "win", r)
                state = 3
                event = "t1_tp"
            elif c < lv["sl1"]:                             # T1 SL
                trade("T1", t1_entry_bar, lv["e1H"], k, lv["sl1"], "loss", -1.0)
                state = 1
                t1_entry_bar = None
                event = "t1_sl"
        elif state == 3:
            if crossed_68 and ema_ok and vol_ok:
                state = 4
                t2_entry_bar = k
                event = "t2_entry"
        elif state == 4:
            if h >= lv["t2L"]:                              # T2 TP
                risk = lv["t1H"] - lv["t1L"]
                r = (lv["t2L"] - lv["t1H"]) / risk if risk > 0 else 0.0
                trade("T2", t2_entry_bar, lv["t1H"], k, lv["t2L"], "win", r)
                state = 5
                event = "t2_tp"
            elif c < lv["t1L"]:                             # T2 SL (close < 0.618)
                trade("T2", t2_entry_bar, lv["t1H"], k, lv["t1L"], "loss", -1.0)
                state = 3 if t1_trig else 1
                t2_entry_bar = None
                event = "t2_sl"

        if event:
            last_event, last_event_bar = event, k
        if state == 5:
            break

    entry_bar = t1_entry_bar if state == 2 else (t2_entry_bar if state == 4 else None)
    return dict(state=state, last_event=last_event, last_event_bar=last_event_bar,
                entry_bar=entry_bar, lv=lv, b_eff=b_eff, trades=trades)


def _prep(df):
    """Extract arrays + indicators once."""
    close = df["Close"].to_numpy(float)
    high = df["High"].to_numpy(float)
    low = df["Low"].to_numpy(float)
    vol = df["Volume"].to_numpy(float)
    ema9 = pd.Series(close).ewm(span=EMA_FAST, adjust=False).mean().to_numpy()
    ema21 = pd.Series(close).ewm(span=EMA_SLOW, adjust=False).mean().to_numpy()
    vol_sma = pd.Series(vol).rolling(VOL_AVG, min_periods=VOL_AVG).mean().to_numpy()
    return close, high, low, vol, ema9, ema21, vol_sma


# ============================================================================
# SCANNER — current state of one symbol/timeframe (live, with intraday hook)
# ============================================================================

def evaluate(sym, tf, daily_df, today_partial=None, partial_is_live=True,
             dev_pct=DEV_PCT_DEFAULT, depth=ZIG_DEPTH):
    """Faithful per-symbol scan. Returns a dashboard row dict, or None."""
    if daily_df is None or len(daily_df) < 30:
        return None

    df = daily_df
    last_is_partial = False
    if today_partial is not None and len(today_partial) > 0:
        df = pd.concat([daily_df, today_partial])
        last_is_partial = True

    close, high, low, vol, ema9, ema21, vol_sma = _prep(df)
    n = len(close)
    pivots = tv_zigzag.detect_pivots(high.tolist(), low.tolist(), depth, dev_pct)
    recent = _recent_downswing(pivots)
    if recent is None:
        return None
    ai, ap, bi, bp = recent
    eff = _eff_depth(depth)

    res = _walk(close, high, low, vol, ema9, ema21, vol_sma,
                ap, bi, bp, eff, n - 1, invalidate=True)
    state = res["state"]
    event = res["last_event"] if res["last_event_bar"] == n - 1 else None
    if event is None and state not in (1, 2, 3, 4):
        return None

    lv = res["lv"]
    b_eff = res["b_eff"]
    ltp = float(close[-1])
    provisional = bool(last_is_partial and partial_is_live and
                       (res["last_event_bar"] == n - 1 or state in (2, 4)))

    active_trade = "T2" if (state in (3, 4) or (event or "").startswith("t2")) else "T1"
    if event:
        signal = _SIGNAL_LABEL[event]
        action = ("Enter" if event.endswith("entry")
                  else "Target" if event.endswith("tp") else "Stop")
    else:
        signal = _STATE_LABEL[state]
        action = "Holding" if state in (2, 4) else "Watch"

    if active_trade == "T1":
        risk, reward = lv["e1H"] - lv["sl1"], lv["t1L"] - lv["e1H"]
    else:
        risk, reward = lv["t1H"] - lv["t1L"], lv["t2L"] - lv["t1H"]
    rr = round(reward / risk, 2) if risk > 0 else None

    entry_lo, entry_hi = ((lv["e1L"], lv["e1H"]) if active_trade == "T1"
                          else (lv["t1L"], lv["t1H"]))
    in_band = bool(entry_lo <= ltp <= entry_hi)
    approaching = bool(ltp < entry_lo and ltp >= entry_lo * (1 - APPROACH_BAND_PCT))

    confirmed_at = None
    idx = res["last_event_bar"] if event else res["entry_bar"]
    if idx is not None and idx < n:
        try:
            confirmed_at = df.index[idx].isoformat()
        except Exception:
            confirmed_at = None

    macro_a, macro_b = _macro(pivots, bi)
    a, b = float(ap), float(b_eff)
    drop_pct = (a - b) / a * 100.0 if a else 0.0
    vx = (vol[-1] / vol_sma[-1]) if (vol_sma[-1] and not np.isnan(vol_sma[-1])) else 0.0

    return {
        "sym": sym, "tf": tf,
        "signal": signal, "action": action, "active_trade": active_trade,
        "provisional": provisional, "in_band": in_band, "approaching": approaching,
        "A": round(a, 2), "B": round(b, 2), "drop_pct": round(drop_pct, 2),
        "ltp": round(ltp, 2),
        "t1_entry_lo": round(lv["e1L"], 2), "t1_entry_hi": round(lv["e1H"], 2),
        "t1_tp_lo": round(lv["t1L"], 2), "t1_tp_hi": round(lv["t1H"], 2),
        "t1_sl": round(lv["sl1"], 2),
        "t2_entry_lo": round(lv["t1L"], 2), "t2_entry_hi": round(lv["t1H"], 2),
        "t2_tp_lo": round(lv["t2L"], 2), "t2_tp_hi": round(lv["t2H"], 2),
        "t2_sl": round(lv["t1L"], 2),
        "ema_ok": bool(ltp > ema9[-1] and ltp > ema21[-1]),
        "vol_ok": bool(vol[-1] > vol_sma[-1] * VOL_MULT) if not np.isnan(vol_sma[-1]) else False,
        "vol_x": round(float(vx), 1), "rr": rr,
        "confirmed_at": confirmed_at,
        "macro_a": round(macro_a, 2) if macro_a else None,
        "macro_b": round(macro_b, 2) if macro_b else None,
    }


# ============================================================================
# BACKTEST — walk every confirmed swing, collect completed trades
# ============================================================================

def backtest(daily_df, dev_pct=DEV_PCT_DEFAULT, depth=ZIG_DEPTH, window_days=None):
    """Historical trades for one symbol/timeframe (no intraday partial)."""
    if daily_df is None or len(daily_df) < 30:
        return []
    close, high, low, vol, ema9, ema21, vol_sma = _prep(daily_df)
    n = len(close)
    pivots = tv_zigzag.detect_pivots(high.tolist(), low.tolist(), depth, dev_pct)
    eff = _eff_depth(depth)

    all_trades = []
    for j in range(1, len(pivots)):
        if pivots[j][2] or not pivots[j - 1][2]:
            continue                                   # need H (j-1) -> L (j)
        ai, ap, _ = pivots[j - 1]
        bi, bp, _ = pivots[j]
        # Swing dies when a later pivot makes a lower low (new down-swing forms).
        end_bar = n - 1
        for k in range(j + 1, len(pivots)):
            if (not pivots[k][2]) and pivots[k][1] < bp:
                end_bar = pivots[k][0] - 1
                break
        res = _walk(close, high, low, vol, ema9, ema21, vol_sma,
                    ap, bi, bp, eff, end_bar, invalidate=False)
        for t in res["trades"]:
            t["entry_date"] = daily_df.index[t["entry_bar"]].isoformat() if t["entry_bar"] is not None else None
            t["exit_date"] = daily_df.index[t["exit_bar"]].isoformat()
        all_trades.extend(res["trades"])

    if window_days is not None and all_trades:
        cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=window_days)

        def _within(t):
            try:
                d = dt.datetime.fromisoformat(t["entry_date"].replace("Z", "+00:00"))
                if d.tzinfo is None:
                    d = d.replace(tzinfo=dt.timezone.utc)
                return d >= cutoff
            except Exception:
                return True
        all_trades = [t for t in all_trades if _within(t)]
    return all_trades


# ============================================================================
# SELF-TEST
# ============================================================================
if __name__ == "__main__":
    # Lead-in so A is a real confirmed pivot, then a clean A->B->rally.
    base = [60, 62, 64, 66, 70, 80, 92, 100]              # rise into A (=100)
    down = list(np.linspace(100, 50, 14))[1:]             # A->B (B=50), ~14 bars
    rally = list(np.linspace(50.5, 110, 45))              # rally past A
    px = base + down + rally
    idx = pd.date_range("2024-01-01", periods=len(px), freq="D", tz="UTC")
    data = pd.DataFrame({
        "Open": px, "High": [p * 1.01 for p in px], "Low": [p * 0.99 for p in px],
        "Close": px, "Volume": [1e6] * (len(base) + len(down)) + list(np.linspace(3e6, 30e6, 45)),
    }, index=idx)
    tr = backtest(data, dev_pct=15.0)
    print(f"backtest trades: {len(tr)}")
    for t in tr:
        print(f"  {t['trade_type']} {t['outcome']} R={t['r_multiple']:+.2f} "
              f"entry={t['entry_price']} exit={t['exit_price']}")
    row = evaluate("TEST", "1D", data, dev_pct=15.0)
    print("scanner:", None if not row else f"{row['signal']} / {row['action']} A={row['A']} B={row['B']}")
