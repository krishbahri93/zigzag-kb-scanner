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


def main():
    ok_all = True
    for f in FILES:
        golden = parity.load_tv_csv(f)
        out = nds_engine.run(golden)
        report = parity.compare(golden, {k: out[k] for k in SERIES})
        print(f"=== {f} ===")
        print(parity.format_report(report))
        ok_all = ok_all and report["passed"]
    print("\nNDS PARITY:", "PASS — short engine is chart-verified" if ok_all else "FAIL")
    sys.exit(0 if ok_all else 1)


if __name__ == "__main__":
    main()
