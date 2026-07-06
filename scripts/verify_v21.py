"""verify_v21.py — the parity gate for the V2.1 rules (retire-missed + seed-pivot fix).

Replays the engine WITH the V2.1 flags over Krish's instrumented NSE exports
(fixtures/golden_csv) and diffs bar-for-bar via pinescan.core.parity. The compared
series are the machine's full internals: B, the four nested peaks, all four
per-trade states, the EMAs, and entry fires. (The golden's TP/SL columns are
skipped only because the un-instrumented plotshapes collide with those names in
the export; the ST columns fully determine those events anyway.)

Exit 0 = both charts match exactly -> the V2.1 rules are chart-verified.

Usage (from the repo root):  python scripts/verify_v21.py
"""
import sys

sys.path.insert(0, ".")

from pinescan.core import parity           # noqa: E402
from pinescan import nsv2_engine            # noqa: E402

FILES = [
    "fixtures/golden_csv/NSE_DLY_LODHA, 1D.csv",
    "fixtures/golden_csv/NSE_DLY_ITCHOTELS, 1D.csv",
]
SERIES = ["EMA 9", "EMA 21", "B", "A0", "A1", "A2", "A3",
          "ST0", "ST1", "ST2", "ST3", "ENTRY"]


def main():
    params = dict(nsv2_engine.DEFAULTS, retireMissed=True, seedPivotFix=True)
    ok_all = True
    for f in FILES:
        golden = parity.load_tv_csv(f)
        out = nsv2_engine.run(golden, params)
        report = parity.compare(golden, {k: out[k] for k in SERIES})
        print(f"=== {f} ===")
        print(parity.format_report(report))
        ok_all = ok_all and report["passed"]
    print("\nV2.1 PARITY:", "PASS — rules are chart-verified" if ok_all else "FAIL")
    sys.exit(0 if ok_all else 1)


if __name__ == "__main__":
    main()
