"""
scan.py — run a scanner over a market's cached universe; write the results JSON.

Thin CLI over pinescan.service.scan_market (the web app calls the SAME function, so the scan logic
lives in one place — see pinescan/service.py).

Usage:
    python scripts/scan.py                   # US, default nsv2 scanner
    python scripts/scan.py --market india    # India
    python scripts/scan.py --scanner nsv2    # pick a registered scanner
"""
import os
import sys
import json
import argparse

# Windows consoles default to cp1252; force UTF-8 so any glyphs print.
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

from pinescan import service, io_safe

_OUT = {"us": "data/results/nsv2_us.json", "india": "data/results/nsv2_india.json"}


def main():
    ap = argparse.ArgumentParser(description="Run a scanner over a market's cache; write results JSON.")
    ap.add_argument("--market", choices=["us", "india"], default="us")
    ap.add_argument("--scanner", default="nsv2")
    args = ap.parse_args()

    out = service.scan_market(args.market, args.scanner)
    path = _OUT.get(args.market, f"data/results/{args.scanner}_{args.market}.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    io_safe.atomic_write_text(path, json.dumps(out, indent=2, allow_nan=False))

    print(f"wrote {path}")
    print(f"  scanned_ok={out['scanned_ok']}  setups={out['setups_total']}  "
          f"actionable={out['actionable_count']}")
    for sym in out["actionable"][:25]:
        print(f"    {sym}")


if __name__ == "__main__":
    main()
