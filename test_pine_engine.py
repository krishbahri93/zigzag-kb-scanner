"""Regression tests for pine_engine + tv_zigzag — faithful Pine logic, the
real ZigZag, and the intraday hook.

Run: python test_pine_engine.py   (exits non-zero on any failure)
"""
import sys
import numpy as np
import pandas as pd

import pine_engine as pe
import tv_zigzag as zz


def _series(vspike=True, base=(60, 62, 64, 66, 70, 80, 92, 100)):
    """Lead-in (so A=100 is a confirmed pivot) -> A->B drop -> rally past A."""
    base = list(base)
    down = list(np.linspace(100, 50, 14))[1:]     # A=100 -> B=50
    rally = list(np.linspace(50.5, 110, 45))       # rally up past A
    px = base + down + rally
    idx = pd.date_range("2024-01-01", periods=len(px), freq="D", tz="UTC")
    nlow = len(base) + len(down)
    vol = [1e6] * nlow + (list(np.linspace(3e6, 30e6, 45)) if vspike else [1e6] * 45)
    return pd.DataFrame({
        "Open": px, "High": [p * 1.01 for p in px], "Low": [p * 0.99 for p in px],
        "Close": px, "Volume": vol}, index=idx)


def test_eff_depth_halving():
    # The library halves the depth input: depth=10 -> 5 (tradingview_zigzag_v9.pine:477)
    assert pe._eff_depth(10) == 5, pe._eff_depth(10)
    assert pe._eff_depth(4) == 2
    assert pe._eff_depth(2) == 2     # min 2
    print("  ok eff_depth: depth input is halved (10 -> 5, floor, min 2)")


def test_zigzag_detects_pivots():
    df = _series()
    piv = zz.detect_pivots(df["High"].tolist(), df["Low"].tolist(),
                           depth_setting=10, dev_threshold=15.0)
    kinds = [("H" if h else "L") for _, _, h in piv]
    # Expect at least one H (the A=100 peak) followed by an L (the B=50 low).
    assert "H" in kinds and "L" in kinds, kinds
    rec = pe._recent_downswing(piv)
    assert rec is not None, "no down-swing found"
    ai, ap, bi, bp = rec
    assert abs(ap - 100) < 2 and abs(bp - 50) < 2, (ap, bp)
    print(f"  ok zigzag: recent A->B ~ ({ap:.0f}->{bp:.0f}) detected via real algorithm")


def test_lifecycle():
    tr = pe.backtest(_series(), dev_pct=15.0)
    assert len(tr) == 2, f"expected T1+T2, got {len(tr)}"
    t1, t2 = tr
    assert t1["trade_type"] == "T1" and t1["outcome"] == "win"
    assert t2["trade_type"] == "T2" and t2["outcome"] == "win"
    assert abs(t1["entry_price"] - 69.17) < 0.5, t1["entry_price"]   # 0.382
    assert abs(t2["entry_price"] - 84.52) < 0.5, t2["entry_price"]   # 0.68
    assert t2["r_multiple"] > t1["r_multiple"] > 0
    print("  ok lifecycle: T1 win + T2 win at correct fib levels")


def test_filters_block_entry():
    # Flat volume -> volume filter never passes -> no entries.
    tr = pe.backtest(_series(vspike=False), dev_pct=15.0)
    assert tr == [], f"flat volume must block entries, got {len(tr)}"
    print("  ok filters: no volume spike -> no entry (faithful, not price-only)")


def test_intraday_provisional():
    """An entry firing on a live 'today' bar is provisional; the same bar once
    confirmed (post-close) is not."""
    df = _series()
    tr = pe.backtest(df, dev_pct=15.0)
    entry_bar = tr[0]["entry_bar"]                       # first T1 entry bar

    daily = df.iloc[:entry_bar]
    partial = df.iloc[entry_bar:entry_bar + 1]

    live = pe.evaluate("X", "1D", daily, today_partial=partial,
                       partial_is_live=True, dev_pct=15.0)
    assert live and live["signal"] == "T1 Entry", live
    assert live["provisional"] is True, "entry on a live partial must be provisional"

    closed = pe.evaluate("X", "1D", df.iloc[:entry_bar + 1], today_partial=None, dev_pct=15.0)
    assert closed and closed["signal"] == "T1 Entry", closed
    assert closed["provisional"] is False, "entry on a confirmed bar is not provisional"
    print("  ok intraday: same entry is provisional live, confirmed at close")


def test_jump_in():
    """Price gaps from below 0.382 to above 0.68 in one bar -> straight to T2.
    The gap must come after B is confirmed (eff_depth bars past B)."""
    base = [60, 62, 64, 66, 70, 80, 92, 100]
    down = list(np.linspace(100, 50, 14))[1:]            # B=50 at end of `down`
    hold = [50.5] * 6                                     # let B confirm (eff_depth=5)
    gap = [86.0, 92.0, 98.0, 104.0, 108.0]               # gap above 0.68 then past A (TP)
    px = base + down + hold + gap
    idx = pd.date_range("2024-01-01", periods=len(px), freq="D", tz="UTC")
    vol = [1e6] * (len(base) + len(down) + len(hold)) + [40e6] * len(gap)
    df = pd.DataFrame({"Open": px, "High": [p * 1.01 for p in px],
                       "Low": [p * 0.99 for p in px], "Close": px, "Volume": vol}, index=idx)
    tr = pe.backtest(df, dev_pct=15.0)
    assert tr and all(t["trade_type"] == "T2" for t in tr), [t["trade_type"] for t in tr]
    print("  ok jump-in: gap above 0.68 skips T1, enters T2 directly")


if __name__ == "__main__":
    tests = [test_eff_depth_halving, test_zigzag_detects_pivots, test_lifecycle,
             test_filters_block_entry, test_intraday_provisional, test_jump_in]
    failed = 0
    for t in tests:
        try:
            t()
        except AssertionError as e:
            failed += 1
            print(f"  FAIL {t.__name__}: {e}")
        except Exception as e:
            failed += 1
            print(f"  ERROR {t.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)
