# Dashboard Rebuild Guide — KWM Auto Screener

Everything needed to rebuild the web dashboard and have it behave identically. The working file
(`KWM_Auto_Screener.html`) sits beside this doc; this guide explains its structure and the contracts
it depends on.

---

## What the dashboard is

A single self-contained HTML file — React 18 + Tailwind + Babel loaded from CDNs, no build step. It
reads the engine's `results.json` and presents the scan as an interactive screener with three tabs:
**Scanner**, **History**, **Performance**. Drop it on any static host (Netlify) or open it locally.

**Stack (all via CDN, no bundler):**
- React 18 + ReactDOM (`unpkg`)
- Tailwind (`cdn.tailwindcss.com`)
- Babel standalone (in-browser JSX, `type="text/babel"`)
- Fonts: Archivo + JetBrains Mono (Google Fonts)
- Inline SVG icon components (no icon library dependency)

---

## The data contract

The single most important thing to preserve. The dashboard reads from:

```
const DATA_URL = "https://raw.githubusercontent.com/krishbahri93/kwm-scan/main/results.json";
```

It expects either `{ generated_at, rows: [...] }` or a bare `rows` array. Each row:

```
{ sym, sector, tf, up (bool), sig, zLow, zHigh, ltp, sinceTrig, volX, spike (bool), confMin }
```

`sig` is one of `"Triggered" | "In Zone" | "Approaching"`. This must match the engine's
`save_dashboard_json` output exactly — if you change one side, change the other.

### Three ways data gets in

1. **Auto-fetch** on load and every **90 seconds** (`setInterval(loadFeed, 90000)`), cache-busted with `?t=Date.now()`.
2. **Manual upload** of a `results.json` via a file input (`onUpload` → `ingest`).
3. **Sample/demo data** generated client-side (`buildRows`, seeded PRNG `mulberry32`) when no live
   feed is present — this is why the dashboard looks populated even with no backend. **The History
   and Performance tabs are currently always sample data** (see roadmap to wire real outcomes).

`ingest(j)` normalizes either shape, attaches a stable `id = sym+"-"+tf`, and joins each row to its
`META` entry for universe/sector/tier/F&O classification.

---

## Build order (rebuild from zero)

### Step 1 — Constants & metadata

- `META`: array of `[symbol, sector, tier, fno]` — tier ∈ mega/large/mid/small drives universe
  filtering; `fno` (0/1) drives the F&O universe. `META_BY_SYM` is the lookup.
- `TFS = ["15m","1H","75m","4H","1D","1W"]`
- `UNIVERSES = ["Nifty 500","Nifty 50","Nifty 200","Nifty Midcap 150","Nifty Smallcap 250","Nifty F&O"]`
- `SIGNALS = ["Triggered","In Zone","Approaching"]`
- `inUniverse(m, u)`: maps a META row to whether it belongs in the selected universe.

### Step 2 — Data ingestion (the contract above)

`ingest`, `loadFeed`, `onUpload`, and the 90s `useEffect` interval. Keep the demo fallback so the UI
never renders empty.

### Step 3 — Filter state & derived rows

State: dark mode, tab, universe, sector, tf, signal, spikeOnly, search query `q`, selection set
`sel`, period. `rows` is the memoized filtered view; `counts` drives the summary cards (total /
triggered / in-zone / spikes).

### Step 4 — Scanner tab

The main table. Columns: checkbox, symbol, sector, TF chip, trend (up/down icon), signal pill, entry
zone (`zLow–zHigh`), LTP, since-trigger %, vol ×avg (with a spike bolt at ≥1.8×), confirmed-ago.
Selecting rows enables export.

### Step 5 — Export to TradingView

- `flatString()`: dedup symbols → `NSE:SYM,NSE:SYM,...`
- `sectionString()`: when viewing all TFs, group into `###15m,NSE:...` sections.
- `copyText()` (clipboard, with textarea fallback) and `downloadFile()` (.txt blob).

### Step 6 — History tab

Per-day table: triggered, in-zone, vol spikes, targets hit, hit %, avg gain. Currently from
`buildHistory` (sample).

### Step 7 — Performance tab

Daily/Weekly/Monthly windows, four KPI cards (triggered / targets hit / hit rate / avg gain on
hits), and a triggered-trades table with Hit/Open/Stopped status. Currently from `buildTrades`
(sample). Note the "first touch counts" definition is stated in the footnote — keep it consistent
with the engine's target logic.

### Step 8 — Theming & chrome

Light/dark palettes in the `c` object; brand colors `TEAL #2a7c8f`, `MINT #37c79b`, `CHAR #3b4147`;
top gradient bar; the SEBI disclaimer footer (**keep this verbatim** — it's a compliance statement).

---

## Local preview

Just open the `.html` in a browser. No server needed. To test against live data, ensure the
`results.json` at `DATA_URL` is reachable (CORS-open via GitHub raw — already the case).

---

## Gotchas worth preserving

- **No build step is a feature.** It deploys as one static file. Don't introduce a bundler unless you
  consciously decide to (see roadmap on migrating off Babel-in-browser for speed).
- **`sig` strings are load-bearing.** They key the color map (`SIG`) and the filters. Keep them
  exactly `"Triggered" | "In Zone" | "Approaching"`.
- **History/Performance are sample data today.** Anyone reading those numbers as real will be
  misled — the footer says "sample data," keep it until real outcomes are wired in.
- **The disclaimer footer is a compliance element**, not decoration. Preserve it on any rebuild.
