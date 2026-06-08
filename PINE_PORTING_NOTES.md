# Pine→Python porting — run notes

Living notes from dogfooding `PINE_PORTING.md` on
`zigzag_kb_fib_dual_trade.pine` (the real indicator, source of truth). Captures
findings, blockers, and open questions as we go. **After we build the new port,
we revisit the "To compare after the port" section and fold confirmed lessons
back into `PINE_PORTING.md`.**

Run date: 2026-06-08 · Target: replace the flawed `pine_engine.py` ZigZag
reconstruction with a faithful port of the real `TradingView/ZigZag/7` library.

---

## Per-step findings

### Step 1 — Extract dependencies ✅ works as written
One import: `import TradingView/ZigZag/7 as zigzag` (line 41). Unambiguous.

### Step 2 — Get the REAL library source ❌ BLOCKED — biggest gap
**Methodology implies this is easy** ("open the Source code button and port it").
**In practice it is not autonomous.** Failed attempts:
- `WebFetch` of the library page (tradingview.com/script/bzIRuGXC-ZigZag/) → only
  rendered docs/release notes; source is behind a JS code viewer.
- `WebFetch` of the Pine v6 reference (`ta.pivothigh`) → JS-rendered, only nav chrome.
- `WebSearch` (several) → page URL + prose, never the code.
- GitHub → only **forks** (niquedegraaff, Trendoscope) = *different* algorithms;
  porting one would repeat the original sin.

→ **GAP #1:** retrieving the source needs the **user to paste it** (or logged-in
browser automation). The most important step is human-in-the-loop.

→ **GAP #1b:** parameter semantics also need the source. The indicator calls
`zigzag.Settings.new(pricePctDeviation, zigDepth, color(na), false, false, false, false, "Absolute", true)`
— positions 3–9 (booleans, `"Absolute"`, trailing `true`) can't be mapped without the
`Settings` type def. `"Absolute"` vs `"Percent"` changes the deviation mode; trailing
`true` is likely `projectionPivots`/`allowZigZagOnOneBar`. Both were **guessed** in the
first port.

### Step 2c — Version pinning vs retrievable source ⚠️ new gap, RESOLVED
The indicator pins `TradingView/ZigZag/**7**`, but TradingView only shows the **latest
(v9)** source — older pinned versions aren't browsable. **GAP #5:** the methodology
says "fetch the imported version's source" but you often can only see the latest.

**Resolution (works): read the release notes (these ARE visible) to check whether the
algorithm changed between the pinned and visible versions.** For ZigZag:
- v7 (Oct 2023): cosmetic (`Point`→`chart.point`), output unchanged.
- v8 (Mar 2025): Pine v6 upgrade, no algorithm change.
- v9 (Feb 2026): added `projectionPivots` (replaced `extendLast`) — projects/replaces
  unconfirmed pivots.
- **Core detection (algorithm, `depth`, `devThreshold`) identical across v7–v9.**

→ So **port the core from the visible v9 source**; it equals v7 functionally. One
caveat: the `Settings` slot is `extendLast` in v7 vs `projectionPivots` in v9 — port
**v7 semantics** (no projection) since the indicator pins v7. Consequence: v7 has **no
projection pivots**, so the CCEP developing "lower B" is almost certainly the
*indicator's own* recent-downswing/B-invalidation logic, not the library — confirm
during the port.

### Step 3 — Identify exact algorithm ✅ DONE (have real v9 source)
Real source obtained (`tradingview_zigzag_v9.pine`). Exact algorithm, with the
findings that explain the bug:

- **`depth` is HALVED:** `update()` does `depth = max(2, floor(settings.depth/2))`.
  So `zigDepth=10` → **5 bars each side**, not 10. (Smoking gun — the old port used
  10 as a min-bars-between gate.)
- **Pivot detection is `ta.pivothigh/pivotlow`-style** (`findPivotPoint`): candidate
  is the value `depth` bars back; for a high it must be `>=` all `depth` *newer* bars
  and `>` all `depth` *older* bars (asymmetric equality); confirmed `depth` bars
  later. Old port used a running-extreme deviation tracker — **wrong algorithm**.
- **Pivot registration** (`newPivotPointFound`): same-direction more-extreme point
  → *updates* (moves) the last pivot; opposite-direction point → registers a new
  pivot only if `calcDev(lastPivot, point) >= devThreshold` (%). `calcDev` is always
  **percentage**.
- **`differencePriceMode "Absolute"` affects LABELS only**, not detection — deviation
  is always %. (Resolves the open "Absolute mode" question: old %-assumption was right.)
- **`Settings.new` decoded** (v9 field order): `(devThreshold, depth, lineColor,
  projectionPivots, displayReversalPrice, displayCumulativeVolume,
  displayReversalPriceChange, differencePriceMode, draw, allowZigZagOnOneBar)`.
  The indicator passes `(35, 10, na, false, false, false, false, "Absolute", true)`
  → **projection/extend = false** (field 4). So projection pivots are **OFF**; the
  library exposes only *confirmed* pivots. The CCEP "lower B" is therefore the
  *indicator's own* recent-downswing/B-invalidation logic — **confirmed, not the lib**.
  → big simplification: the port can **skip the entire projection machinery**
  (`findProjectionPivot`, `updateProjectionPivot`, the `barstate.islast` block).
- **`allowZigZagOnOneBar` defaults true** (indicator passes 9 args) → a high and low
  pivot may both register on one bar.

→ **GAP #6 (the important one):** the parameter *semantics* (`depth/2`,
pivot-confirmation lag, %-vs-absolute) are invisible from the indicator + docs alone
and were all **guessed wrong** in the first port. Only the real source reveals them.
This is the concrete proof of the methodology's core thesis.

### Step 4 — Instrument Pine (plot every series) ⏳ not started
→ **GAP #2:** "plot every series" gives no mechanics for *library-internal* values.
ZigZag pivots live inside the imported lib; to export them you must read back its
`pivots` array and `plot()` those yourself. Methodology should say so.

### Step 5 — Export golden CSV ❌ BLOCKED — second fundamental gap
→ **GAP #3:** needs a **paid TradingView plan** + **manual user export**. The whole
verify half (steps 5 + 7) is human-in-the-loop, not turnkey. Also unresolved: export
bar-cap (~10–20k) limits the golden window length.

### Step 6 — Port faithfully ⛔ correctly NOT started
Per the methodology's own #1 rule, the right move when source is unavailable is to
**stop and obtain it**, not write a second guess.
→ **GAP #4:** methodology has no explicit "STOP if source unavailable" gate — the very
thing that would have prevented the original reconstruction bug.

### Step 7 — Parity test ⏳ blocked on Steps 5 + 6.

---

## Gap summary (candidate edits to PINE_PORTING.md)
1. **GAP #1** — "fetch real source" is not autonomous; add a human-in-the-loop
   precondition + concrete how-to (Source-code button / hover-import). Incl. **#1b**:
   also grab the `Settings`/type defs to decode param positions.
2. **GAP #2** — document how to export *library-internal* series (read back + plot).
3. **GAP #3** — reframe verify (steps 5+7) as user-provided/paid, not turnkey; note
   the export bar-cap limits golden-window length.
4. **GAP #4** — add an explicit "STOP if source unavailable — do NOT reconstruct" gate.

**Headline:** the methodology is *correct* but **not autonomously executable** — its
two load-bearing steps (obtain real source; obtain golden data) both require the user.

---

## Blockers needing the user
- [ ] **ZigZag source — v9 is fine** (core algorithm == v7 per release notes). Open the
      library page → "Source code", copy the full Pine, paste here or save as
      `tradingview_zigzag_v9.pine`. Include the **`Settings` type definition** so we can
      decode the `Settings.new(...)` arg positions. (Port v7 semantics: `extendLast`,
      not v9's `projectionPivots`.)
- [ ] **Golden CSV export** (paid TV plan) for the parity test — later.

---

## Compared after the port — answers
- **Algorithm:** real lib = `ta.pivothigh/pivotlow` over `depth` bars each side
  (`depth = max(2, floor(setting/2))`), with same-direction-update /
  opposite-direction-deviation registration. Old port = running-extreme deviation
  tracker with `depth` misused as a 10-bar min-gap. **Completely different.**
- **Trailing field:** the indicator passes `false` for projection/extend → projection
  is OFF. The CCEP "lower B" is the **indicator's own** logic, not the library. The
  port omits all projection machinery.
- **"Absolute" mode:** labels only; detection is always %. Old %-assumption was right.
- **Did A/B change:** YES, materially. Faithful port on CCEP weekly (dev=15) returns
  **A=110.90 (2026-02-27), B=89.72 (2026-04-03)** — an **EXACT match to the chart**.
  Old reconstruction returned A=100.67/B=84.66 (an older swing). This is the
  single-point parity verification (Step 7, partial) and it passes exactly.
- **Tuning impact:** wiring this into the full engine will shift A/B across the
  universe → backtest numbers and the 15% deviation pick must be re-derived. NOT yet
  done (next step).
- **Gaps real vs surmountable:** GAP #1 (can't auto-fetch source) real — solved by
  user paste. GAP #5 (version pinning) solved via release-notes check. GAP #6 (hidden
  param semantics, esp. `depth/2`) was the decisive one — only the real source
  revealed it. GAP #3 (golden CSV) still open: we verified one chart data point, not a
  full bar-for-bar CSV.

## Artifacts produced
- `tv_zigzag.py` — faithful port of the ZigZag library (confirmed-pivot path).
  Verified against the CCEP chart.
- `pine_engine.py` — **rewired** to use `tv_zigzag.detect_pivots` (the broken inline
  tracker is gone). Adds no-lookahead: a swing is simulated only from B-confirmation
  (`bi + eff_depth`). `evaluate`/`backtest` signatures unchanged → `us_kb_engine.py`
  untouched. `test_pine_engine.py` rewritten, **6/6 pass**.

## Engine wired + re-tuned (done)
Re-derived the deviation sweep on the FAITHFUL engine (vs the broken-pivot sweep
earlier). The real ZigZag (depth halved → 5) finds far more, finer pivots:

```
            broken pivots        faithful pivots
dev=15:  1127 setups / +3325R   1630 setups / 3758 trades / 66.2% / +2.12R / +7973R
```
Same monotonic shape (total R rises as dev falls; win/avgR flat ~64-66% / +1.9-2.1R),
so **15% remains the correct default** — now validated on real pivots, with stronger
numbers. Feeds regenerated; CCEP reports A=110.9 (matches chart). Indian scanner
verified untouched.

**One nuance to pin with the golden master:** `evaluate` reports CCEP B=89.3, not the
raw pivot 89.72 — the indicator's **B-invalidation** (lower B to a new low while
pre-entry, faithful to the .pine) moved it. Whether the chart shows the raw pivot or
the invalidated B at a given moment is exactly what a full CSV parity test resolves.

## Still open
- **Step 7 full golden master:** still needs a paid-TV CSV export. We have two strong
  point-oracles (CCEP A exact via `tv_zigzag` and via `evaluate`) but not a bar-for-bar
  diff. GAP #3 remains.
- **B-invalidation timing** vs the chart — verify with golden data.
