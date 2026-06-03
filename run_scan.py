# Runs the scan and writes results.json — used by the GitHub Actions robot.
# Designed to run on a schedule (see scan.yml) and commit results.json to the repo.

from zigzag_kb_engine import scan, save_dashboard_json, load_nifty500

# Use the full Nifty 500 (auto-loaded from NSE)
SYMBOLS, SECTORS = load_nifty500()

TIMEFRAMES = ["1D", "1W"]   # Daily + Weekly per spec
DEVIATION = 35.0            # ZigZag deviation %

print(f"Scanning {len(SYMBOLS)} stocks at {DEVIATION}% deviation, timeframes={TIMEFRAMES}")

# Run the scan — return_stats=True so we can write a health status to results.json
df, stats = scan(SYMBOLS, timeframes=TIMEFRAMES, dev_pct=DEVIATION,
                 verbose=False, return_stats=True)

# Write the dashboard feed (includes data_status for auth/API failure detection)
save_dashboard_json(df, path="results.json", deviation=DEVIATION,
                    sectors=SECTORS, stats=stats)

print(f"wrote results.json — {len(df)} setups across {len(SYMBOLS)} stocks")
print(f"stats: attempted={stats['attempted']}  fetched_ok={stats['fetched_ok']}  setups={stats['setups']}")
if stats.get("sample_errors"):
    print("sample errors:")
    for e in stats["sample_errors"]:
        print(f"  {e}")

