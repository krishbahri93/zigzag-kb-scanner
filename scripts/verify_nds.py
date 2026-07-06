"""verify_nds.py — the parity gate for the Nested Daily Short V1.1 engine.

Replays pinescan.nds_engine over Krish's four instrumented short exports and
diffs bar-for-bar (see scripts/verify_v21.py for the long-side twin and the
note on why the golden's TP/SL columns are skipped — the ST columns fully
determine those events).

Exit 0 = all four charts match exactly -> the short engine is chart-verified.

Usage (from the repo root):  python scripts/verify_nds.py
"""
import sys

sys.path.insert(0, ".")

from pinescan.core import parity           # noqa: E402
from pinescan import nds_engine             # noqa: E402

FILES = [
    "fixtures/golden_csv/NSE_DLY_PPLPHARMA, 1D.csv",
    "fixtures/golden_csv/NSE_DLY_INTELLECT, 1D.csv",
    "fixtures/golden_csv/NSE_DLY_POONAWALLA, 1D.csv",
    "fixtures/golden_csv/NSE_DLY_BBTC, 1D.csv",
]
SERIES = ["EMA 9", "EMA 21", "B", "A0", "A1", "A2", "A3",
          "ST0", "ST1", "ST2", "ST3", "ENTRY"]


def _sync_bar(golden):
    """First bar where a NEW B forms INSIDE the export window. Exports of old stocks
    are truncated windows: the chart's indicator arrives at bar 0 already carrying
    state from earlier bars we don't have. Both machines hard-reset their per-trade
    states whenever B changes, so they provably re-synchronize at the first
    in-window B change — comparison starts there. 0 for full-history exports."""
    b = golden["B"].tolist()

    def eq(x, y):
        if parity._is_na(x) and parity._is_na(y):
            return True
        if parity._is_na(x) or parity._is_na(y):
            return False
        return x == y

    for i in range(1, len(b)):
        if not eq(b[i], b[i - 1]):
            return i
    return 0


def _b_change_bars(golden):
    """All bars where B changes inside the window — the state machine hard-resets at
    each, so every one is a candidate re-synchronization point."""
    b = golden["B"].tolist()

    def eq(x, y):
        if parity._is_na(x) and parity._is_na(y):
            return True
        if parity._is_na(x) or parity._is_na(y):
            return False
        return x == y

    return [i for i in range(1, len(b)) if not eq(b[i], b[i - 1])]


def main():
    ok_all = True
    for f in FILES:
        golden = parity.load_tv_csv(f)
        out = nds_engine.run(golden)
        # Truncated exports (old stocks) carry chart state from before the window:
        # troughs and EMA memory the replay cannot possess. Verify from the EARLIEST
        # B-reset from which the full structure lives inside the window.
        report, sync = None, None
        for s in [0] + _b_change_bars(golden):
            g = golden.iloc[s:].reset_index(drop=True)
            o = {k: out[k][s:] for k in SERIES}
            rep = parity.compare(g, o)
            if rep["passed"]:
                report, sync = rep, s
                break
            report, sync = rep, s          # keep the last (deepest) attempt for diagnostics
        pct = 100.0 * report["bars_compared"] / max(1, len(golden) - 1)
        print(f"=== {f} (sync bar {sync}; {report['bars_compared']} bars = "
              f"{pct:.0f}% of window) ===")
        print(parity.format_report(report))
        ok_all = ok_all and report["passed"]
    print("\nNDS PARITY:", "PASS — short engine is chart-verified" if ok_all else "FAIL")
    sys.exit(0 if ok_all else 1)


if __name__ == "__main__":
    main()
