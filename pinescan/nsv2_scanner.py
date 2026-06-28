"""
nsv2_scanner — turn the V2 engine's output into an actionable Setup row.

`scan_symbol(sym, df)` replays the V2 indicator over one daily DataFrame and reads
the LAST confirmed bar's state exactly as the Pine table/plots show on the chart's
right edge: B, T1..T4 peaks + fib zones, per-swing wait/IN/TP state, the active
swing, in_band/approaching/expired, and any entry/tp/sl fire. Market-agnostic —
takes a DataFrame, returns a dict (or None when there's no current setup).
"""
import math

from . import nsv2_engine

MIN_BARS = 50          # need enough history for a >=Min-Decline% swing to confirm


def _f(x):
    """JSON-safe float (None for na/inf)."""
    if x is None:
        return None
    try:
        if math.isnan(x) or math.isinf(x):
            return None
    except TypeError:
        return None
    return round(float(x), 4)


def scan_symbol(sym, df, params=None):
    """Replay V2 over one daily DataFrame and return a scanner row for the last
    bar, or None if there's no current setup (no B). Faithful to the indicator's
    right-edge state — no re-derivation, just reads `nsv2_engine.run` output."""
    res = nsv2_engine.run(df, params)
    n = len(df)
    last = n - 1

    b = res["B"][last]
    if b is None or (isinstance(b, float) and math.isnan(b)):
        return None                                   # no qualifying decline -> not a setup

    close = float(df["Close"].iloc[last])
    p = dict(nsv2_engine.DEFAULTS)
    if params:
        p.update(params)

    # peaks + per-swing detail, mirroring the Pine info table
    swings = []
    top_a = None
    active_idx = None
    for i in range(4):
        a = res[f"A{i}"][last]
        st = res[f"ST{i}"][last]
        if a is None or (isinstance(a, float) and math.isnan(a)):
            continue
        top_a = a                                     # highest present peak = last seen
        lv = nsv2_engine.swing_levels(a, b, p)
        sti = int(st) if st == st else 0
        if active_idx is None and sti != 3:           # active = lowest swing not TP'd
            active_idx = i
        swings.append({
            "swing": f"T{i + 1}",
            "A": _f(a),
            "state": {1: "wait", 2: "IN", 3: "TP"}.get(sti, "-"),
            "entry_lo": _f(lv["eL"]), "entry_hi": _f(lv["eH"]),
            "tp_lo": _f(lv["tL"]), "tp_hi": _f(lv["tH"]),
            "sl": _f(lv["sl"]),
            "depth_pct": _f((a - b) / a * 100.0) if a else None,
        })

    if not swings:
        return None

    expired = top_a is not None and close > top_a

    # active-swing entry band -> in_band / approaching (matches dashboard semantics)
    in_band = approaching = False
    active = None
    if active_idx is not None:
        active = next(s for s in swings if s["swing"] == f"T{active_idx + 1}")
        eL, eH = active["entry_lo"], active["entry_hi"]
        if eL is not None and eH is not None:
            in_band = eL <= close <= eH
            # within 3% below the band = "approaching" (climbing toward entry)
            approaching = (not in_band) and (eL * 0.97 <= close < eL)

    # did anything fire on the most recent confirmed bar?
    fired = {k: (res[k][last] == 1.0) for k in ("ENTRY", "TP", "SL")}

    return {
        "sym": sym,
        "asof": str(df.index[last].date()),
        "ltp": _f(close),
        "B": _f(b),
        "active": active["swing"] if active else None,
        "active_state": active["state"] if active else None,
        "in_band": bool(in_band),
        "approaching": bool(approaching),
        "expired": bool(expired),
        "fired_entry": bool(fired["ENTRY"]),
        "fired_tp": bool(fired["TP"]),
        "fired_sl": bool(fired["SL"]),
        "n_swings": len(swings),
        "swings": swings,
    }
