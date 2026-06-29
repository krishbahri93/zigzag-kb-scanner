"""
forward_run.py — advance the paper forward-test by one day and render the markdown dashboard.

Thin CLI over pinescan.service: `service.refresh_market` + `service.forward_standings` do the work
(the web app calls the SAME functions — one compute, two front-ends). This script adds only the
markdown dashboard renderer + a console summary. See pinescan/service.py for the engine and the
"forward = backtest on a growing cache" rationale.

USAGE
  python scripts/forward_run.py --market us                 # warm ~6mo on first init, then locked
  python scripts/forward_run.py --market us --start today   # pure forward (first init only)
  python scripts/forward_run.py --market us --no-refresh    # use the cache as-is (no network)
"""
import os
import sys
import argparse
import datetime as dt

# Windows consoles default to cp1252; force UTF-8 so the Rs / $ glyphs print.
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

from pinescan import service, study, io_safe

REPORT_DIR = "reports/forward"


def _px(v, sym):
    """Per-share price with 2 decimals (study.money rounds to whole units — too coarse for a quote)."""
    return "N/A" if v is None else f"{sym}{v:,.2f}"


def _write_dashboard(market, data):
    """Render the markdown dashboard from service.forward_standings' plain data. The web app renders
    the SAME data as HTML, so this is just the CLI's view — one compute, two front-ends."""
    meta = data["meta"]
    cur = meta["currency"]
    L = [f"# Forward test — {meta['title']}",
         "",
         f"_Paper trading since **{meta['since']}** · data through {meta['last']} · starting capital "
         f"{meta['capital']} per account · all 5 strategies on the same V2 signals._",
         "",
         "## Standings",
         "| Strategy | Equity | Return | Realized win% | PF | Open | Closed |",
         "|---|---|---|---|---|---|---|"]
    for s in data["standings"]:
        L.append(f"| {s['strategy']} | {study.money(s['equity'], cur)} | {study.pct(s['return_pct'])} | "
                 f"{study.num(s['win_pct'], 0)}% | {study.num(s['pf'])} | {s['n_open']} | {s['n_closed']} |")
    for b in data["benchmark"]:
        L.append(f"| _{b['name']} (buy & hold)_ |  | {study.pct(b['return_pct'])} |  |  |  |")
    L.append("")

    L.append("## Open positions (marked to last close)")
    any_open = False
    for s in data["standings"]:
        ps = data["positions"][s["strategy"]]
        if not ps:
            continue
        any_open = True
        L.append(f"### {s['strategy']} — {len(ps)} open")
        L.append("| Symbol | Entry | Now | Unrealized P&L | Days held | Swing |")
        L.append("|---|---|---|---|---|---|")
        for p in ps:
            L.append(f"| {p['symbol']} | {_px(p['entry'], cur)} | {_px(p['now'], cur)} | "
                     f"{study.money(p['pnl'], cur)} | {p['days']} | {p['swing']} |")
        L.append("")
    if not any_open:
        L.append("_None yet — no funded positions are open._")
        L.append("")

    os.makedirs(REPORT_DIR, exist_ok=True)
    io_safe.atomic_write_text(os.path.join(REPORT_DIR, f"{market}.md"), "\n".join(L))


def main():
    ap = argparse.ArgumentParser(description="Advance the paper forward-test by one day, per market.")
    ap.add_argument("--market", choices=["us", "india"], required=True)
    ap.add_argument("--start", default=None,
                    help="warm (default ~6mo) | today | YYYY-MM-DD — FIRST init only, then locked")
    ap.add_argument("--no-refresh", action="store_true", help="use the cache as-is (no network)")
    args = ap.parse_args()
    market = args.market

    # Refresh today's bar (weekdays only). Non-fatal: fall back to the existing cache on any failure.
    if not args.no_refresh and dt.date.today().weekday() < 5:
        print(f"Refreshing {market} data ...")
        try:
            r = service.refresh_market(market)
            if not r["ok"]:
                print(f"  WARNING: {r['msg']} — using the existing cache.")
        except Exception as e:
            print(f"  WARNING: data refresh failed ({str(e)[:140]}); using the existing cache.")
    else:
        print("  (skipping data refresh — weekend or --no-refresh)")

    data = service.forward_standings(market, args.start)
    if data is None:
        sys.exit("No cached symbols — run the backfill first.")

    for s in data["standings"]:
        print(f"  {s['strategy']:24s} ret {study.pct(s['return_pct']):>9s}  "
              f"{s['n_open']} open · {s['n_closed']} closed")
    _write_dashboard(market, data)
    print(f"\nWrote {REPORT_DIR}/{market}.md  (forward test since {data['meta']['since']}, "
          f"data through {data['meta']['last']}).")


if __name__ == "__main__":
    main()
