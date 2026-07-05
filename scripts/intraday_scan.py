"""intraday_scan.py — one market-hours scan tick (run by pinescan-scan-india.timer
every 15 minutes, 09:00–15:45 IST on weekdays).

Scans the cached universe with TODAY'S live partial bar merged in memory (see
service.intraday_tick). Writes only the scan-result JSON the dashboard serves —
never the price cache and never the forward test; those belong to the 15:55 close
run. Outside market hours this degrades to a harmless re-scan of cached data.

Usage:
    python scripts/intraday_scan.py
"""
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass


def main():
    from pinescan import service
    r = service.intraday_tick("india")
    print(f"  {r['msg']}")
    sys.exit(0 if r["ok"] else 1)


if __name__ == "__main__":
    main()
