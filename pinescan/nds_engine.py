"""
nds_engine — faithful port of "Nested Daily Short V1.1" (the short-only mirror of NDL V2.1).
============================================================================================

Everything is the long engine reversed, per the Pine (New Scripts/
nested_daily_short_v1_1_pinescript.txt):

  * B  = the HIGHEST HIGH of the most recent confirmed rally of >= minRallyPct
         (up-leg END in the coarse ZigZag), instead of the decline's lowest low.
  * A0..A3 = nested TROUGHS below B, nearest-first walking back from B; min-gap
         keeps the LOWER of two close troughs; a HIGH above B halts the walk.
  * Fib ladder measured DOWN from B:  level = B - fib * (B - A)
         0.236 -> stop (ABOVE entry), 0.32-0.382 -> entry zone (trigger = confirmed
         close BELOW the 0.382 level), 0.618-0.68 -> target zone (first touch of
         0.618 going down).
  * Entry filters mirrored: close < EMA9 & EMA21, volume > 1.2x 20-bar avg.
  * V1.1 rules are BUILT IN (no legacy toggle — there are no legacy short goldens):
      - retire-missed: a WAITING short whose whole target zone price closed BELOW
        -> terminal state 4;
      - seed-pivot fix: the oldest point's geometric flag is trusted (this
        detector computes real directions, matching the Pine V1.1 inference).

Chart-verified by scripts/verify_nds.py against the four instrumented NSE exports
(PPLPHARMA / INTELLECT / POONAWALLA / BBTC, fixtures/golden_csv/).
"""
import numpy as np
import pandas as pd

from pinescan.core import runtime as rt
from pinescan.nsv2_engine import _Pivots, _col

DEFAULTS = {
    "minRallyPct": 35.0,     # sets B (qualifying rally depth)
    "pivotSensPct": 25.0,    # finds nested troughs (finer)
    "zigDepth": 10,
    "maxSwings": 4,
    "minGapPct": 8.0,
    "fib_sl": 0.236,
    "fib_eL": 0.32,          # entry zone NEAR fib (upper price for shorts)
    "fib_eH": 0.382,         # entry zone FAR fib (lower price = the trigger)
    "fib_tL": 0.618,         # target NEAR fib (upper price, first touch)
    "fib_tH": 0.68,          # target FAR fib (lower price)
    "emaFast": 9,
    "emaSlow": 21,
    "volAvg": 20,
    "volMult": 1.2,
    "useEmaFilter": True,
    "useVolFilter": True,
}


# ---------------------------------------------------------------------------
# B detection — end of the most recent UP-leg (Pine short 131-144)
# ---------------------------------------------------------------------------
def _b_from_points(points):
    """Latest up-leg's end (its high). Mirror of the long engine's `_b_from_points`."""
    fb = fbt = None
    for i in range(len(points) - 1):
        s_idx, s_price, _ = points[i]
        e_idx, e_price, _ = points[i + 1]
        if e_price > s_price:                       # up-swing -> its end is the high
            fb, fbt = e_price, e_idx
    return None if fb is None else (fb, fbt)


# ---------------------------------------------------------------------------
# nested-trough walk — nearest-first from B (Pine short 149-233, V1.1 seed fix)
# ---------------------------------------------------------------------------
def _nested_troughs(points, b_price, b_idx, min_gap_pct, max_swings):
    """Walk the pivot points newest->oldest keeping the staircase of nested troughs
    BELOW B. Mirror of `_nested_peaks`:
      * only points strictly older than B,
      * a LOW counts only if price < B * (1 - minGap%),
      * first kept low = T1 (nearest trough below B),
      * clearly lower (< lastKept * gapMul) -> NEW trough; within the gap but lower
        -> REPLACES the last kept (keep the lower),
      * a HIGH above B halts the walk (a different rally),
      * seed-pivot fix built in: the oldest point keeps its geometric flag.
    """
    gap_mul = 1.0 - min_gap_pct / 100.0
    k = [None, None, None, None]
    kt = [None, None, None, None]
    last_kept = None
    kept = 0
    n = len(points)
    for j in range(n):
        idx = n - 1 - j                              # newest first
        t = points[idx][0]
        if t < b_idx:
            pr = points[idx][1]
            is_low = not points[idx][2]
            if is_low:
                if pr < b_price * gap_mul:
                    if last_kept is None:
                        k[0], kt[0] = pr, t          # T1 = nearest trough below B
                        last_kept = pr
                        kept = 1
                    elif pr < last_kept * gap_mul:   # clearly lower -> new trough
                        if kept == 1:
                            k[1], kt[1] = pr, t
                        elif kept == 2:
                            k[2], kt[2] = pr, t
                        elif kept == 3:
                            k[3], kt[3] = pr, t
                        last_kept = pr
                        kept += 1
                    elif pr < last_kept:             # within gap -> keep lower
                        if kept == 1:
                            k[0], kt[0] = pr, t
                        elif kept == 2:
                            k[1], kt[1] = pr, t
                        elif kept == 3:
                            k[2], kt[2] = pr, t
                        elif kept == 4:
                            k[3], kt[3] = pr, t
                        last_kept = pr
            else:
                if pr > b_price:
                    break                            # higher high -> stop
            if kept >= max_swings:
                break
    troughs = [(k[i], kt[i]) for i in range(kept)]
    return troughs, kept


# ---------------------------------------------------------------------------
# fib levels + per-swing state machine (Pine short 256-294)
# ---------------------------------------------------------------------------
def swing_levels(a_price, b_price, params=DEFAULTS):
    """Levels measured DOWN from B. Keys keep the registry contract's price
    semantics: eL/tL are the LOWER prices, eH/tH the higher; sl sits ABOVE."""
    r = b_price - a_price
    return {
        "sl": b_price - params["fib_sl"] * r,
        "eH": b_price - params["fib_eL"] * r,        # 0.32 -> upper edge
        "eL": b_price - params["fib_eH"] * r,        # 0.382 -> lower edge = trigger
        "tH": b_price - params["fib_tL"] * r,        # 0.618 -> upper edge (first touch)
        "tL": b_price - params["fib_tH"] * r,        # 0.68  -> lower edge
    }


def step_trade(s, e_lo, t_hi, sl, e_ok, v_ok, close, close_prev, low):
    """One short trade's wait(1)->IN(2)->TP(3) machine for one bar. Entry on a
    confirmed close crossing e_lo (0.382 level) FROM ABOVE + filters; TP when low
    reaches t_hi (0.618); SL on close > sl (0.236) -> re-arm. 3 is terminal."""
    ns = s
    e_fire = tp_fire = sl_fire = False
    cross_e = (not rt.is_na(e_lo)) and close < e_lo and (not rt.is_na(close_prev)) and close_prev >= e_lo
    if s == 1 and cross_e and e_ok and v_ok:
        ns = 2
        e_fire = True
    elif s == 2:
        if (not rt.is_na(t_hi)) and low <= t_hi:
            ns = 3
            tp_fire = True
        elif (not rt.is_na(sl)) and close > sl:
            ns = 1
            sl_fire = True
    return ns, e_fire, tp_fire, sl_fire


# ---------------------------------------------------------------------------
# driver — replay the whole indicator bar-by-bar
# ---------------------------------------------------------------------------
def run(df, params=None):
    """Replay the short indicator over `df`; returns the instrumented series
    (same keys/columns as the long engine: B, A0..A3, ST0..ST3, ENTRY/TP/SL, EMAs)."""
    p = dict(DEFAULTS)
    if params:
        p.update(params)
    nan = float("nan")

    close = _col(df, "close", "Close")
    high = _col(df, "high", "High")
    low = _col(df, "low", "Low")
    try:
        volume = _col(df, "volume", "Volume")
    except KeyError:
        volume = np.full(len(close), nan)
    n = len(close)

    ema9 = rt.ema(close.tolist(), p["emaFast"])
    ema21 = rt.ema(close.tolist(), p["emaSlow"])
    vol_sma = rt.sma(volume.tolist(), p["volAvg"])
    high_l, low_l = high.tolist(), low.tolist()

    piv_b = _Pivots(p["zigDepth"], p["minRallyPct"])
    piv_p = _Pivots(p["zigDepth"], p["pivotSensPct"])

    B_price = None
    B_time = None
    A = [None, None, None, None]
    st = [0, 0, 0, 0]
    state_for_b = None

    out = {key: [nan] * n for key in
           ("EMA 9", "EMA 21", "B", "A0", "A1", "A2", "A3",
            "ST0", "ST1", "ST2", "ST3", "ENTRY", "TP", "SL")}

    for k in range(n):
        piv_b.update(high_l, low_l, k)
        piv_p.update(high_l, low_l, k)

        # --- B detection (latest confirmed >= minRally% up-leg) ---
        b_pts = piv_b.points()
        if len(b_pts) >= 1:
            bres = _b_from_points(b_pts)
            if bres is not None:
                fb, fbt = bres
                if B_time is None or fbt != B_time:
                    B_price, B_time = fb, fbt

        has_b = B_price is not None

        # --- nested troughs ---
        if has_b:
            p_pts = piv_p.points()
            if len(p_pts) >= 1:
                troughs, kept = _nested_troughs(p_pts, B_price, B_time,
                                                p["minGapPct"], p["maxSwings"])
                A = [None, None, None, None]
                for i in range(kept):
                    A[i] = troughs[i][0]

        # --- state reset on new B ---
        if has_b and (state_for_b is None or B_time != state_for_b):
            state_for_b = B_time
            st = [1, 1, 1, 1]

        # --- filters (mirrored: close BELOW both EMAs) ---
        c = close[k]
        ema_ok = (not p["useEmaFilter"]) or (
            (not rt.is_na(ema9[k]) and c < ema9[k]) and
            (not rt.is_na(ema21[k]) and c < ema21[k]))
        vs = vol_sma[k]
        vol_ok = (not p["useVolFilter"]) or (
            (not rt.is_na(vs)) and (not rt.is_na(volume[k])) and volume[k] > vs * p["volMult"])

        # --- per-swing state machine (historical bars are confirmed) ---
        any_e = any_t = any_x = False
        if has_b:
            c_prev = close[k - 1] if k > 0 else nan
            for i in range(4):
                if A[i] is None:
                    continue
                lv = swing_levels(A[i], B_price, p)
                ns_, ef, tf, sf = step_trade(st[i], lv["eL"], lv["tH"], lv["sl"],
                                             ema_ok, vol_ok, c, c_prev, low[k])
                st[i] = ns_
                # V1.1: retire a MISSED short — still WAITING while price closed below
                # its whole target zone; terminal state 4, the spotlight moves on.
                if st[i] == 1 and c < lv["tL"]:
                    st[i] = 4
                any_e = any_e or ef
                any_t = any_t or tf
                any_x = any_x or sf

        # --- record instrumented series ---
        out["EMA 9"][k] = ema9[k]
        out["EMA 21"][k] = ema21[k]
        for i in range(4):
            out[f"ST{i}"][k] = float(st[i])
        if has_b:
            out["B"][k] = B_price
            for i in range(4):
                if A[i] is not None:
                    out[f"A{i}"][k] = A[i]
        if any_e:
            out["ENTRY"][k] = 1.0
        if any_t:
            out["TP"][k] = 1.0
        if any_x:
            out["SL"][k] = 1.0

    return out
