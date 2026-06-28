"""
Regression gate: golden-CSV parity on every TradingView export in
`fixtures/parity_csv/` against pinescan.nsv2_engine.

Each CSV is a chart-data export of the instrumented V2 indicator (data-window
columns B/A0-A3/ST0-ST3/ENTRY/TP/SL + Volume, exported from full history so the
indicator starts cold). A clean pass = the Python port reproduces TradingView's
own computation bar-for-bar.

Run as a test:  pytest tests/test_parity.py
Run as a CLI :  python tests/test_parity.py   (exit 0 iff every valid export passes)
"""
import sys
from pathlib import Path

from pinescan import nsv2_engine
from pinescan.core import parity

CSV_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "parity_csv"


def run_all(verbose=False):
    """Diff every fixture; return (checked, failed_symbols). Skips invalid exports
    (no Volume, or warm start) — those are export artifacts, not port bugs."""
    csvs = sorted(CSV_DIR.glob("*.csv"))
    if not csvs:
        raise FileNotFoundError(f"no CSVs found in {CSV_DIR}")
    failed, checked = [], 0
    for path in csvs:
        golden = parity.load_tv_csv(str(path))
        sym = path.stem
        if "Volume" not in golden.columns:
            if verbose:
                print(f"  SKIP  {sym}  (no Volume column)")
            continue
        # EMA warms in ~9 bars: a value on row 0 means the export carries pre-window
        # bars (warm start) → left-edge mismatch the cold Python run can't reproduce.
        if "EMA 9" in golden.columns and not parity._is_na(golden["EMA 9"].iloc[0]):
            if verbose:
                print(f"  SKIP  {sym}  (warm start)")
            continue
        checked += 1
        report = parity.compare(golden, nsv2_engine.run(golden))
        if report["passed"]:
            if verbose:
                print(f"  PASS  {sym}")
        else:
            failed.append(sym)
            if verbose:
                print(f"  FAIL  {sym}\n{parity.format_report(report)}")
    return checked, failed


def test_all_fixtures_parity():
    checked, failed = run_all()
    assert checked >= 20, f"expected the full parity corpus, only {checked} valid exports"
    assert not failed, f"parity FAILED for: {failed}"


if __name__ == "__main__":
    checked, failed = run_all(verbose=True)
    print(f"\n{checked - len(failed)}/{checked} valid exports passed")
    sys.exit(1 if failed else 0)
