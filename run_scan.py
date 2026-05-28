# Runs the scan on the full Nifty 500 and writes results.json (GitHub Actions robot).
from kwm_engine import scan, save_dashboard_json, load_nifty500

SYMBOLS, SECTORS = load_nifty500()        # full Nifty 500, fetched live from NSE
TIMEFRAMES = ["1D", "1H", "15m"]

df = scan(SYMBOLS, TIMEFRAMES, src="close", verbose=False)
df["sector"] = df["symbol"].map(SECTORS).fillna("-")
df = df.sort_values(["signal", "volx"], ascending=[True, False]).reset_index(drop=True)
save_dashboard_json(df, "results.json")
print(f"wrote results.json — {len(df)} setups across {len(SYMBOLS)} names")
