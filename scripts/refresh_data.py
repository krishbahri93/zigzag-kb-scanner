"""
refresh_data.py — pull the latest US daily data, then run the V2 scan.

Reads POLYGON_API_KEY from the environment or a local, git-ignored `.polygon_key`
file. Backfill is resumable — only the trading days missing from the cache are
fetched — then scan.py replays the V2 scanner over the refreshed cache.

Usage:
    python scripts/refresh_data.py        # refresh + scan full cached universe
    python scripts/refresh_data.py 50     # refresh, then scan first 50 symbols
"""
import sys

# Windows consoles default to cp1252, which can't encode Unicode in some log lines.
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass


def _load_key():
    """Ensure POLYGON_API_KEY is set, or exit with a clear message. Delegates the actual loading
    to us.ensure_api_key() — the single `.polygon_key` loader shared by every entry point — so the
    file convention lives in exactly one place (mirrors backfill_india._load_creds on the Dhan side)."""
    from pinescan.markets import us
    if not us.ensure_api_key():
        sys.exit("POLYGON_API_KEY not set and no .polygon_key file found. "
                 "Put your key in a file named .polygon_key in this folder.")


def main():
    _load_key()
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None

    from pinescan.markets import us
    import scan   # scripts/ is on sys.path[0] when run as `python scripts/refresh_data.py`

    symbols, _ = us.select_liquid_universe()
    print(f"Refreshing daily history for {len(symbols)} symbols "
          f"(resumable — only missing recent days are fetched) ...")
    us.backfill(symbols, days=730)
    print("Backfill done. Running V2 scan ...\n")

    sys.argv = [sys.argv[0]] + ([str(limit)] if limit else [])
    scan.main()


if __name__ == "__main__":
    main()
