# Runs the scan AND backtest, writes results.json + performance.json.
# Used by GitHub Actions on the scheduled cron.

from zigzag_kb_engine import (
    scan, save_dashboard_json, load_nifty500,
    backtest_all, save_performance_json,
)

SYMBOLS, SECTORS = load_nifty500()
TIMEFRAMES = ["1D", "1W"]
DEVIATION = 35.0
BACKTEST_WINDOW_DAYS = 365   # 12-month backtest window

# ----- Scan (current setups) -----
print(f"Scanning {len(SYMBOLS)} stocks at {DEVIATION}% dev, tfs={TIMEFRAMES}")
df, stats = scan(SYMBOLS, timeframes=TIMEFRAMES, dev_pct=DEVIATION,
                 verbose=False, return_stats=True)
save_dashboard_json(df, path="results.json", deviation=DEVIATION,
                    sectors=SECTORS, stats=stats)
print(f"wrote results.json — {len(df)} setups, "
      f"stats: attempted={stats['attempted']} fetched_ok={stats['fetched_ok']} setups={stats['setups']}")

# ----- Backtest (historical performance) -----
print(f"\nBacktesting last {BACKTEST_WINDOW_DAYS} days …")
trades = backtest_all(SYMBOLS, timeframes=TIMEFRAMES, dev_pct=DEVIATION,
                      window_days=BACKTEST_WINDOW_DAYS, sectors=SECTORS, verbose=False)
save_performance_json(trades, path="performance.json", window_days=BACKTEST_WINDOW_DAYS)
print(f"wrote performance.json — {len(trades)} completed historical trades")
if trades:
    wins = sum(1 for t in trades if t["outcome"] == "win")
    avg_r = sum(t["r_multiple"] for t in trades) / len(trades)
    print(f"  Quick stats: {wins}/{len(trades)} wins ({wins/len(trades)*100:.1f}%), avg R = {avg_r:+.2f}")

