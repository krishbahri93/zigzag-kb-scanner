# US scanner entry point — mirror of run_scan.py for the US market.
# Selects a liquid universe, backfills daily history from Polygon (resumable),
# runs the scan + backtest, and writes results_us.json + performance_us.json.
#
# The Indian scanner (run_scan.py / zigzag_kb_engine.py / scan.yml) is untouched;
# this reuses the market-agnostic strategy via imports and writes separate files.
#
# Env:
#   POLYGON_API_KEY   Polygon key (free tier OK for EOD)
#   US_N_SYMBOLS      universe size (default 1000)
#   US_BACKFILL_DAYS  history window in days (default 730 ≈ 2 yr, free-tier cap)
#   US_DEVIATION      ZigZag deviation % (default 35)

import os
import sys

# Windows consoles default to cp1252, which can't encode the Unicode in some log
# lines. Force UTF-8 so a print never crashes the run (Linux/CI is UTF-8 already).
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

from us_kb_engine import (
    select_liquid_universe, backfill, load_cache, scan_us, backtest_us,
    save_dashboard_us, save_performance_us,
)

N_SYMBOLS = int(os.environ.get("US_N_SYMBOLS", "1000"))
BACKFILL_DAYS = int(os.environ.get("US_BACKFILL_DAYS", "730"))
# US default deviation = 15% (NOT the Indian 35%). US large-caps are ~half as
# volatile as Indian midcaps, and a 2-yr sweep over the top-1000 liquid US names
# showed total backtest R rising monotonically as deviation fell (35%->+1877R,
# 15%->+3325R) while win-rate/avg-R stayed flat — more trades of equal quality,
# not noise. 15% won on every metric. See US_STOCKS_PLAN.md "Deviation tuning".
# Override with the US_DEVIATION env var.
DEVIATION = float(os.environ.get("US_DEVIATION", "15.0"))
TIMEFRAMES = ["1D", "1W"]
BACKTEST_WINDOW_DAYS = 365

# ----- Universe -----
print(f"Selecting top {N_SYMBOLS} liquid US common stocks …")
symbols, sectors = select_liquid_universe(n=N_SYMBOLS)

# ----- Backfill (resumable; ~2 hr first time on the free 5-calls/min tier) -----
print(f"Backfilling {BACKFILL_DAYS} days of daily history …")
backfill(symbols, days=BACKFILL_DAYS)

print("Loading cache …")
cache = load_cache(symbols)
print(f"  cache populated for {len(cache)} symbols")

# ----- Scan (current setups) -----
print(f"Scanning {len(symbols)} stocks at {DEVIATION}% dev, tfs={TIMEFRAMES}")
df, stats = scan_us(symbols, cache, timeframes=TIMEFRAMES, dev_pct=DEVIATION)
save_dashboard_us(df, path="results_us.json", deviation=DEVIATION,
                  sectors=sectors, stats=stats)
print(f"wrote results_us.json — {len(df)} setups, "
      f"stats: attempted={stats['attempted']} fetched_ok={stats['fetched_ok']} "
      f"setups={stats['setups']}")

# ----- Backtest (historical performance) -----
print(f"\nBacktesting last {BACKTEST_WINDOW_DAYS} days …")
trades = backtest_us(symbols, cache, timeframes=TIMEFRAMES, dev_pct=DEVIATION,
                     window_days=BACKTEST_WINDOW_DAYS, sectors=sectors)
save_performance_us(trades, path="performance_us.json",
                    window_days=BACKTEST_WINDOW_DAYS)
print(f"wrote performance_us.json — {len(trades)} completed historical trades")
if trades:
    wins = sum(1 for t in trades if t["outcome"] == "win")
    avg_r = sum(t["r_multiple"] for t in trades) / len(trades)
    print(f"  Quick stats: {wins}/{len(trades)} wins "
          f"({wins/len(trades)*100:.1f}%), avg R = {avg_r:+.2f}")
