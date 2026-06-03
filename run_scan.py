# Runs the scan and writes results.json — used by the GitHub Actions robot.
# Designed to run on a schedule (see scan.yml) and commit results.json to the repo.

from zigzag_kb_engine import scan, save_dashboard_json, load_nifty500

# ── Watchlist — edit these to the names you actively want to scan ──
WATCHLIST = [
    "RELIANCE","TCS","HDFCBANK","ICICIBANK","INFY","SBIN","BHARTIARTL","ITC","LT","HINDUNILVR",
    "KOTAKBANK","AXISBANK","BAJFINANCE","MARUTI","SUNPHARMA","TATAMOTORS","TITAN","ULTRACEMCO","ASIANPAINT","NESTLEIND",
    "WIPRO","HCLTECH","JSWSTEEL","TATASTEEL","POWERGRID","NTPC","ADANIENT","ADANIPORTS","M&M","TRENT",
    "DMART","COALINDIA","ONGC","BPCL","HDFCLIFE","SBILIFE","BAJAJFINSV","DLF","IRCTC","PIIND",
    # Add your reference charts here:
    "DEEPAKNTR","TEGA","360ONE","CDSL","GODFRYPHLP","DIXON",
]

TIMEFRAMES = ["1D", "1W"]   # Daily + Weekly per spec
DEVIATION = 35.0            # ZigZag deviation %

print(f"Scanning {len(WATCHLIST)} stocks at {DEVIATION}% deviation, timeframes={TIMEFRAMES}")

# Get sector labels for the dashboard
_, SECTORS = load_nifty500()

# Run the scan
df = scan(WATCHLIST, timeframes=TIMEFRAMES, dev_pct=DEVIATION, verbose=False)

# Write the dashboard feed
save_dashboard_json(df, path="results.json", deviation=DEVIATION, sectors=SECTORS)

print(f"wrote results.json — {len(df)} setups across {len(WATCHLIST)} stocks")
