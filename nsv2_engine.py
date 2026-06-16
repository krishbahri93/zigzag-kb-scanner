"""
nsv2_engine.py — faithful Python replica of "ZZ KB Nested Swings V2"
===================================================================

Ports `zigzag_kb_Indicator_nested_v2_pinescript.txt` (Pine v6). Pivot detection
is delegated to `tv_zigzag.py`, the chart-verified port of the imported
`TradingView/ZigZag/7` library — the SAME dependency already cleared for the
dual-trade engine, so no new library source is needed.

What V2 does differently from the dual-trade engine (`pine_engine.py`):
  * TWO ZigZag instances — `zzB` at devThreshold = Min Decline % (default 35,
    deep declines only) sets the common low B; `zzP` at Peak Sensitivity %
    (default 25, finer) finds the nested peaks.
  * B = the END of the most recent down-leg (latest confirmed low).
  * Nested peaks are found nearest-first walking back from B, with a min-gap
    "keep the higher of two close peaks" rule, a B*gapMul floor, a
    stop-at-any-low-below-B rule, and a maxSwings cap (up to T1..T4).
  * Each swing runs an INDEPENDENT wait->IN->TP/SL state machine (entry on a
    confirmed close crossing 0.382 from below + EMA9/21 + 1.2x-vol; TP when
    high reaches 0.618; SL when close < 0.236; SL re-arms, TP is terminal).

NO-LOOKAHEAD: pivots are streamed bar-by-bar (`_Pivots`), reproducing
`zz.pivots` exactly as the live chart has it on each bar — a pivot at bar i is
only known `eff_depth = max(2, floor(depth/2))` bars later. The detection and
state machine are replayed in that same forward pass; nothing reads the future.

Pine line map (zigzag_kb_Indicator_nested_v2_pinescript.txt):
  Settings.new / update      :83-96   -> two _Pivots (dev 35 / 25, depth 10)
  B detection (down-leg end) :124-137 -> _b_from_points
  nested-peak walk           :141-226 -> _nested_peaks
  state reset on new B       :233-241 -> run() (stateForB)
  swingLevels                :244-251 -> swing_levels
  filters                    :258-261 -> run() (ema/vol)
  stepTrade                  :264-280 -> step_trade
"""
import math

import numpy as np
import pandas as pd

import tv_zigzag
from pine_port import runtime as rt


# ---------------------------------------------------------------------------
# inputs (Pine input.* defaults)
# ---------------------------------------------------------------------------
DEFAULTS = {
    "minDeclinePct": 35.0,   # zzB devThreshold — sets B / which declines qualify
    "pivotSensPct": 25.0,    # zzP devThreshold — finds nested peaks
    "zigDepth": 10,          # depth input (HALVED internally by the library)
    "maxSwings": 4,
    "minGapPct": 8.0,
    "fib_sl": 0.236,
    "fib_eL": 0.32,
    "fib_eH": 0.382,
    "fib_tL": 0.618,
    "fib_tH": 0.68,
    "emaFast": 9,
    "emaSlow": 21,
    "volAvg": 20,
    "volMult": 1.2,
    "useEmaFilter": True,
    "useVolFilter": True,
}


# ---------------------------------------------------------------------------
# streaming ZigZag — reproduces zz.pivots bar-by-bar (no lookahead)
# ---------------------------------------------------------------------------
class _Pivots:
    """One ZigZag instance, advanced one bar at a time. `update(high, low, k)`
    mirrors `tryFindPivot(high, true)` then `tryFindPivot(low, false)` for bar k
    and `newPivotPointFound`'s update-vs-register logic — identical to the loop
    body inside `tv_zigzag.detect_pivots`, so after bar k `.points()` equals the
    detector's output over bars 0..k.
    """

    def __init__(self, depth_setting, dev_threshold, allow_one_bar=True):
        self.depth = max(2, math.floor(depth_setting / 2))   # the halving (P:477)
        self.dev = dev_threshold
        self.allow = allow_one_bar
        self.pivots = []   # [bar_index, price, is_high] per confirmed pivot END

    def _register(self, point, is_high):
        idx, price = point
        if self.pivots:
            last = self.pivots[-1]
            last_idx, last_price, last_is_high = last
            if last_is_high == is_high:
                m = 1 if is_high else -1
                if price * m > last_price * m:               # isMorePrice
                    last[0], last[1] = idx, price
            else:
                dev = tv_zigzag._calc_dev(last_price, price)
                if (not last_is_high and dev >= self.dev) or \
                   (last_is_high and dev <= -self.dev):
                    self.pivots.append([idx, price, is_high])
        else:
            self.pivots.append([idx, price, is_high])

    def update(self, high, low, k):
        hp = tv_zigzag._find_pivot_point(high, k, self.depth, True)
        new_high = hp is not None
        if new_high:
            self._register(hp, True)
        register_low = self.allow or not new_high
        lp = tv_zigzag._find_pivot_point(low, k, self.depth, False)
        if lp is not None and register_low:
            self._register(lp, False)

    def points(self):
        return [(i, p, h) for i, p, h in self.pivots]


# ---------------------------------------------------------------------------
# B detection — end of the most recent down-leg  (Pine 124-137)
# ---------------------------------------------------------------------------
def _b_from_points(points):
    """Latest down-leg's end (its low). `points` is the alternating pivot list
    [(bar_idx, price, is_high), ...]; a down-leg is a consecutive pair whose end
    price is below its start price. Returns (b_price, b_idx) or None."""
    fb = fbt = None
    for i in range(len(points) - 1):
        start = points[i]
        end = points[i + 1]
        if end[1] < start[1]:                # down-leg -> its end is the low
            fb, fbt = end[1], end[0]
    return None if fb is None else (fb, fbt)


# ---------------------------------------------------------------------------
# nested-peak walk — nearest-first from B  (Pine 141-226)
# ---------------------------------------------------------------------------
def _nested_peaks(points, b_price, b_idx, min_gap_pct, max_swings):
    """Walk the pivot points newest->oldest, keeping the staircase of nested
    peaks above B. Returns (peaks, kept) where peaks is a list of (price, idx)
    for the kept slots k0..k(kept-1).

    Rules (faithful to the Pine):
      * only points strictly older than B (t < b_idx) are considered,
      * a HIGH counts only if price > B * (1 + minGap%),
      * first kept high = T1 (nearest peak above B),
      * a later (older) high that is > lastKept * gapMul starts a NEW nested
        peak; one that is merely > lastKept (within the gap) REPLACES the last
        kept peak (keep the higher), taking its time too,
      * a LOW below B halts the walk (a deeper, different decline),
      * stop once `kept` reaches maxSwings.
    """
    gap_mul = 1.0 + min_gap_pct / 100.0
    k = [None, None, None, None]
    kt = [None, None, None, None]
    last_kept = None
    kept = 0
    n = len(points)
    for j in range(n):
        idx = n - 1 - j                      # newest first
        t = points[idx][0]
        if t < b_idx:
            pr = points[idx][1]
            is_high = points[idx][2]
            if is_high:
                if pr > b_price * gap_mul:
                    if last_kept is None:
                        k[0], kt[0] = pr, t          # T1 = nearest peak above B
                        last_kept = pr
                        kept = 1
                    elif pr > last_kept * gap_mul:    # clearly higher -> new peak
                        if kept == 1:
                            k[1], kt[1] = pr, t
                        elif kept == 2:
                            k[2], kt[2] = pr, t
                        elif kept == 3:
                            k[3], kt[3] = pr, t
                        last_kept = pr
                        kept += 1
                    elif pr > last_kept:              # within gap -> keep higher
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
                if pr < b_price:
                    break                            # deeper low -> stop
            if kept >= max_swings:
                break
    peaks = [(k[i], kt[i]) for i in range(kept)]
    return peaks, kept


# ---------------------------------------------------------------------------
# fib levels + per-swing state machine  (Pine 244-280)
# ---------------------------------------------------------------------------
def swing_levels(a_price, b_price, params=DEFAULTS):
    """swingLevels(Ap, Bp): fib levels off the (A - B) range, measured up from B."""
    r = a_price - b_price
    return {
        "sl": b_price + params["fib_sl"] * r,
        "eL": b_price + params["fib_eL"] * r,
        "eH": b_price + params["fib_eH"] * r,
        "tL": b_price + params["fib_tL"] * r,
        "tH": b_price + params["fib_tH"] * r,
    }


def step_trade(s, e_hi, t_lo, sl, e_ok, v_ok, close, close_prev, high):
    """stepTrade: one swing's wait(1)->IN(2)->TP(3) machine for one bar.

    Returns (new_state, entry_fire, tp_fire, sl_fire). Entry requires a confirmed
    close crossing e_hi (0.382) FROM BELOW plus the EMA/vol filters; TP when high
    reaches t_lo (0.618); SL when close < sl (0.236) -> re-arm to wait. State 3 is
    terminal.
    """
    ns = s
    e_fire = tp_fire = sl_fire = False
    cross_e = (not rt.is_na(e_hi)) and close > e_hi and (not rt.is_na(close_prev)) and close_prev <= e_hi
    if s == 1 and cross_e and e_ok and v_ok:
        ns = 2
        e_fire = True
    elif s == 2:
        if (not rt.is_na(t_lo)) and high >= t_lo:
            ns = 3
            tp_fire = True
        elif (not rt.is_na(sl)) and close < sl:
            ns = 1
            sl_fire = True
    return ns, e_fire, tp_fire, sl_fire


# ---------------------------------------------------------------------------
# driver — replay the whole indicator bar-by-bar
# ---------------------------------------------------------------------------
def _col(df, *names):
    for nm in names:
        if nm in df.columns:
            return df[nm].to_numpy(float)
    raise KeyError(f"none of {names} in columns {list(df.columns)}")


def run(df, params=None):
    """Replay the indicator over `df` and return the instrumented series, each a
    list bar-aligned to df, for golden-master parity:

      "EMA 9", "EMA 21"  — the plotted EMAs
      "B"                — common-low B price (na when no setup)
      "A0".."A3"         — nested peak prices T1..T4 (na when absent)
      "ENTRY"/"TP"/"SL"  — 1.0 on a bar where ANY swing fires that event, else na

    Accepts either TradingView-CSV columns (open/high/low/close/volume) or
    Title-case OHLCV.
    """
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

    piv_b = _Pivots(p["zigDepth"], p["minDeclinePct"])
    piv_p = _Pivots(p["zigDepth"], p["pivotSensPct"])

    # persistent indicator state
    B_price = None
    B_time = None
    A = [None, None, None, None]            # A0..A3 prices
    st = [0, 0, 0, 0]                        # per-swing state (Pine `var int st0 = 0`)
    state_for_b = None

    out = {key: [nan] * n for key in
           ("EMA 9", "EMA 21", "B", "A0", "A1", "A2", "A3",
            "ST0", "ST1", "ST2", "ST3", "ENTRY", "TP", "SL")}

    for k in range(n):
        piv_b.update(high_l, low_l, k)
        piv_p.update(high_l, low_l, k)

        # --- B detection (Pine 124-137) ---
        b_pts = piv_b.points()
        if len(b_pts) >= 1:
            bres = _b_from_points(b_pts)
            if bres is not None:
                fb, fbt = bres
                is_first = B_time is None
                is_changed = B_time is not None and fbt != B_time
                if is_first or is_changed:
                    B_price, B_time = fb, fbt

        has_b = B_price is not None

        # --- nested peaks (Pine 141-226) ---
        if has_b:
            p_pts = piv_p.points()
            if len(p_pts) >= 1:
                peaks, kept = _nested_peaks(p_pts, B_price, B_time,
                                            p["minGapPct"], p["maxSwings"])
                A = [None, None, None, None]
                for i in range(kept):
                    A[i] = peaks[i][0]

        # --- state reset on new B (Pine 233-241) ---
        if has_b and (state_for_b is None or B_time != state_for_b):
            state_for_b = B_time
            st = [1, 1, 1, 1]

        # --- filters (Pine 258-261) ---
        c = close[k]
        ema_ok = (not p["useEmaFilter"]) or (
            (not rt.is_na(ema9[k]) and c > ema9[k]) and
            (not rt.is_na(ema21[k]) and c > ema21[k]))
        vs = vol_sma[k]
        vol_ok = (not p["useVolFilter"]) or (
            (not rt.is_na(vs)) and (not rt.is_na(volume[k])) and volume[k] > vs * p["volMult"])

        # --- per-swing state machine (Pine 263-319; historical bars are confirmed) ---
        any_e = any_t = any_x = False
        if has_b:
            c_prev = close[k - 1] if k > 0 else nan
            for i in range(4):
                if A[i] is None:
                    continue
                lv = swing_levels(A[i], B_price, p)
                ns_, ef, tf, sf = step_trade(st[i], lv["eH"], lv["tL"], lv["sl"],
                                             ema_ok, vol_ok, c, c_prev, high[k])
                st[i] = ns_
                any_e = any_e or ef
                any_t = any_t or tf
                any_x = any_x or sf

        # --- record instrumented series ---
        out["EMA 9"][k] = ema9[k]
        out["EMA 21"][k] = ema21[k]
        for i in range(4):
            out[f"ST{i}"][k] = float(st[i])     # plotted unconditionally (Pine var int)
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


# ============================================================================
# SELF-TEST
# ============================================================================
if __name__ == "__main__":
    base = [60, 62, 64, 66, 70, 80, 92, 100]
    down = list(np.linspace(100, 50, 14))[1:]
    rally = list(np.linspace(50.5, 110, 45))
    px = base + down + rally
    idx = pd.date_range("2024-01-01", periods=len(px), freq="D", tz="UTC")
    vol = [1e6] * (len(base) + len(down)) + list(np.linspace(3e6, 30e6, 45))
    data = pd.DataFrame({"Open": px, "High": [x * 1.01 for x in px],
                         "Low": [x * 0.99 for x in px], "Close": px, "Volume": vol}, index=idx)
    res = run(data)
    print("B final:", res["B"][-1])
    print("A0 final:", res["A0"][-1])
    print("entry bars:", [i for i, v in enumerate(res["ENTRY"]) if v == 1.0])
