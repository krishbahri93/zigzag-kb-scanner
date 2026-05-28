# Runs the scan and writes results.json — used by the GitHub Actions robot.
from kwm_engine import scan, save_dashboard_json, load_nifty500

# ── Your 5-minute watchlist — edit these to the names you actively trade ──
WATCHLIST = ["RELIANCE","TCS","HDFCBANK","ICICIBANK","INFY","SBIN","BHARTIARTL","ITC","LT","HINDUNILVR",
             "KOTAKBANK","AXISBANK","BAJFINANCE","MARUTI","SUNPHARMA","TATAMOTORS","TITAN","ULTRACEMCO","ASIANPAINT","NESTLEIND",
             "WIPRO","HCLTECH","JSWSTEEL","TATASTEEL","POWERGRID","NTPC","ADANIENT","ADANIPORTS","M&M","TRENT",
             "DMART","COALINDIA","ONGC","BPCL","HDFCLIFE","SBILIFE","BAJAJFINSV","DLF","IRCTC","PIIND"]

TIMEFRAMES = ["1D", "1H", "15m"]

_, SECTORS = load_nifty500()                      # sector labels for the dashboard
df = scan(WATCHLIST, TIMEFRAMES, src="close", verbose=False)
df["sector"] = df["symbol"].map(SECTORS).fillna("-")
df = df.sort_values(["signal", "volx"], ascending=[True, False]).reset_index(drop=True)
save_dashboard_json(df, "results.json")
print(f"wrote results.json — {len(df)} setups across {len(WATCHLIST)} names")
