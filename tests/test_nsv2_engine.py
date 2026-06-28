"""Tests for nsv2_engine — faithful port of zigzag_kb_Indicator_nested_v2.

The risky/novel logic vs the existing dual-trade engine:
  * streaming ZigZag state (two instances at different devThresholds) that must
    match the verified tv_zigzag.detect_pivots bar-for-bar,
  * B detection = end of the most recent down-leg,
  * the nested-peak walk (nearest-first, min-gap keep-higher, stop-at-lower-low,
    B*gapMul floor, maxSwings cap),
  * the per-swing wait->IN->TP/SL state machine.

Run: python test_nsv2_engine.py   (exits non-zero on any failure)
"""
import math
import sys

import numpy as np
import pandas as pd

from pinescan.core import tv_zigzag as zz
from pinescan import nsv2_engine as ns


def _approx(a, b, tol=1e-6):
    return abs(a - b) <= tol


# ============================================================================
# streaming pivots must equal the verified detect_pivots
# ============================================================================

def _wiggly():
    # deterministic non-monotonic series with several swings
    seq = [100, 96, 90, 80, 70, 62, 58, 64, 75, 88, 99, 110, 104, 95, 84,
           72, 66, 60, 55, 51, 58, 70, 83, 96, 108, 120, 116, 108, 99, 90,
           80, 70, 60, 52, 48, 55, 67, 80, 94, 109]
    high = [p * 1.01 for p in seq]
    low = [p * 0.99 for p in seq]
    return high, low


def test_pivot_stream_matches_detect_pivots():
    high, low = _wiggly()
    for dev in (35.0, 25.0, 15.0):
        stream = ns._Pivots(depth_setting=10, dev_threshold=dev)
        for k in range(len(high)):
            stream.update(high, low, k)
        got = stream.points()
        exp = zz.detect_pivots(high, low, depth_setting=10, dev_threshold=dev)
        assert got == exp, f"dev={dev}\n got={got}\n exp={exp}"
    print("  ok stream: per-bar pivot state == detect_pivots (dev 35/25/15)")


# ============================================================================
# B detection = end of most recent down-leg
# ============================================================================

def test_b_from_points_recent_downswing():
    pts = [(10, 100.0, True), (20, 50.0, False), (30, 80.0, True), (40, 60.0, False)]
    b = ns._b_from_points(pts)
    assert b == (60.0, 40), b
    print("  ok B: end of the most recent down-leg (latest low)")


def test_b_uses_last_low_even_when_latest_point_is_high():
    pts = [(10, 100.0, True), (20, 50.0, False), (30, 90.0, True)]
    assert ns._b_from_points(pts) == (50.0, 20)
    print("  ok B: latest point a high -> B is the prior low")


def test_b_none_when_no_downleg():
    pts = [(10, 50.0, False), (20, 100.0, True)]
    assert ns._b_from_points(pts) is None
    print("  ok B: no down-leg -> None")


# ============================================================================
# nested-peak walk
# ============================================================================

def test_nested_peaks_t1_nearest_only():
    # one qualifying peak above B*gapMul -> T1 only. The peak must NOT be the
    # first-ever pivot (idx 0) — the library treats that as a low — so an earlier
    # low precedes it (chronological order; a real chart always has prior history).
    b_price, b_idx = 50.0, 100
    pts = [(80, 45.0, False), (95, 60.0, True)]
    peaks, kept = ns._nested_peaks(pts, b_price, b_idx, min_gap_pct=8.0, max_swings=4)
    assert kept == 1 and _approx(peaks[0][0], 60.0) and peaks[0][1] == 95, (peaks, kept)
    print("  ok peaks: nearest qualifying high becomes T1")


def test_nested_peaks_new_nested_then_keep_higher():
    # hand-traced: 60 -> 70 (new nested) -> 72 within gap of 70 (keep higher, replaces slot1)
    b_price, b_idx = 50.0, 100
    pts = [
        (70, 45.0, False),   # low < B -> would break, but it's oldest (walked last)
        (75, 72.0, True),
        (80, 58.0, False),
        (85, 70.0, True),
        (90, 55.0, False),
        (95, 60.0, True),
    ]
    peaks, kept = ns._nested_peaks(pts, b_price, b_idx, min_gap_pct=8.0, max_swings=4)
    # walk newest->oldest: 60(T1), 55 skip, 70(new nested), 58 skip,
    # 72 (within 8% of 70 -> keep higher, replaces slot1 incl. its time), 45 -> BREAK
    assert kept == 2, (peaks, kept)
    assert _approx(peaks[0][0], 60.0) and peaks[0][1] == 95
    assert _approx(peaks[1][0], 72.0) and peaks[1][1] == 75, peaks
    print("  ok peaks: new-nested then keep-higher (replaces slot + time)")


def test_nested_peaks_stop_at_lower_low():
    # The deeper low must be NEWER (closer to B) than the peak it shields:
    # walking back from B we hit the low first and stop, so the older 90 peak
    # (in a different, deeper decline) is never reached.
    b_price, b_idx = 50.0, 100
    pts = [
        (75, 90.0, True),    # older peak in a deeper decline -> must NOT be kept
        (80, 40.0, False),   # deeper low (newer than the 90 peak) -> halts here
        (95, 60.0, True),    # nearest peak above B -> T1
    ]
    peaks, kept = ns._nested_peaks(pts, b_price, b_idx, min_gap_pct=8.0, max_swings=4)
    assert kept == 1 and _approx(peaks[0][0], 60.0), (peaks, kept)
    print("  ok peaks: a low below B halts the staircase (deeper decline)")


def test_nested_peaks_below_gap_floor_skipped():
    # a high just above B but below B*gapMul is ignored
    b_price, b_idx = 50.0, 100
    pts = [(95, 53.0, True), (90, 60.0, True)]   # 53 < 54 floor; 60 qualifies
    peaks, kept = ns._nested_peaks(pts, b_price, b_idx, min_gap_pct=8.0, max_swings=4)
    assert kept == 1 and _approx(peaks[0][0], 60.0), (peaks, kept)
    print("  ok peaks: highs below B*gapMul floor are skipped")


def test_nested_peaks_max_swings_cap():
    b_price, b_idx = 50.0, 100
    # four cleanly separated rising peaks going back + a fifth that must be cut
    pts = [
        (60, 200.0, True),
        (70, 150.0, True),
        (80, 110.0, True),
        (90, 80.0, True),
        (95, 60.0, True),
    ]
    peaks, kept = ns._nested_peaks(pts, b_price, b_idx, min_gap_pct=8.0, max_swings=4)
    assert kept == 4, (peaks, kept)
    vals = [round(p[0], 1) for p in peaks]
    assert vals == [60.0, 80.0, 110.0, 150.0], vals
    print("  ok peaks: capped at maxSwings (5th peak dropped)")


# ============================================================================
# fib levels + state machine
# ============================================================================

def test_swing_levels():
    lv = ns.swing_levels(100.0, 50.0, ns.DEFAULTS)
    r = 50.0
    assert _approx(lv["sl"], 50 + 0.236 * r)
    assert _approx(lv["eL"], 50 + 0.32 * r)
    assert _approx(lv["eH"], 50 + 0.382 * r)
    assert _approx(lv["tL"], 50 + 0.618 * r)
    assert _approx(lv["tH"], 50 + 0.68 * r)
    print("  ok levels: fib math off (A-B) range, measured up from B")


def test_step_trade_entry_on_cross_from_below():
    # close crosses above eH (prev <= eH < close), filters pass -> enter
    ns_, ef, tf, sf = ns.step_trade(1, e_hi=69.1, t_lo=80.9, sl=61.8,
                                    e_ok=True, v_ok=True,
                                    close=70.0, close_prev=68.0, high=70.5)
    assert (ns_, ef, tf, sf) == (2, True, False, False)
    print("  ok step: entry on confirmed cross above 0.382 with filters")


def test_step_trade_no_entry_without_cross():
    # already above last bar -> not a cross
    ns_, ef, *_ = ns.step_trade(1, 69.1, 80.9, 61.8, True, True,
                                close=71.0, close_prev=70.0, high=71.0)
    assert ns_ == 1 and ef is False
    print("  ok step: no entry when there is no cross-from-below")


def test_step_trade_filters_block_entry():
    ns_, ef, *_ = ns.step_trade(1, 69.1, 80.9, 61.8, e_ok=False, v_ok=True,
                                close=70.0, close_prev=68.0, high=70.0)
    assert ns_ == 1 and ef is False
    print("  ok step: EMA/vol filter blocks entry")


def test_step_trade_tp_on_high():
    ns_, ef, tf, sf = ns.step_trade(2, 69.1, 80.9, 61.8, True, True,
                                    close=79.0, close_prev=78.0, high=81.0)
    assert (ns_, tf) == (3, True) and ef is False and sf is False
    print("  ok step: TP when high reaches 0.618")


def test_step_trade_sl_rearms():
    ns_, ef, tf, sf = ns.step_trade(2, 69.1, 80.9, 61.8, True, True,
                                    close=60.0, close_prev=70.0, high=62.0)
    assert (ns_, sf) == (1, True) and tf is False
    print("  ok step: SL (close<0.236) re-arms to wait")


def test_step_trade_tp_is_terminal():
    ns_, ef, tf, sf = ns.step_trade(3, 69.1, 80.9, 61.8, True, True,
                                    close=200.0, close_prev=199.0, high=201.0)
    assert (ns_, ef, tf, sf) == (3, False, False, False)
    print("  ok step: state 3 (TP'd) is terminal")


def test_step_trade_na_guards():
    # na entry level -> no entry; na tp level in state 2 -> no tp
    nan = float("nan")
    ns_, ef, *_ = ns.step_trade(1, nan, 80.9, 61.8, True, True, 70.0, 60.0, 71.0)
    assert ns_ == 1 and ef is False
    ns2, _, tf, _ = ns.step_trade(2, 69.1, nan, nan, True, True, 90.0, 80.0, 99.0)
    assert ns2 == 2 and tf is False
    print("  ok step: na level guards (no entry/tp on na)")


# ============================================================================
# integration — run() over a synthetic A->B->rally
# ============================================================================

def _series(vspike=True):
    # Lead-in forms an earlier low pivot so the A=100 peak is NOT the first-ever zzP
    # pivot: the library classifies its first pivot as a low (degenerate start==end),
    # and a real chart always has prior history before a tradeable peak. See
    # test_degenerate_first_pivot_high_treated_as_low.
    pre = [70, 67, 63, 58, 53, 49, 47, 49, 53, 58, 63, 68]  # early low ~47 (first pivot)
    base = [72, 80, 90, 100]                              # rise into A=100
    down = list(np.linspace(100, 50, 14))[1:]             # A=100 -> B=50 (50% > 35%)
    rally = list(np.linspace(50.5, 110, 45))              # rally up past A
    px = pre + base + down + rally
    idx = pd.date_range("2024-01-01", periods=len(px), freq="D", tz="UTC")
    nlow = len(pre) + len(base) + len(down)
    vol = [1e6] * nlow + (list(np.linspace(3e6, 30e6, 45)) if vspike else [1e6] * 45)
    return pd.DataFrame({
        "Open": px, "High": [p * 1.01 for p in px], "Low": [p * 0.99 for p in px],
        "Close": px, "Volume": vol}, index=idx)


def test_run_outputs_aligned_and_keys():
    df = _series()
    out = ns.run(df)
    for key in ("EMA 9", "EMA 21", "B", "A0", "A1", "A2", "A3",
                "ST0", "ST1", "ST2", "ST3", "ENTRY", "TP", "SL"):
        assert key in out, f"missing output series {key}"
        assert len(out[key]) == len(df), f"{key} not bar-aligned ({len(out[key])} vs {len(df)})"
    print("  ok run: all instrumented series present and bar-aligned")


def test_run_states_start_zero_then_arm():
    # Pine: `var int st0 = 0`; states are 0 until B is found, then reset to 1.
    out = ns.run(_series())
    assert out["ST0"][0] == 0.0, out["ST0"][0]          # before any B
    # once B exists the swing is armed (>=1) by the final bar
    assert out["ST0"][-1] >= 1.0, out["ST0"][-1]
    print("  ok run: states start at 0 (pre-B), arm to >=1 after B")


def test_run_detects_b_and_t1_and_fires_entry():
    df = _series()
    out = ns.run(df)
    # B settles at the ~50 low; A0 (T1) at the ~100 peak
    b_final = out["B"][-1]
    a0_final = out["A0"][-1]
    assert b_final is not None and not math.isnan(b_final) and abs(b_final - 49.5) < 3, b_final
    assert a0_final is not None and not math.isnan(a0_final) and abs(a0_final - 101) < 4, a0_final
    # an entry must fire on exactly the bar close first crosses 0.382 from below
    entry_bars = [i for i, v in enumerate(out["ENTRY"]) if v == 1.0]
    assert entry_bars, "no entry fired on the rally"
    print(f"  ok run: B~{b_final:.1f}, T1 A0~{a0_final:.1f}, entry fired (bars {entry_bars[:3]})")


def test_run_flat_volume_blocks_entry():
    out = ns.run(_series(vspike=False))
    assert all(v != 1.0 for v in out["ENTRY"]), "flat volume must block all entries"
    print("  ok run: no volume spike -> no entry (filter faithful)")


def test_run_insufficient_data_all_na():
    df = _series().iloc[:10]
    out = ns.run(df)
    assert all((v is None or math.isnan(v)) for v in out["B"]), "tiny series should yield no B"
    assert all(v != 1.0 for v in out["ENTRY"])
    print("  ok run: insufficient bars -> no B, no fires")


# ============================================================================

def test_degenerate_first_pivot_high_treated_as_low():
    # Pine/library quirk: the FIRST pivot is a degenerate Pivot(start==end)
    # (newPivotPointFound first-pivot branch), so the nested-peak block computes
    # down = end<start = false and pushes that point with ptH=down=FALSE — i.e. the
    # oldest pivot is classified a LOW even when it is actually a high. A stale
    # far-back first high must therefore NOT be kept as a peak above B. Without this,
    # PY invents a phantom T1 that TradingView does not have (QBTS/ONDS/RGTI/CLSK).
    points = [(38, 11.96, True), (409, 7.5, False)]      # first-ever pivot is a HIGH
    peaks, kept = ns._nested_peaks(points, 7.5, 409, 8.0, 4)
    assert kept == 0, f"degenerate first-pivot high must not become a peak, got {peaks}"
    print("  ok nested: degenerate first pivot treated as low (no phantom peak)")


def test_non_first_pivot_high_still_kept():
    # Guard against over-correction: a high that is NOT the first pivot is a valid
    # peak. points = low, high, low(=B); the high at idx 1 must be kept as T1, and
    # the idx-0 low (below B) correctly halts the walk.
    points = [(10, 5.0, False), (38, 11.96, True), (409, 7.5, False)]
    peaks, kept = ns._nested_peaks(points, 7.5, 409, 8.0, 4)
    assert kept == 1 and _approx(peaks[0][0], 11.96), f"expected T1=11.96, got {peaks}"
    print("  ok nested: non-first high still kept as peak")


TESTS = [v for k, v in sorted(globals().items()) if k.startswith("test_")]

if __name__ == "__main__":
    failed = 0
    for t in TESTS:
        try:
            t()
        except AssertionError as e:
            failed += 1
            print(f"  FAIL {t.__name__}: {e}")
        except Exception as e:
            failed += 1
            print(f"  ERROR {t.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(TESTS) - failed}/{len(TESTS)} passed")
    sys.exit(1 if failed else 0)
