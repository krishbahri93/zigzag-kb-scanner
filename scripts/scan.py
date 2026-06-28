"""
scan.py — run the V2 scanner over a market's cached universe; write results JSON.

Usage:
    python scripts/scan.py            # US, whole cached universe
    python scripts/scan.py 50         # US, first 50 symbols (quick smoke)

Wired to the US cached data layer for now. Adding a market = import its module and
swap the universe/cache calls (the scanner itself is market-agnostic).
"""
import os
import sys
import json

import pandas as pd

from pinescan import nsv2_engine, nsv2_scanner
from pinescan.markets import us

OUT_PATH = "data/results/nsv2_us.json"


def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    symbols, _sectors = us.select_liquid_universe()
    if limit:
        symbols = symbols[:limit]
    print(f"Loading cache for {len(symbols)} symbols ...")
    cache = us.load_cache(symbols)
    print(f"  cache populated for {len(cache)} symbols")

    rows = []
    scanned = 0
    asof_dates = set()
    for s in symbols:
        df = cache.get(s)
        if df is None or len(df) < nsv2_scanner.MIN_BARS:
            continue
        try:
            r = nsv2_scanner.scan_symbol(s, df)
        except Exception as e:
            if scanned < 3:
                print(f"  error {s}: {str(e)[:120]}")
            continue
        scanned += 1
        if r is not None:
            rows.append(r)
            asof_dates.add(r["asof"])

    # rank: in-band first, then approaching, then by active-swing depth
    rows.sort(key=lambda r: (not r["in_band"], not r["approaching"], -(r["n_swings"])))
    actionable = [r for r in rows if (r["in_band"] or r["approaching"]
                                      or r["fired_entry"]) and not r["expired"]]

    out = {
        "engine": "nsv2 (ZZ KB Nested Swings V2, faithful port)",
        "generated_for_date": str(pd.Timestamp.now(tz="America/New_York").date()),
        "data_asof": max(asof_dates) if asof_dates else None,
        "params": {k: nsv2_engine.DEFAULTS[k] for k in
                   ("minDeclinePct", "pivotSensPct", "zigDepth", "maxSwings",
                    "minGapPct", "useEmaFilter", "useVolFilter")},
        "universe_size": len(symbols),
        "scanned_ok": scanned,
        "setups_total": len(rows),
        "actionable_count": len(actionable),
        "actionable": [r["sym"] for r in actionable],
        "rows": rows,
    }
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(out, f, indent=2, allow_nan=False)
    print(f"\nwrote {OUT_PATH}")
    print(f"  scanned_ok={scanned}  setups={len(rows)}  actionable={len(actionable)}")
    for r in actionable[:25]:
        tag = ("IN-BAND" if r["in_band"] else
               "approaching" if r["approaching"] else "entry-fired")
        print(f"    {r['sym']:6s} {r['active'] or '-':3s} {r['active_state'] or '-':5s} "
              f"{tag:12s} ltp={r['ltp']} B={r['B']} swings={r['n_swings']}")


if __name__ == "__main__":
    main()
