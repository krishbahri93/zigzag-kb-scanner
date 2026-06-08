# US Stocks Scanner

A US-market scanner that runs **alongside** the existing Indian (NSE/Nifty 500)
scanner without modifying it. It reuses the market-agnostic strategy engine and
adds a Polygon.io data layer.

## Strategy engine: `pine_engine.py` (Pine-faithful)

The US scanner runs on **`pine_engine.py`**, a faithful bar-by-bar replica of
`zigzag_kb_fib_dual_trade.pine` (the source of truth) — confirmed-only ZigZag pivots, the
`depth` filter enforced, live B-lowering + state reset, and entries that require
the real EMA/volume + cross confirmation (no price-only "Triggered"). The live
scanner and backtest share one state machine, so they can't disagree.

The **one** intentional deviation from Pine — the only thing kept from the old
scanner — is the **intraday early-notify**: `evaluate(daily_df, today_partial=…)`
can evaluate a live "today-so-far" bar before the daily close and flags any event
fired on it `provisional=True`. On US that bar comes from one Snapshot-All-Tickers
call (Phase 2). `us_kb_engine.scan_us` / `backtest_us` call `pine_engine`; the old
`zigzag_kb_engine.py` is untouched (only its pure `_resample_weekly` is imported).
Tests: `test_pine_engine.py`.

## Design principle: additive, zero-impact on the Indian scanner

These files are **never modified**: `zigzag_kb_engine.py`, `run_scan.py`,
`.github/workflows/scan.yml`, `results.json`, `performance.json`.

The strategy engine is market-agnostic and data-driven (`analyze_one(df=…)`,
`backtest_history(df)`, `save_dashboard_json`, `save_performance_json` all take
data you pass in), so the US side **imports and reuses** it and only provides a
new data layer + universe + orchestrator.

### New files
| File | Role |
|---|---|
| `us_kb_engine.py` | Polygon data layer: universe loader, grouped-daily backfill (throttled + resumable), cache assembly, `scan_us` / `backtest_us` wrappers |
| `run_scan_us.py` | Entry point — select universe → backfill → scan → backtest → write US feeds |
| `.github/workflows/scan_us.yml` | Separate CI workflow (US hours, `POLYGON_API_KEY`, `actions/cache`) |
| `results_us.json` / `performance_us.json` | US output feeds (mirror the Indian schema) |
| `us_cache/` (gitignored) | One parquet per trading date; the local daily-history cache |

The two workflows run in non-overlapping windows and touch different files — no
conflict.

## Data provider: Polygon.io (now "Massive")

- **Tier:** free key is enough to **build + validate on EOD data**. Live
  intraday signals + a 5-min cadence need **Starter ($29/mo)** — see Phases.
- **Verified endpoints (free key):**
  - `GET /v3/reference/tickers?market=stocks&active=true&type=CS` → universe
    (paginated via `next_url`).
  - `GET /v2/aggs/grouped/locale/us/market/stocks/{date}` → **every** ticker's
    OHLCV for one date in a single call (~12k rows). Billed **per date, not per
    symbol**, so 1,000 vs 6,000 symbols costs the same number of calls.

### Why bulk matters
The engine's per-symbol fetch model is infeasible for thousands of US stocks at a
5-min cadence (~12,000 calls/scan). Grouped-daily + (Phase 2) snapshot collapse a
scan to ~2 calls.

## Universe: liquid subset

`select_liquid_universe(n=1000)` pages all active US common stocks, then keeps the
top N by **dollar-volume** (`close * volume`, price ≥ $5) from the most recent
trading day. Cached to `us_universe.json` for run-to-run consistency. Sector is
currently `"-"` (SIC mapping is a later enhancement; the dashboard tolerates it).

## Backfill: resumable, free-tier throttled

`backfill(symbols, days=730)` fetches grouped-daily for each weekday (newest
first), keeps only the selected symbols, and writes one parquet per date in
`us_cache/`. Dates already on disk are skipped, so an interrupted run resumes.
Throttled to ~13s/call (free tier = 5 calls/min) with 429 backoff.

- **2 years ≈ ~500 weekday calls ≈ ~1.75–2 hrs** on the free tier (one-time).
- On Starter (unlimited calls) the same backfill takes minutes; daily updates are
  1 call.

## Phases
- **Phase 1 (now, free key, EOD):** everything above. For completed daily bars the
  reused `classify_signal` correctly reports `provisional=False`, so no timezone
  change is needed.
- **Phase 2 (Starter $29/mo, live):** add `_snapshot_all()` (today's partial bar)
  + 5-min cadence. Because live bars are dated "today," provisional gating needs
  US-Eastern time — add small US-local copies `classify_signal_us` / `analyze_one_us`
  and ET-stamped `save_*_us` wrappers, keeping the shared engine untouched.

## Deviation tuning — US default = 15% (decided 2026-06-08)

The Indian scanner uses **35%** (`DEV_PCT_DEFAULT`), tuned for volatile NSE
midcaps. US large-caps are ~half as volatile (S&P 500 average intra-year drawdown
~14% vs Indian midcaps 25–35%), so 35% is too coarse here. A deviation sweep over
2 years of the top-1000 liquid US names (cached data; no slippage/cost modeling):

```
dev%  setups  trades  win%   avgR   totalR
 15    1127    1752   63.0  +1.90  +3325   <- chosen (US default)
 20    1105    1647   59.4  +1.71  +2815
 25     980    1452   60.1  +1.74  +2521
 30     820    1210   61.8  +1.83  +2212
 35     662    1034   62.0  +1.82  +1877   (Indian default)
 40     545     828   60.1  +1.69  +1401
```

Total R rises **monotonically** as deviation falls, while win-rate and avg-R stay
**flat** (~60–63%, +1.7–1.9R) — i.e. more trades of the *same* quality, not noise.
Entry quality is governed by the EMA+volume+cross+fib confirmation, not the ZigZag
threshold (median traded swing at 15% is still ~28%). 15% won on every metric;
20% was the win-rate *low point* for only ~6% fewer trades, so **15%** was chosen.

Set as the default in `run_scan_us.py` and `scan_us.yml`; override per-run via the
`US_DEVIATION` env var. **Caveat:** in-sample backtest with idealized fills
(exact-level entries, −1R losses, no slippage/commissions); more trades means more
real-world cost drag, though the 15%↔20% trade-count gap is small.

## Run it
```
# Local (free key). First run does the ~2 hr backfill; later runs resume/append.
set POLYGON_API_KEY=<your key>        # PowerShell: $env:POLYGON_API_KEY="<key>"
python run_scan_us.py                 # writes results_us.json + performance_us.json

# Knobs (env): US_N_SYMBOLS=1000  US_BACKFILL_DAYS=730  US_DEVIATION=35.0
```

## Verification
1. **Smoke test:** `US_BACKFILL_DAYS=15 python run_scan_us.py` — confirms the
   pipeline runs end-to-end (universe → backfill → cache → scan → backtest →
   JSON) without errors.
2. **Full run:** default 730 days over 1,000 symbols; inspect setup counts,
   win-rate, avg-R in the US feeds.
3. **Isolation check:** `git status` shows no changes to the Indian files; the
   Indian `run_scan.py` path is unaffected.
4. **Schema check:** US JSON keys match the Indian schema so the dashboard renders.

## Cost
Free to build & validate now. **$29/mo** Polygon Starter for live (Phase 2).
GitHub Actions free for public repos.
