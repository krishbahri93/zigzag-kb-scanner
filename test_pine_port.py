"""Tests for pine_port — the reusable Pine->Python conversion pipeline.

Covers:
  * runtime: Pine-exact semantics for na/nz, Series history access, and ta.*
    (seeding, na propagation, window rules) — the published Pine equivalents.
  * lint: static .pine pre-port analysis — dependency extraction (library
    copy-paste warning), gotcha flags, plot inventory.
  * parity: golden-master CSV comparison — the only accepted equivalence proof.

Run: python test_pine_port.py   (exits non-zero on any failure)
Also pytest-compatible.
"""
import io
import json
import math
import sys

from pine_port import runtime as rt
from pine_port import lint as pl
from pine_port import parity as pp


NAN = float("nan")


def eq(a, b, tol=1e-9):
    """Compare scalars where na == na."""
    if rt.is_na(a) and rt.is_na(b):
        return True
    if rt.is_na(a) or rt.is_na(b):
        return False
    return abs(a - b) <= tol


def seq_eq(xs, ys, tol=1e-9):
    return len(xs) == len(ys) and all(eq(a, b, tol) for a, b in zip(xs, ys))


# ============================================================================
# runtime — core
# ============================================================================

def test_na_nz():
    assert rt.is_na(rt.na)
    assert rt.is_na(None)
    assert rt.is_na(float("nan"))
    assert not rt.is_na(0.0)
    assert rt.nz(rt.na) == 0
    assert rt.nz(rt.na, 7.5) == 7.5
    assert rt.nz(3.0, 7.5) == 3.0
    print("  ok na/nz")


def test_series_history():
    s = rt.Series()
    s.push(10.0)
    s.push(20.0)
    s.push(30.0)
    assert s[0] == 30.0          # current bar
    assert s[1] == 20.0          # one bar back  (Pine s[1])
    assert s[2] == 10.0
    assert rt.is_na(s[3])        # before first bar -> na, like Pine
    assert len(s) == 3
    s.set(31.0)                  # Pine `s := 31` re-assignment on current bar
    assert s[0] == 31.0 and s[1] == 20.0
    print("  ok Series history access")


def test_sma():
    # Pine: na until the window holds `len` values; na in window -> na out.
    out = rt.sma([1, 2, 3, 4], 3)
    assert seq_eq(out, [NAN, NAN, 2.0, 3.0]), out
    out = rt.sma([NAN, 2, 3, 4], 3)
    assert seq_eq(out, [NAN, NAN, NAN, 3.0]), out
    print("  ok sma: window + na propagation")


def test_ema_seeding():
    # Pine ema: na(prev) ? sma(src, len) : alpha*src + (1-alpha)*prev, alpha=2/(len+1)
    src = [1.0, 2.0, 3.0, 4.0]
    out = rt.ema(src, 3)
    a = 2.0 / 4.0
    seed = 2.0                                  # sma of first 3
    nxt = a * 4.0 + (1 - a) * seed              # 3.0
    assert seq_eq(out, [NAN, NAN, seed, nxt]), out
    # leading na shifts the seed window (sma stays na until clean window)
    out = rt.ema([NAN, 1.0, 2.0, 3.0, 4.0], 3)
    assert seq_eq(out, [NAN, NAN, NAN, 2.0, 3.0]), out
    print("  ok ema: sma seed + recursion + leading-na shift")


def test_rma_seeding():
    # Pine rma: same recursion with alpha = 1/len
    src = [1.0, 2.0, 3.0, 4.0]
    out = rt.rma(src, 2)
    seed = 1.5                                  # sma of first 2
    v2 = 0.5 * 3.0 + 0.5 * seed                # 2.25
    v3 = 0.5 * 4.0 + 0.5 * v2                  # 3.125
    assert seq_eq(out, [NAN, seed, v2, v3]), out
    print("  ok rma: sma seed, alpha=1/len")


def test_change_mom():
    out = rt.change([1.0, 4.0, 9.0])
    assert seq_eq(out, [NAN, 3.0, 5.0]), out
    out = rt.change([1.0, 4.0, 9.0], 2)
    assert seq_eq(out, [NAN, NAN, 8.0]), out
    assert seq_eq(rt.mom([1.0, 4.0, 9.0], 1), [NAN, 3.0, 5.0])
    print("  ok change/mom")


def test_highest_lowest():
    src = [3.0, 1.0, 4.0, 1.0, 5.0]
    assert seq_eq(rt.highest(src, 3), [NAN, NAN, 4.0, 4.0, 5.0])
    assert seq_eq(rt.lowest(src, 3), [NAN, NAN, 1.0, 1.0, 1.0])
    # offsets: 0 = current bar, negative = bars back of the extreme
    assert seq_eq(rt.highestbars(src, 3), [NAN, NAN, 0.0, -1.0, 0.0])
    print("  ok highest/lowest/highestbars")


def test_crossover_crossunder():
    a = [1.0, 1.0, 3.0, 3.0, 1.0]
    b = [2.0, 2.0, 2.0, 2.0, 2.0]
    assert rt.crossover(a, b) == [False, False, True, False, False]
    assert rt.crossunder(a, b) == [False, False, False, False, True]
    assert rt.cross(a, b) == [False, False, True, False, True]
    # na on either bar -> no cross
    assert rt.crossover([NAN, 3.0], [2.0, 2.0]) == [False, False]
    print("  ok crossover/crossunder/cross")


# ============================================================================
# runtime — extended ta
# ============================================================================

def test_tr_atr():
    high = [10.0, 12.0, 11.0]
    low = [9.0, 10.5, 9.5]
    close = [9.5, 11.0, 10.0]
    # tr(handle_na=False): first bar na; else max(h-l, |h-c1|, |l-c1|)
    out = rt.tr(high, low, close, handle_na=False)
    assert seq_eq(out, [NAN, 2.5, 1.5]), out
    # tr(handle_na=True): first bar = high-low
    out = rt.tr(high, low, close, handle_na=True)
    assert seq_eq(out, [1.0, 2.5, 1.5]), out
    # atr = rma(tr(true), len)
    out = rt.atr(high, low, close, 2)
    seed = (1.0 + 2.5) / 2.0
    v2 = 0.5 * 1.5 + 0.5 * seed
    assert seq_eq(out, [NAN, seed, v2]), out
    print("  ok tr/atr: first-bar handling + rma of tr(true)")


def test_rsi():
    # Hand-computed: src=[1,2,4,3], len=2
    # gains rma: [na,na,1.5,0.75]; losses rma: [na,na,0,0.5]
    # bar2: loss==0 -> 100 ; bar3: rs=1.5 -> 60
    out = rt.rsi([1.0, 2.0, 4.0, 3.0], 2)
    assert seq_eq(out, [NAN, NAN, 100.0, 60.0]), out
    print("  ok rsi: rma-of-gains/losses, div-by-zero -> 100")


def test_cum():
    assert seq_eq(rt.cum([1.0, 2.0, 3.0]), [1.0, 3.0, 6.0])
    print("  ok cum")


def test_stdev_biased():
    # Pine default is biased (population) stdev
    out = rt.stdev([1.0, 2.0, 3.0, 4.0], 3)
    exp2 = math.sqrt(2.0 / 3.0)                 # population stdev of 1,2,3
    assert seq_eq(out, [NAN, NAN, exp2, exp2]), out
    print("  ok stdev: biased/population by default")


def test_wma_vwma():
    # wma(len=3) weights 1,2,3 (most recent heaviest), denom 6
    out = rt.wma([1.0, 2.0, 3.0, 4.0], 3)
    w2 = (1 * 1 + 2 * 2 + 3 * 3) / 6.0
    w3 = (2 * 1 + 3 * 2 + 4 * 3) / 6.0
    assert seq_eq(out, [NAN, NAN, w2, w3]), out
    # vwma = sma(src*vol, len) / sma(vol, len)
    src = [1.0, 2.0, 3.0]
    vol = [1.0, 1.0, 2.0]
    out = rt.vwma(src, vol, 2)
    assert seq_eq(out, [NAN, 1.5, (2.0 + 6.0) / 3.0]), out
    print("  ok wma/vwma")


def test_valuewhen_barssince():
    cond = [False, True, False, True, False]
    src = [10.0, 20.0, 30.0, 40.0, 50.0]
    assert seq_eq(rt.valuewhen(cond, src, 0), [NAN, 20.0, 20.0, 40.0, 40.0])
    assert seq_eq(rt.valuewhen(cond, src, 1), [NAN, NAN, NAN, 20.0, 20.0])
    assert seq_eq(rt.barssince(cond), [NAN, 0.0, 1.0, 0.0, 1.0])
    print("  ok valuewhen/barssince")


def test_pivothigh_confirmation_lag():
    #          0    1    2    3    4
    src = [1.0, 2.0, 5.0, 2.0, 1.0]
    # left=right=1: candidate at bar2 (5.0) confirmed at bar3 -> value emitted at bar3
    out = rt.pivothigh(src, 1, 1)
    assert seq_eq(out, [NAN, NAN, NAN, 5.0, NAN]), out
    out = rt.pivotlow([5.0, 2.0, 1.0, 2.0, 5.0], 1, 1)
    assert seq_eq(out, [NAN, NAN, NAN, 1.0, NAN]), out
    # equality disqualifies (strict comparison — flagged unverified vs TV)
    out = rt.pivothigh([1.0, 5.0, 5.0, 1.0, 1.0], 1, 1)
    assert all(rt.is_na(v) for v in out), out
    print("  ok pivothigh/pivotlow: value emitted on confirmation bar")


# ============================================================================
# lint — static pre-port analysis
# ============================================================================

SAMPLE_PINE = '''\
//@version=6
indicator("Demo", overlay=true)
import TradingView/ZigZag/7 as zigzag
import someone/OtherLib/3

var float state = na
varip int ticks = 0
htf = request.security(syminfo.tickerid, "D", close, lookahead=barmerge.lookahead_on)
e = ta.ema(close, 21)
s = ta.supertrend(3, 10)
ph = ta.pivothigh(high, 5, 5)
if barstate.isconfirmed
    state := e
plot(e, "EMA21")
plot(ph, title="PivotH")
'''


def test_lint_dependencies_and_warning():
    rep = pl.lint_pine(SAMPLE_PINE)
    deps = [(d["author"], d["library"], d["version"]) for d in rep["dependencies"]]
    assert ("TradingView", "ZigZag", 7) in deps, deps
    assert ("someone", "OtherLib", 3) in deps, deps
    assert rep["dependencies"][0]["alias"] == "zigzag"
    # THE upfront warning: libraries cannot be auto-fetched, user must paste source
    codes = [w["code"] for w in rep["warnings"]]
    assert "LIBRARY_SOURCE_REQUIRED" in codes, codes
    print("  ok lint: imports extracted + library copy-paste warning is upfront")


def test_lint_gotcha_flags():
    rep = pl.lint_pine(SAMPLE_PINE)
    codes = [w["code"] for w in rep["warnings"]]
    assert "VARIP" in codes
    assert "REQUEST_SECURITY" in codes
    assert "LOOKAHEAD_ON" in codes
    assert "VAR_STATE" in codes
    assert "PIVOT_CONFIRMATION_LAG" in codes
    print("  ok lint: gotcha flags (varip, security, lookahead, var, pivots)")


def test_lint_builtins_and_support():
    rep = pl.lint_pine(SAMPLE_PINE)
    used = rep["builtins_used"]
    assert "ta.ema" in used and "ta.pivothigh" in used
    assert "ta.supertrend" in rep["unsupported"]       # not in runtime
    assert "ta.ema" not in rep["unsupported"]
    print("  ok lint: builtin inventory + unsupported detection")


def test_lint_plots():
    rep = pl.lint_pine(SAMPLE_PINE)
    assert rep["plots"] == ["EMA21", "PivotH"], rep["plots"]
    print("  ok lint: plot titles inventoried (CSV exports only plotted series)")


def test_lint_clean_file_no_dep_warning():
    rep = pl.lint_pine('//@version=6\nindicator("x")\nplot(close, "c")\n')
    codes = [w["code"] for w in rep["warnings"]]
    assert "LIBRARY_SOURCE_REQUIRED" not in codes
    assert rep["dependencies"] == []
    print("  ok lint: no false library warning when there are no imports")


# ============================================================================
# parity — golden-master comparison
# ============================================================================

GOLDEN_CSV = """time,open,high,low,close,EMA21,PivotH
2024-01-01T00:00:00Z,1,2,0.5,1.5,NaN,NaN
2024-01-02T00:00:00Z,2,3,1.5,2.5,2.0,NaN
2024-01-03T00:00:00Z,3,4,2.5,3.5,2.5,4.0
2024-01-04T00:00:00Z,4,5,3.5,4.5,3.0,NaN
"""


def test_parity_load_csv():
    df = pp.load_tv_csv(io.StringIO(GOLDEN_CSV))
    assert list(df.columns[:5]) == ["time", "open", "high", "low", "close"]
    assert len(df) == 4
    assert df["time"].iloc[0].year == 2024
    print("  ok parity: TV CSV loads (ISO time, NaN cells)")


def test_parity_pass_and_last_bar_dropped():
    df = pp.load_tv_csv(io.StringIO(GOLDEN_CSV))
    ours = {
        "EMA21": [NAN, 2.0, 2.5, 999.0],     # divergence ONLY on last (repainting) bar
        "PivotH": [NAN, NAN, 4.0, NAN],
    }
    rep = pp.compare(df, ours, drop_last=True)
    assert rep["passed"], rep
    assert rep["bars_compared"] == 3
    print("  ok parity: bar-for-bar match passes; last (repainting) bar excluded")


def test_parity_reports_first_divergence():
    df = pp.load_tv_csv(io.StringIO(GOLDEN_CSV))
    ours = {"EMA21": [NAN, 2.0, 2.6, 3.0], "PivotH": [NAN, NAN, 4.0, NAN]}
    rep = pp.compare(df, ours, drop_last=True)
    assert not rep["passed"]
    bad = rep["series"]["EMA21"]
    assert not bad["passed"] and bad["n_diverged"] == 1
    d = bad["divergences"][0]
    assert d["bar"] == 2 and eq(d["expected"], 2.5) and eq(d["got"], 2.6)
    assert "2024-01-03" in d["time"]
    assert rep["series"]["PivotH"]["passed"]
    print("  ok parity: divergence localized to bar + series, with timestamps")


def test_parity_na_mismatch_is_divergence():
    df = pp.load_tv_csv(io.StringIO(GOLDEN_CSV))
    ours = {"PivotH": [NAN, 4.0, 4.0, NAN]}   # we emit a pivot one bar early
    rep = pp.compare(df, ours, drop_last=True)
    assert not rep["passed"]
    assert rep["series"]["PivotH"]["n_diverged"] == 1
    print("  ok parity: na-vs-value mismatch counts as divergence")


def test_parity_tolerance():
    df = pp.load_tv_csv(io.StringIO(GOLDEN_CSV))
    ours = {"EMA21": [NAN, 2.0, 2.5 + 1e-7, 3.0]}
    assert pp.compare(df, ours, drop_last=True, abs_tol=1e-6, rel_tol=0.0)["passed"]
    assert not pp.compare(df, ours, drop_last=True, abs_tol=1e-9, rel_tol=0.0)["passed"]
    print("  ok parity: tolerance is explicit and honored")


def test_parity_snapshot_roundtrip(tmp_path=None):
    import tempfile, os
    df = pp.load_tv_csv(io.StringIO(GOLDEN_CSV))
    ours = {"EMA21": [NAN, 2.0, 2.5, 3.0]}
    with tempfile.TemporaryDirectory() as d:
        snap = os.path.join(d, "golden.json")
        pp.save_snapshot(snap, ours)
        loaded = pp.load_snapshot(snap)
        assert seq_eq(loaded["EMA21"], ours["EMA21"])
        rep = pp.compare(df, loaded, drop_last=True)
        assert rep["passed"]
    print("  ok parity: regression snapshot save/load roundtrip")


# ============================================================================
# CLI
# ============================================================================

def test_cli_lint_json():
    import os, subprocess, tempfile
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "demo.pine")
        with open(p, "w", encoding="utf-8") as f:
            f.write(SAMPLE_PINE)
        r = subprocess.run(
            [sys.executable, "-m", "pine_port", "lint", p, "--json"],
            capture_output=True, text=True,
            cwd=os.path.dirname(os.path.abspath(__file__)),
        )
        assert r.returncode == 0, r.stderr
        rep = json.loads(r.stdout)
        assert rep["plots"] == ["EMA21", "PivotH"]
        assert any(w["code"] == "LIBRARY_SOURCE_REQUIRED" for w in rep["warnings"])
    print("  ok cli: lint --json")


# ============================================================================

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
