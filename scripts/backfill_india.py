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
import os
import sys

# Windows consoles default to cp1252, which can't encode Unicode in some log lines.
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

# The two creds Dhan needs (client id + daily access token).
_DHAN_KEYS = ("DHAN_CLIENT_ID", "DHAN_ACCESS_TOKEN")


def _load_creds():
    """Ensure DHAN_CLIENT_ID + DHAN_ACCESS_TOKEN are in os.environ.

    If both are already set, do nothing. Otherwise read the first `.dhan_creds`
    found (cwd, then ~) as KEY=VALUE lines and set any missing keys. Existing
    environment values win (setdefault). Exits with a clear message if, after
    that, either credential is still missing. Mirrors refresh_data._load_key but
    for two values instead of one.
    """
    if all(os.environ.get(k) for k in _DHAN_KEYS):
        return
    for path in (".dhan_creds", os.path.expanduser("~/.dhan_creds")):
        if not os.path.exists(path):
            continue
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())   # env wins over file
        print(f"  loaded Dhan creds from {path}")
        break
    missing = [k for k in _DHAN_KEYS if not os.environ.get(k)]
    if missing:
        sys.exit(f"Dhan creds not set ({', '.join(missing)}) and no usable "
                 ".dhan_creds file found. Put DHAN_CLIENT_ID=... and "
                 "DHAN_ACCESS_TOKEN=... lines in a file named .dhan_creds here.")


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
