---
name: pine-to-python
description: Use when porting, converting, or translating a TradingView Pine Script (indicator, strategy, or library) to Python, when writing Python that must match a TradingView chart's signals, or when an existing Python port's output diverges from the chart.
---

# Pine Script → Python, with zero behavioral differences

## Overview

**The only proof of equivalence is a bar-for-bar diff against data exported
from TradingView itself.** Code review, synthetic unit tests, README blurbs,
and agent reasoning all pass on ports that are wrong. Everything below exists
to get you to that diff. Full methodology + case study: `PINE_PORTING.md`
(this repo). Deterministic tooling: the `pine_port` package (copy/install it
into the target project).

## Warn the user upfront

Before any work, tell the user two things:

1. **Every `import author/Lib/N` line requires THEM to copy-paste the
   library's full Pine source** (TradingView script page → "Source code",
   including type definitions). Library source is NOT auto-fetchable —
   WebFetch/WebSearch only see the JS docs shell. This is the #1 schedule
   risk; surface it in your first reply.
2. **Verification requires THEM to export a golden CSV** from TradingView
   ("Export chart data", paid plan, ~10–20k bar cap) after instrumentation.

## Workflow

| Step | Action | Tool |
|---|---|---|
| 1 | Pre-port analysis: imports, traps, plotted series | `python -m pine_port lint file.pine` |
| 2 | **STOP GATE**: obtain real library source (user paste). No source → no port. | human |
| 3 | Pinned version older than visible? Read release notes; confirm algorithm unchanged | human + you |
| 4 | Port bar-by-bar with Pine-exact builtins | `pine_port.runtime` |
| 5 | Instrument Pine: `plot()` every series to verify (CSV exports ONLY plotted series; library-internal values must be read back and plotted) | you → user |
| 6 | User exports golden CSV; record symbol/timeframe/timezone | human |
| 7 | Bar-for-bar diff; last bar dropped (it repaints); na-aware; explicit tolerance | `python -m pine_port parity --csv golden.csv --port mod:run` |
| 8 | On pass, snapshot as regression golden master | `--snapshot golden.json` |

## Non-negotiable porting rules

- **Never reconstruct an imported library from its name/README/docs.** Real
  case: `TradingView/ZigZag` silently computes `depth = floor(input/2)` — a
  reconstruction passed every synthetic test and diverged on the chart.
  The value you *pass* is not necessarily the value the library *uses*.
- **Never use pandas `ewm`, pandas-ta, or TA-Lib for Pine `ta.*`.**
  `ewm(span=n, adjust=False)` seeds from the first value; Pine's `ta.ema`
  seeds with `sma(src, n)` and is na until the window fills → head-of-series
  divergence. Use `pine_port.runtime` (Pine-published recursions) or
  implement from Pine's reference equivalent.
- **Never vectorize path-dependent logic** (`var`/`varip` state, ZigZag,
  pivots, trailing stops). Pine executes bar-by-bar; so must the port
  (`pine_port.runtime.Series`).
- **Pivots confirm late**: `ta.pivothigh(l, r)` emits the value `r` bars
  after the pivot bar. Equality semantics are unpublished — pivots MUST be
  covered by the golden CSV.
- **Parity compares confirmed bars only**: drop the last bar (repaints);
  na-on-one-side counts as divergence (`np.allclose` gets this wrong).
- A single observed chart value (e.g. "A=110.90 on 2026-02-27") is a useful
  smoke oracle before the CSV arrives — it is not the proof.

## Runtime quick reference

`pine_port.runtime` uses Pine's own names — don't invent wrappers:
`na, is_na, nz, Series` · `sma, ema, rma, wma, vwma` · `change, mom, cum,
highest, lowest, highestbars, lowestbars` · `crossover, crossunder, cross` ·
`tr, atr, rsi, stdev` · `valuewhen, barssince, pivothigh, pivotlow`.
All are causal whole-series functions (`out[i]` uses only bars `<= i`).
Docstrings flag any detail that is **UNVERIFIED vs TV** — those must be
exercised by the golden CSV.

## Red flags — STOP, you are about to ship a divergent port

- "The function name/README tells me enough to implement it"
- "I'll approximate the library and refine later"
- "ewm/pandas-ta is close enough to Pine"
- "Synthetic tests pass, so it matches the chart"
- "I'll vectorize this var-state loop for speed"
- "allclose passes" (without na handling / last-bar drop)
- Claiming success without a parity run against user-exported data

Each of these reproduces a documented, real failure (see the case study in
`PINE_PORTING.md`).
