# Porting TradingView Pine Script → Python (the reliable way)

Canonical checklist for turning a Pine indicator into a faithful Python scanner.
Distilled from deep research (29 sources, adversarially verified) **and** a real
failure-then-fix in this repo: the `TradingView/ZigZag` dependency was *reconstructed
from assumptions* instead of ported from its real source, synthetic unit tests
passed, and the divergence only surfaced when a user compared A/B against the live
chart. Following this checklist then fixed it exactly (see Case study below).

## The one rule that matters most

**Correctness is proven by a deterministic bar-for-bar diff against data exported
from TradingView itself — NOT by code review, unit tests on synthetic data, or
LLM agents reasoning about the code.**

Agents reason *about code*; they cannot prove *behavioral* equivalence. A
faithful-looking reconstruction of an unseen library passes every code review and
every synthetic test, yet still diverges. Only numeric parity against real
indicator output catches that class of bug. So: golden-master parity testing is the
**primary** mechanism; everything else (including a multi-agent skill) is secondary.

> **Tooling:** this checklist is now executable. The `pine_port/` package
> automates the deterministic steps — `python -m pine_port lint <file.pine>`
> (step 1 + trap flags + plot inventory) and `python -m pine_port parity
> --csv golden.csv --port module:run` (step 7, incl. regression snapshots) —
> and `pine_port/runtime.py` provides Pine-exact `ta.*` building blocks for
> step 6. The agent workflow lives in `.claude/skills/pine-to-python/`.
> See `pine_port/README.md`.

## Pipeline — run this for every port

### 1. Extract dependencies
Scan the indicator for every `import author/library/version` line. You cannot port
what you cannot see. Each import uniquely identifies a dependency (the version is
explicit — there is no "latest").

### 2. Get the REAL library source — never reconstruct
All **published** Pine libraries are open-source by platform rule. But the source is
**NOT auto-fetchable** — `WebFetch`/`WebSearch` only see the JS-rendered docs page,
not the code (confirmed: 4 automated attempts all failed). Retrieving it is
**human-in-the-loop**:
- On TradingView: open the library's script page → **"Source code"**; *or* in the
  Pine editor add `import author/lib/version as x`, hover the import → **"Source
  code"**. Copy the **full** Pine into the repo as `<lib>_v<N>.pine`.
- **Also grab the type definitions** (e.g. the `Settings` type). You need them to
  decode positional constructor calls like `Settings.new(35, 10, na, false, …)` —
  the booleans/strings are meaningless without the field order.

**Version pinning (GAP):** the page shows only the **latest** version's source;
older *pinned* versions (`/7` when `/9` exists) aren't browsable. **Read the release
notes** (these are visible) to confirm whether the algorithm changed between the
pinned and visible version. If the core detection is unchanged, port the visible
source and just account for renamed/added fields. (Real case: ZigZag v7 vs v9 — core
identical; v9 only added `projectionPivots`, which replaced `extendLast` in that
field slot.)

> **STOP GATE — do NOT reconstruct.** If you cannot obtain the real source, **stop
> and get it** (ask the user to paste it). Writing a port from assumptions is the
> exact failure this document exists to prevent. A reconstruction passes every test
> and still diverges.

### 3. Identify the EXACT algorithm
Different libraries with the same name behave very differently — confirm which one
and which version is imported, then read its source:
- Official **`TradingView/ZigZag`**: driven by `depth` (bars for pivot detection) and
  `devThreshold` (min % deviation before direction change); pivots are the
  highest/lowest over N bars **before AND after** the point → confirmed only
  `rightBars` later → inherently repaints/looks ahead.
- Forks (e.g. `Absolute_ZigZag_Lib`): may not use `ta.pivothigh/ta.pivotlow` at all,
  have no depth/deviation params, and repaint by updating the latest pivot in place.

Read the real source; do not work from a generic mental model of "a ZigZag."

**The parameter you pass is NOT the parameter that's used (GAP — the decisive one).**
Names and input values lie; only the real source reveals the actual computation.
Read what the library *does* with each setting:
- **`depth=10` is internally `5`.** The official ZigZag computes
  `depth = max(2, floor(settings.depth / 2))` before detection — so the "Depth" input
  is *halved*. The first port used 10 as a literal min-bars gate → wrong algorithm AND
  wrong value. This single line was the entire CCEP bug.
- **A setting can affect only display, not math.** `differencePriceMode = "Absolute"`
  changes *label text* only; detection always uses **percentage** deviation. Don't
  infer math behavior from a display-oriented input name.
- **Decode positional constructor args against the real type.** A bare `false` in
  `Settings.new(…)` means nothing until you map it to its field — and that field may
  be renamed across versions.
Trace each input from the call site → the type field → every place the library reads
it. Guessing from the input's display name is the anti-pattern.

### 4. Instrument the Pine source — `plot()` every series you want to verify
TradingView's CSV export **only emits values passed to `plot()`** (or
`plotchar`/etc.). Internally-computed series (pivot prices, intermediate state, the
exact A/B levels) are **silently absent** unless you plot them first. Add a `plot()`
for every value you intend to check, including internal/intermediate state.

**Library-internal values need extra work.** Values computed *inside* an imported
library (e.g. the ZigZag `pivots` array) aren't directly plottable. Call the library,
read its output back in your indicator (e.g. `zigZag.pivots.get(i).end.price`), assign
to a variable, and `plot()` that. If you can't surface a value, you can't verify it.

### 5. Export the golden reference
Use TradingView **"Export chart data" → CSV** (OHLC + all plotted series) as the
bar-for-bar oracle. Record **symbol, timeframe, timezone, session, and bar range**.
**Drop/ignore the last bar** (the realtime bar can repaint).
Limitations: requires a **paid plan**; capped (~10k bars Plus / ~20k Premium) and
covers only loaded/visible bars — this bounds how long a golden window you can build.

### 6. Port faithfully — replicate Pine's execution model
- **Bar-by-bar, not vectorized.** Pine executes start→end on each bar sequentially,
  using only data available on that bar. Path-dependent logic (ZigZag, recursive
  EMAs, `var`/`varip` state, pivots) **must** be replicated this way.
- **Gate on confirmed/closed bars** (`barstate.isconfirmed`). Historical bars are
  always confirmed; comparing only closed bars makes output deterministic and
  repaint-proof — the foundation of reproducible parity. (Note: `barstate.isconfirmed`
  is unreliable inside `request.security()`.)
- **Match `ta.*` exactly**: `ema/rma/sma` seeding, `na` propagation (NaN until a
  window fills), rolling-window definitions.
- **Replicate lookahead/offset behavior.** `request.security(..., lookahead_on)`
  without a `[1]` offset leaks future data on historical bars; a naive port reading
  completed bars won't reproduce it unless handled deliberately.

### 7. Differential / characterization test
Assert the Python port reproduces the CSV **bar-for-bar within tolerance**, aligned
on bar timestamps (handle timezone explicitly), **confirmed bars only**, excluding
the last (repainting) bar. Snapshot the passing result as a **regression golden
master**. Tolerance is **not** a known constant — choose it empirically per indicator
and tighten over time (PyneCore's self-reported ~0.001% relative / 1e-8 absolute is a
reasonable starting point, not gospel).

**Cheap interim oracle:** before a full CSV export is available, a single observed
data point from the live chart (e.g. "A=110.90, B=89.72 on these dates") is a strong
smoke test — the faithful ZigZag port matched it exactly while the reconstruction
didn't. Use it to catch gross divergence early; it does **not** replace the full
bar-for-bar test.

> **Reality of the verify half (Steps 5+7):** it is **human-in-the-loop and
> paid-gated** — CSV export needs a paid TradingView plan and a manual user action,
> and is bar-capped (~10–20k). The port is *authored* autonomously; it is *verified*
> only with user-supplied golden data. Plan for that handoff.

## Tooling that reduces hand-porting
- **PyneCore** — open-source (Apache-2.0); replicates Pine's execution model, `na`
  handling, `var`/`varip` persistence, and a Pine-compatible `ta.*` library validated
  against TradingView (tolerances vendor-asserted — still verify with exported data).
- **PyneSys / PyneComp** — actual Pine→Python transpilation, but **closed-source &
  paid** (3 free conversions via Discord, v6, ≤25KB). Use to bootstrap, then verify.
- **pandas-ta / TA-Lib** — convenient, but parity with Pine's `ta.*` seeding and
  `ta.pivothigh/pivotlow` is **unverified** — do not assume their defaults match Pine.

## Where a multi-agent / adversarial skill genuinely helps (secondary layer)
Build it for the upstream scaffolding, not the proof:
- **Dependency discovery** — find every `import` line, fetch the correct handle+version.
- **Pine-semantics review** — flag `na`/`var`/lookahead/`ta.*`-seeding traps.
- **Checklist enforcement** — ensure every series is `plot()`-ed before export.
Do **not** rely on it as the equivalence proof — that's the golden-master test's job.

## Anti-patterns (each one bit us or is a known trap)
- ❌ Reconstructing an imported library from assumptions instead of its real source.
- ❌ Treating "passes synthetic unit tests" as proof of behavioral equivalence
  (synthetic data you authored can't expose a pivot-detection divergence).
- ❌ Vectorizing path-dependent logic.
- ❌ Comparing against the realtime/last bar (it repaints).
- ❌ Assuming pandas-ta/TA-Lib `ta.*` matches Pine without checking seeding.
- ❌ Guessing what an input named "Min Bars Between Pivots" does instead of reading
  the library that consumes it. (Real bite: "Depth = 10" is used as `floor(10/2) = 5`.)
- ❌ Treating the value you *pass* to a library as the value it *uses* — it may be
  transformed (halved, clamped, renamed by version).
- ❌ Inferring math from a display-oriented setting (`"Absolute"` was labels-only).
- ❌ Proceeding to write the port when you couldn't get the real source (STOP instead).

## Open questions to resolve per project
- Exact numeric tolerance + float/timezone alignment scheme (empirical, per indicator).
- Whether webhook/`alertcondition` payloads can build longer golden datasets than the
  bar-capped CSV export.
- How closely pandas-ta / TA-Lib actually match Pine's `ta.*` (needs direct comparison).

## Case study — the ZigZag port (this repo)
The end-to-end proof of every rule above:
1. **Failure:** `pine_engine.py` *reconstructed* the imported `TradingView/ZigZag`
   from assumptions — a running-extreme deviation tracker, `depth=10` used as a
   min-bars gate. Synthetic tests passed; nobody compared to the chart.
2. **Symptom:** on CCEP weekly the scanner reported A=100.67/B=84.66 (an old swing)
   while the chart showed A=110.90/B=89.72. A user caught it by eye.
3. **Diagnosis via this checklist:** got the **real source** (`tradingview_zigzag_v9.pine`,
   user-pasted — not auto-fetchable). It revealed the bug no reasoning could:
   `depth = max(2, floor(settings.depth/2))` (10→**5**), `ta.pivothigh`-style detection,
   `"Absolute"` = labels-only, projection OFF for this indicator.
4. **Fix:** faithful port → `tv_zigzag.py` (confirmed-pivot path; projection omitted).
5. **Verify:** reproduced the chart **exactly** — A=110.90/B=89.72 — where the
   reconstruction did not. (One-point oracle; full CSV golden-master still pending.)

The lesson in one line: **the load-bearing input to the whole strategy was an
external library we never read — get the real source, then prove it against the
chart.** A multi-agent skill would not have caught this; a parity check did.

## Key sources
- Pine execution model: https://www.tradingview.com/pine-script-docs/language/execution-model/
- Bar states / repainting: https://www.tradingview.com/pine-script-docs/concepts/bar-states/ ·
  https://www.tradingview.com/pine-script-docs/concepts/repainting/
- Libraries (open-source rule, imports): https://www.tradingview.com/pine-script-docs/concepts/libraries/
- Export chart data: https://www.tradingview.com/support/solutions/43000537255-how-to-export-chart-data/
- Official ZigZag (depth/devThreshold): https://www.tradingview.com/script/bzIRuGXC-ZigZag/
- PyneCore / PyneSys: https://github.com/PyneSys/pynecore
