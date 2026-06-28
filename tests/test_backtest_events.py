"""
Acceptance test for U1 — events.trades_for (engine signals -> [Trade]).

Drives a synthetic V2 setup (early low -> rise to A~100 -> fall to B~50 -> rally)
straight through the parity-locked engine and checks that events.py reconstructs
the swing's lifecycle correctly: a T1 entry near the 0.382 band, with target above
the fill, and V2's own outcome ("tp" when the rally reaches 0.618, "open" when it
enters but never gets there). Tolerances are loose — this guards the reconstruction
shape, not the engine's exact prices (those are covered by the parity gate).
"""
import numpy as np
import pandas as pd

from pinescan import nsv2_engine
from pinescan.backtest.events import trades_for


def _df(rally_to):
    """Early low -> rise to A~100 -> fall to B~50 -> rally up to `rally_to`.

    Adapted from tests/test_scanner.py. Rising volume on the rally clears the
    1.2x-vol entry filter. With the engine's measured levels (A0=101, B=49.5) the
    0.382 entry sits ~69.2 and the 0.618 target ~81.3; since High = Close*1.01, a
    rally_to of ~82+ is needed for the high to actually tag the target.
    """
    pre = [70, 67, 63, 58, 53, 49, 47, 49, 53, 58, 63, 68]   # early low = first pivot
    base = [72, 80, 90, 100]                                 # rise into A=100
    down = list(np.linspace(100, 50, 14))[1:]                # A -> B=50
    rally = list(np.linspace(50.5, rally_to, 30))
    px = pre + base + down + rally
    idx = pd.date_range("2024-01-01", periods=len(px), freq="D", tz="UTC")
    vol = [1e6] * (len(pre) + len(base) + len(down)) + list(np.linspace(3e6, 30e6, 30))
    return pd.DataFrame({"Open": px, "High": [x * 1.01 for x in px],
                         "Low": [x * 0.99 for x in px], "Close": px, "Volume": vol}, index=idx)


def _entry_band(df):
    """Recompute the engine's (eL, eH, tL) for this setup so the assertions can
    locate the entry band / target independently of events.py."""
    out = nsv2_engine.run(df, nsv2_engine.DEFAULTS)
    a0, b = out["A0"][-1], out["B"][-1]
    lv = nsv2_engine.swing_levels(a0, b, nsv2_engine.DEFAULTS)
    return lv["eL"], lv["eH"], lv["tL"]


def test_trades_for_emits_t1_entry_that_reaches_target():
    df = _df(rally_to=85)                       # rally clears 0.382 AND tags 0.618
    trades = trades_for("SYN", df)

    assert len(trades) >= 1                      # the setup fired at least once
    t = trades[0]
    assert t.swing == "T1"                       # nearest peak above B is T1
    assert t.symbol == "SYN"

    e_lo, e_hi, t_lo = _entry_band(df)
    assert t.entry_price > 0
    assert e_lo - 5 <= t.entry_price <= e_hi + 5  # fill lands near the 0.32-0.382 band
    assert t.target > t.entry_price               # take-profit is above the fill
    assert abs(t.target - t_lo) < 1e-6            # target == swing_levels' 0.618 tL
    assert t.sl < t.entry_price                   # stop sits below the fill

    # the rally reaches 0.618, so V2's own outcome is a take-profit
    assert t.natural_outcome == "tp"
    assert t.natural_exit_date is not None
    assert t.natural_exit_date > t.entry_date     # exit strictly after entry


def test_trades_for_marks_open_when_target_not_reached():
    # enters the 0.382 band but the rally tops out below 0.618 -> still holding
    trades = trades_for("SYN", _df(rally_to=78))
    assert len(trades) >= 1
    t = trades[0]
    assert t.swing == "T1"
    assert t.natural_outcome == "open"
    assert t.natural_exit_date is None
