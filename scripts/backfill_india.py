"""
backfill_india.py — pull daily history for the NSE Nifty-500 into the local cache.

Mirrors scripts/refresh_data.py (the US flow), but for India/Dhan: it loads Dhan
credentials, resolves the Nifty-500 universe, and runs the resumable per-symbol
backfill in pinescan.markets.india. Backfill is resumable — symbols already cached
are skipped — so an interrupted run just continues on the next invocation.

Credentials come from the environment or a local, git-ignored `.dhan_creds` file
with KEY=VALUE lines (token refreshes daily, so this is usually rewritten daily):

    DHAN_CLIENT_ID=1234567890
    DHAN_ACCESS_TOKEN=eyJ0eXAiOi...

Usage:
    python scripts/backfill_india.py        # backfill the full Nifty-500
    python scripts/backfill_india.py 25     # smoke: backfill the first 25 symbols
"""
import sys

# Windows consoles default to cp1252, which can't encode Unicode in some log lines.
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass


def _load_creds():
    """Ensure Dhan creds are set, or exit with a clear message.

    Delegates the actual loading to india.ensure_dhan_creds() — the single `.dhan_creds` loader
    shared by every entry point — so the file convention lives in exactly one place. This wrapper
    just turns "still missing" into a friendly exit, since a backfill can't proceed without a token.
    """
    from pinescan.markets import india
    if not india.ensure_dhan_creds():
        sys.exit("Dhan creds not set (DHAN_CLIENT_ID, DHAN_ACCESS_TOKEN) and no usable "
                 ".dhan_creds file found. Put DHAN_CLIENT_ID=... and DHAN_ACCESS_TOKEN=... "
                 "lines in a file named .dhan_creds here.")


def main():
    _load_creds()
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None

    from pinescan.markets import india

    symbols, _sectors = india.get_universe()   # (symbols, {symbol: sector})
    todo = symbols[:limit] if limit else symbols
    print(f"Backfilling daily history for {len(todo)} of {len(symbols)} "
          f"Nifty-500 symbols (resumable — cached symbols are skipped) ...")
    india.backfill(todo)

    # Coverage report: how many symbols landed, plus a sample's date span.
    cache = india.load_cache(todo)
    print(f"\nCoverage: {len(cache)}/{len(todo)} symbols cached.")
    if cache:
        sym = next(iter(cache))
        df = cache[sym]
        print(f"  sample {sym}: {len(df)} bars, {df.index.min()} .. {df.index.max()}")


if __name__ == "__main__":
    main()
