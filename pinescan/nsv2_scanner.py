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

    # each trade is graded independently; "approaching" = within approachPct% below the band
    approach_mul = 1.0 - float(p.get("approachPct", 1.5)) / 100.0

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

        # engine-truth age: trailing bars in the CURRENT state (ST history is bar-aligned),
        # and — for open trades — the bar date the entry fired (start of the IN run)
        stser = res[f"ST{i}"]

        def _sti_at(j):
            v = stser[j]
            return int(v) if (v is not None and v == v) else None

        bars_in = 0
        for j in range(last, -1, -1):
            if _sti_at(j) != sti:
                break
            bars_in += 1
        entry_date = str(df.index[last - bars_in + 1].date()) if (sti == 2 and bars_in) else None
        # a TP'd trade is terminal: the start of its state-3 run is the day the target was hit
        tp_date = str(df.index[last - bars_in + 1].date()) if (sti == 3 and bars_in) else None
        # most recent STOP-OUT event: a 2 -> 1 transition in the state history (the SL bar itself
        # records state 1, since SL re-arms the trade). Bounded walk: exits older than ~90 bars
        # are ancient history for the dashboard.
        last_sl_date = None
        for j in range(last, max(0, last - 90), -1):
            if _sti_at(j) == 1 and j > 0 and _sti_at(j - 1) == 2:
                last_sl_date = str(df.index[j].date())
                break

        # this trade's own zone flags (only a waiting trade can be in/approaching its band)
        sw_in = sw_appr = False
        if sti == 1 and lv["eL"] == lv["eL"]:         # eL not NaN
            sw_in = lv["eL"] <= close <= lv["eH"]
            sw_appr = (not sw_in) and (lv["eL"] * approach_mul <= close < lv["eL"])

        swings.append({
            "swing": f"T{i + 1}",
            "A": _f(a),
            "state": {1: "wait", 2: "IN", 3: "TP"}.get(sti, "-"),
            "bars_in_state": bars_in,
            "entry_date": entry_date,
            "tp_date": tp_date,
            "last_sl_date": last_sl_date,
            "in_band": bool(sw_in),
            "approaching": bool(sw_appr),
            "entry_lo": _f(lv["eL"]), "entry_hi": _f(lv["eH"]),
            "tp_lo": _f(lv["tL"]), "tp_hi": _f(lv["tH"]),
            "sl": _f(lv["sl"]),
            "depth_pct": _f((a - b) / a * 100.0) if a else None,
        })

    if not swings:
        return None

    expired = top_a is not None and close > top_a

    # row-level flags mirror the ACTIVE trade (kept for backwards compatibility)
    in_band = approaching = False
    active = None
    if active_idx is not None:
        active = next(s for s in swings if s["swing"] == f"T{active_idx + 1}")
        in_band = active["in_band"]
        approaching = active["approaching"]

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
