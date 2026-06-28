# ZigZag Scanner — Build Plan

_Last updated: 2026-06-27_

## Vision

Turn the parity-verified **V2** scanner into a product: a clean, V2-only codebase that
(a) ports TradingView Pine indicators to Python via a repeatable pipeline,
(b) runs them as scanners across multiple markets (US, India) on near-real-time data,
(c) backtests capital-allocation policies over many years, and
(d) serves live results to a React dashboard.

## Decisions (locked)

- **Scope:** V2 (`ZZ KB Nested Swings V2`) only. Drop the Dual-Trade (`pine_engine.py`) and
  Indian-strategy (`zigzag_kb_engine.py`) logic; salvage only their **data-fetching**.
- **Live cadence:** near-real-time **polling** (re-run every few min during market hours on
  1-min / 15-min-delayed bars). No tick streaming — V2 is a swing strategy.
- **Stack:** FastAPI backend + React frontend. **Private** use (no NSE redistribution concern).
- **Markets:** US (Polygon) + India (Dhan) behind one data interface.
- **Backtester:** its own `backtest/` layer; governs **money & portfolio management only**
  (V2's entry/TP/SL stay fixed & verified); **India first**; **Python rule files + JSON policies**.

## Architecture (layers)

```
backend/pinescan/
  core/      Pine→Python toolkit (runtime builtins, tv_zigzag, lint, parity)
  engines/   faithful Pine ports — run(df) -> {series}        (nsv2.py = V2)
  scanners/  engine output -> actionable Setup rows           (base.py + nsv2.py)
  markets/   data sources, one per market, shared interface   (us_polygon.py, india_*.py)
  app/       runner (poll loop) + store + FastAPI api
  backtest/  portfolio simulator + hierarchical rules + JSON policies + metrics
backend/pine/      .pine source of truth + instrumented + library
backend/fixtures/  nsv2_golden.json + the 24-symbol parity CSVs
backend/tests/     unit tests + the parity gate
frontend/          React live dashboard
data/              generated parquet cache (gitignored)
```

Each layer has one job and a clean edge: swap a feed, add an indicator, or change the UI
without disturbing the others.

## Adding a new scanner (the reusable pipeline)

1. Port the Pine → `engines/<name>.py` (using `core/` + the `pine-to-python` skill).
2. Instrument the Pine, export a golden CSV, `parity` it green.
3. Write `scanners/<name>.py` (interpret the engine output into Setups).
4. Register it — the runner picks it up across every configured market.

## Phases

1. **Restructure** ← *current.* Stand up the package; move engine/scanner/toolkit; refactor
   the data layer; drop the old strategies. **Done = all tests + 24-symbol parity still green.**
2. **Backtester (India first)** — portfolio simulator + rule hierarchy + JSON policies +
   metrics & policy comparison. See `backtest/` design below.
3. **Backend** — runner (poll loop) + store + FastAPI endpoints.
4. **Frontend** — React live dashboard (filter market→scanner→stage, drill-down, auto-refresh).

## Backtester design (Phase 2)

- **Simulator** replays the timeline day-by-day for one market: mark-to-market open positions →
  close any that hit the scanner's TP/SL → for each new signal ask the rules *take it?* (open if
  cash covers a full position and under the max; else invoke the **rotation** rule to free
  capital). Record equity daily.
- **Rules** are hooks the simulator calls (`position_size`, `can_open`, `should_take`,
  `free_capital`), organized by category (`capital/ sizing/ selection/ rotation/ exit/`), each a
  small Python file carrying its plain-English description.
- **Policies** are JSON configs composing rules + params (the "options" you compare).
- **English ↔ code never drift:** `report.py` generates the hierarchy tree from the rule
  descriptions + the policy.
- **Metrics:** return %, CAGR, max drawdown, win rate, avg R, % capital utilized,
  signals-skipped-for-no-cash, rotations-triggered. Configurable costs (brokerage + slippage; STT).

## Open data considerations (India-first)

- **India daily history:** the backtest needs reliable multi-year Nifty-500 daily bars. Dhan
  serves both the daily history (backfilled to parquet like the US layer) and the live feed —
  one authenticated provider for the whole India side, no second EOD source.
- **V2-on-India parity (recommended checkpoint):** export 2-3 NSE charts from TradingView and
  parity-check before trusting India backtest numbers. The engine is market-agnostic and
  US-verified across 24 symbols, so this is a sanity check, not a rebuild.
- **Live data cost (Phase 3/4 only):** Polygon Developer ~$79/mo (US intraday),
  Dhan ~₹499/mo (India). Backtesting + EOD work need neither.

## Data sources / API keys (researched 2026-06)

- **US:** Polygon/Massive — already integrated. Developer $79/mo = 15-min-delayed minute+daily
  bars + websocket, 10y history (plenty for a swing scanner). Alpaca $99 = true real-time
  (requires rewrite). Advanced $199 = real-time, no rewrite.
- **India:** Dhan Data API ₹499/mo (already integrated; 1-yr key, programmatic token). Fyers =
  free (5,000-symbol WS, best free history) as backup/primary. NSE data is personal-use only.
