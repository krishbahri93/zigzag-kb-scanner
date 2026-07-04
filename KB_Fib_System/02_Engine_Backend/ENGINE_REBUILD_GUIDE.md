# Engine Rebuild Guide — KWM Scanner

This is everything needed to rebuild the Python scanning engine from scratch and have it match the
original. The working code sits beside this file (`kwm_engine.py`, `run_scan.py`); this doc explains
**what each piece must do and why**, so a fresh implementation reproduces the same behavior.

---

## What the engine is

A Python port of the indicator's golden-zone geometry that runs over the whole Nifty 500 instead of
one chart. It fetches OHLCV, finds the dominant A→B swing per symbol per timeframe, computes the
entry pocket, classifies the latest close as Approaching / In Zone / Triggered, and writes a
`results.json` the dashboard reads.

**Files:**
- `kwm_engine.py` — all the logic (config, data fetch, pivots, analysis, scan, JSON export).
- `run_scan.py` — the thin runner the GitHub Action calls: defines the watchlist, runs the scan, writes `results.json`.

---

## Build order (rebuild from zero)

### Step 1 — Config block

Constants that define the system. Reproduce exactly:

```python
GOLDEN   = (0.618, 0.68)   # entry pocket edges (the golden zone)
VOL_AVG  = 20              # bars for average-volume baseline
VOL_SPIKE = 1.8            # ×avg that counts as a display "spike"
PROX     = 0.03            # within 3% below the pocket = "Approaching"

PIV   = {"15m":5, "1H":8, "75m":5, "4H":6, "1D":10, "1W":6}      # pivot strength per TF
LOOK  = {"15m":120,"1H":160,"75m":120,"4H":120,"1D":450,"1W":160} # dominant-swing lookback
TF_MIN = {"15m":15,"1H":60,"75m":75,"4H":240,"1D":375,"1W":1875}  # minutes per bar
```

### Step 2 — Universe loader

`load_nifty500()` fetches the official NSE Nifty 500 CSV
(`archives.nseindia.com/.../ind_nifty500list.csv`) with a browser User-Agent, returns
`(symbols, {symbol: sector})`. On any failure it must fall back to a hardcoded ~20-name shortlist so
the scan never dies on a network hiccup.

### Step 3 — Data layer (two sources, switchable)

Driven by env var `KWM_DATA_SOURCE` (`yahoo` default, or `dhan`).

- **Yahoo path** (`fetch`): `yfinance.download(symbol + ".NS", ...)`. Native intervals defined in
  `YF_NATIVE = {"15m":("15m","60d"), "1H":("60m","730d"), "1D":("1d","3y"), "1W":("1wk","5y")}`.
  Flatten any MultiIndex columns, keep OHLCV, convert tz to Asia/Kolkata.
- **Dhan path** (`_dhan_candles`): real-time, **read-only** — fetches candles only, never touches an
  order endpoint. Builds a security-id map from Dhan's scrip-master CSV (NSE EQ/BE only). Throttles
  ~0.15s between calls. Intraday limited to ~88 days/request.
- **Resampling** (`_bucket_resample`): 75m = 5×15m bars bucketed within each trading day; 4H =
  4×60m bars. Weekly via `_to_weekly` (resample `W-FRI`).
- `get_tf(symbol, tf)` is the single dispatcher both paths route through.

### Step 4 — Pivots

`find_pivots(arr, left, right)` returns indices of confirmed pivot highs and lows. A bar is a pivot
high if it's strictly greater than all `left` bars before and ≥ all `right` bars after (mirror for
lows). The `right`-side requirement is what makes a pivot "confirmed" (it needs future bars).

### Step 5 — Core analysis (`analyze`)

This is the heart. For one OHLCV frame at one timeframe:

1. Bail if fewer bars than `max(PIV[tf]*2+5, VOL_AVG+2)`.
2. Find all pivot highs/lows on the chosen source (`close` by default).
3. Restrict to pivots within `LOOK[tf]` bars; pick the **dominant swing** = highest pivot high
   (`hi_p`) and lowest pivot low (`lo_p`). Require `hi_p > lo_p`.
4. **Trend direction:** `is_up = hi_i >= lo_i` (whichever extreme is more recent sets the trend).
5. `level(r)` returns the price at fib ratio `r`, measured from the dominant extreme — **same
   formula as the Pine indicator** (this is the line that must match the chart).
6. Entry pocket = `level(0.618)`..`level(0.68)`, sorted into `z_lo`..`z_hi`.
7. Classify last close: above `z_hi` → **Triggered**; inside → **In Zone**; below but within
   `PROX` → **Approaching**; else drop.
8. Volume multiple `volx` = last volume / mean of prior `VOL_AVG` bars; `spike = volx >= VOL_SPIKE`.
9. If Triggered, walk back to the first cross above `z_hi` to compute **since-trigger %** and
   **confirmation bars**.
10. Compute the **target** as the touch of the reversed (upper) pocket.
11. Return a dict with tf, trend, signal, zlow, zhigh, ltp, since, volx, spike, conf_min, target.

### Step 6 — Scan + export

- `scan(symbols, timeframes, src, verbose)` loops symbol × timeframe, collects non-None analyses
  into a DataFrame with a fixed column order.
- `tradingview_string(df)` builds a TradingView-importable watchlist (`NSE:` prefixes, optional
  `###TF` sections).
- `rows_for_dashboard(df)` + `save_dashboard_json(df, path)` write `results.json` in the dashboard's
  exact row schema with a `generated_at` timestamp.

### Step 7 — Runner (`run_scan.py`)

Defines `WATCHLIST` (the 5-minute active list), `TIMEFRAMES = ["1D","1H","15m"]`, loads sector
labels, runs `scan`, sorts by signal then volume, writes `results.json`. Keep it thin — all logic
lives in the engine.

---

## results.json schema (the contract with the dashboard)

```json
{
  "generated_at": "14:35 06 Jun",
  "rows": [
    {
      "sym": "RELIANCE", "sector": "Energy", "tf": "1D",
      "up": true, "sig": "Triggered",
      "zLow": 2840.0, "zHigh": 2910.0, "ltp": 2955.0,
      "sinceTrig": 1.55, "volX": 2.1, "spike": true, "confMin": 750
    }
  ]
}
```

If you change this schema, change the dashboard's row parser in lockstep (see Dashboard guide).

---

## Local run

```bash
pip install yfinance pandas numpy requests dhanhq
# free Yahoo data:
python run_scan.py
# real-time Dhan data:
KWM_DATA_SOURCE=dhan DHAN_CLIENT_ID=xxx DHAN_ACCESS_TOKEN=yyy python run_scan.py
```

Output: `results.json` (+ `kwm_scan.csv` and `kwm_watchlist.txt` when run from the notebook).

---

## Gotchas worth preserving

- **The `level()` formula must match Pine.** If the chart and scanner disagree on zone prices, this
  is the first suspect.
- **Dhan adapter stays read-only.** Never add an import of an order function to that file.
- **Token expiry:** Dhan access tokens expire ~24h — the runner will silently fall back to errors if
  stale. Regenerate and update the secret.
- **NSE CSV is rate-sensitive.** The browser User-Agent header is required; without it the fetch 403s.
