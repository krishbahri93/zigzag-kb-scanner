"""Coverage for nsv2_scanner.scan_symbol — the actionable-signal interpretation
layer (the engine itself is covered bar-for-bar by the 24-symbol parity gate).
Checks the last-bar reading: B/peaks/swings, in_band, expired, no-setup -> None."""
import numpy as np
import pandas as pd

from pinescan import nsv2_scanner


def _df(rally_to):
    """Early low -> rise to A~100 -> fall to B~50 -> rally up to `rally_to`."""
    pre = [70, 67, 63, 58, 53, 49, 47, 49, 53, 58, 63, 68]   # early low = first pivot
    base = [72, 80, 90, 100]                                 # rise into A=100
    down = list(np.linspace(100, 50, 14))[1:]                # A -> B=50
    rally = list(np.linspace(50.5, rally_to, 30))
    px = pre + base + down + rally
    idx = pd.date_range("2024-01-01", periods=len(px), freq="D", tz="UTC")
    vol = [1e6] * (len(pre) + len(base) + len(down)) + list(np.linspace(3e6, 30e6, 30))
    return pd.DataFrame({"Open": px, "High": [x * 1.01 for x in px],
                         "Low": [x * 0.99 for x in px], "Close": px, "Volume": vol}, index=idx)


def test_scan_symbol_detects_setup_structure():
    r = nsv2_scanner.scan_symbol("SYN", _df(rally_to=68))   # last close inside the entry band
    assert r is not None and r["sym"] == "SYN"
    assert abs(r["B"] - 49.5) < 3                           # B = the ~50 low
    assert r["n_swings"] >= 1 and r["swings"][0]["swing"] == "T1"
    assert abs(r["swings"][0]["A"] - 101) < 4               # T1 peak ~ A=100
    assert r["active"] == "T1"
    assert r["in_band"] is True and r["expired"] is False   # 68 sits in T1's 0.32-0.382 band


def test_scan_symbol_expired_when_price_past_peak():
    r = nsv2_scanner.scan_symbol("SYN", _df(rally_to=115))  # rally blows past the peak
    assert r is not None and r["expired"] is True


def test_scan_symbol_tp_carries_holding_period():
    r = nsv2_scanner.scan_symbol("SYN", _df(rally_to=90))   # through the entry AND the target
    s = r["swings"][0]
    assert s["state"] == "TP" and s["tp_date"]
    assert s["entry_date"] and s["held_bars"] and s["held_bars"] >= 1
    assert r["expired"] is False                            # 90 is still under the ~100 peak


def test_scan_symbol_none_without_setup():
    px = [100 + (i % 3) for i in range(60)]                 # flat: no qualifying decline
    idx = pd.date_range("2024-01-01", periods=len(px), freq="D", tz="UTC")
    df = pd.DataFrame({"Open": px, "High": [x * 1.01 for x in px], "Low": [x * 0.99 for x in px],
                       "Close": px, "Volume": [1e6] * len(px)}, index=idx)
    assert nsv2_scanner.scan_symbol("FLAT", df) is None
