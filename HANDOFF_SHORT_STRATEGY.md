# HANDOFF — Build a SHORT-ONLY version of "ZZ KB Nested Swings V2"

> **Purpose of this file:** the user (Krish) is starting a fresh chat to build a
> short-only mirror of his working long-only TradingView indicator. This file is
> the complete context. Read it fully before doing anything.

---

## 1. Who you're working with (IMPORTANT — read first)

- The user has **no coding experience**. Explain everything step by step, in
  plain language, over-explain rather than under-explain. Define jargon.
- **Never overwrite his existing working files.** All new work goes in a
  **new, separate file**. (He caught an early overwrite once — don't repeat it.)
- **Git safety:** work on a branch, never commit to `main`, and **do not commit
  at all without his explicit go-ahead** (he once rejected a commit mid-command).
  Do not push, merge, or delete branches unless he asks.
- He verifies everything **manually in TradingView** (paste script → Pine Editor
  → Add to chart). You cannot compile Pine locally. If he reports a red error,
  ask for the exact error text + line number.
- His style: he shares chart screenshots as observations in batches, then says
  "I'm ready" — hold fixes until then, log each observation briefly.
- Push back when warranted. He explicitly asked: "don't simply agree with me,"
  "don't fix one thing and spoil another," "don't disturb the accuracy."

## 2. Project layout (repo: `D:\Coding Folder\zigzag-kb-scanner`)

| File | What it is | Touch? |
|---|---|---|
| `zigzag_kb_Indicator_pinescript.txt` | His ORIGINAL single-setup dual-trade indicator (proven at 35% deviation) | **Never modify** |
| `zigzag_kb_Indicator_nested_pinescript.txt` | V1 nested experiment (superseded) | Leave as-is |
| `zigzag_kb_Indicator_nested_v2_pinescript.txt` | **"ZZ KB Nested Swings V2" — the current working LONG indicator.** 3 weeks live-tested, user rates it ~70% of a perfect semi-auto plotter and is happy | **Reference / template — do not modify.** The short version goes in a NEW file |
| `ZZ_KB_Nested_Swings_V2_Strategy_and_Logic.pdf` | Shareable strategy+logic doc | Leave |
| `zigzag_kb_engine.py`, `run_scan.py`, `results.json`, etc. | Python scanner (separate system, git-tracked, runs on a schedule) | **Never modify** |
| `KB_Fib_System/` | His documentation package (rules master, version history, etc.) | Read-only reference |

Git state at handoff: everything above except the Python side is **untracked**;
current branch `nested-a-staircase-trades` (empty, nothing committed). Fine to
create a new branch for the short work if committing is ever requested.

**Suggested new file name:** `zigzag_kb_Indicator_short_v1_pinescript.txt`
**Suggested indicator name:** `"ZZ KB Nested Swings SHORT V1"`.

## 3. The LONG strategy (what V2 does — the thing to mirror)

**Concept:** after a stock falls sharply and starts recovering, buy the recovery
and take profit at the prior peaks of the decline — repeatedly, like a relay.

- **B (common low):** the low of the most recent *confirmed* decline of at
  least `Min Decline %` (default **35**, adjustable).
- **Nested peaks T1..T4:** the descending lower-highs of the decline into B,
  found **nearest-first** walking backward in time from B with a finer detector
  (`Peak Sensitivity %`, default **25**). **T1 = the peak NEAREST to B** (this
  was the single most important design decision — his manual markings were
  unanimous on it). T4 = highest/furthest.
- **Fib ladder per peak** (measured from B UP to that peak, fraction of A−B):
  - `0.236` → stop-loss line
  - `0.32–0.382` → entry zone
  - `0.618–0.68` → golden take-profit zone
- **Per-trade rules (identical for every peak):**
  - **Entry:** confirmed close crosses **above 0.382** + close > EMA9 & EMA21
    + volume > 1.2× 20-bar SMA
  - **TP:** high touches **0.618** (first touch)
  - **SL:** confirmed close **below 0.236** → back to "waiting" (setup not dead)
- **Relay effect:** each trade's golden TP zone ≈ the next trade's entry zone,
  so trades hand off T1→T2→T3→T4 as price climbs. No hard lockout (deliberate).
- **Filters/UX:** only the ACTIVE trade (lowest not-yet-TP'd) draws bold
  (golden entry / green target / red SL); higher trades faint; completed hidden.
- **Expiry:** close above the highest peak → setup "fully played" → hidden
  (toggle `Show Expired` exists).

## 4. Detection rules that took ~25 charts to get right (DO NOT lose these)

1. **Two independent ZigZag engines** (TradingView/ZigZag/7 library):
   one at `Min Decline %` (sets B), one at `Peak Sensitivity %` (finds peaks).
   Decoupled so his proven 35% selectivity is untouched by finer peak finding.
2. **Nearest-first staircase:** walk pivots backward in time from B; the first
   qualifying high = T1; each next kept peak must be higher.
3. **Min Gap % (default 8): if two peaks are within the gap, KEEP THE HIGHER**
   (he specifically requested this after the ACE chart dropped a 1695 top in
   favour of 1600).
4. **Stop-at-lower-low:** the backward walk **breaks** the moment it crosses a
   pivot low below B — prevents reaching into an older, deeper decline
   (the J&K Bank lesson: 2014-15 peaks were wrongly attached to a 2025 low).
5. **Wait for confirmation:** only confirmed pivots; no marking fresh crashing
   bottoms ("no falling knives" — his explicit choice).
6. **Expiry** (SunPharma lesson): if price already ran above the top peak,
   there is nothing to trade — hide it.
7. **Known deliberate gaps** (user accepted): sub-35% declines don't register
   by default (Tata Motors 29.85%, Sundaram ~29%) — the dial can be lowered
   per-stock; fresh unconfirmed bottoms (JAINREC, HDBFS) stay hidden.
8. **Open mystery — handle with care:** the exact mechanism by which the ZigZag
   library confirms a pivot is NOT fully understood. An earlier theory ("price
   must retrace 35% to confirm B") was DISPROVED by Coromandel (B confirmed
   after only ~16% bounce). Before ever changing confirmation behaviour,
   investigate the library's real behaviour empirically. Do not guess.

## 5. Pine v6 implementation notes (from building V2)

- Persistent state via `var` scalars (B, A0..A3 price/time, per-trade states
  st0..st3, `stateForB`) — deliberately NOT arrays/UDTs, for readability.
- **`na != x` gotcha:** `na != anything` evaluates falsy — always use the
  two-branch guard (`isFirst = not na(new) and na(old)` /
  `isChanged = not na(new) and not na(old) and new != old`).
- All state transitions gated on `barstate.isconfirmed` (no intra-bar flips).
- Trade logic is a pure function `stepTrade()` returning
  `[newState, entryFired, tpFired, slFired]`; states: 0 none, 1 waiting,
  2 in trade, 3 TP done.
- Drawing: global `var` arrays of box/line/label handles; `clearDrawings()`
  deletes + clears, everything redrawn on `barstate.islast`. Info table uses
  `table.clear` then re-fill.
- Levels helper `swingLevels(Ap, Bp)` returns `[sl, eL, eH, tL, tH]`.
- Alerts: per-trade entry alerts + combined any-entry/any-TP/any-SL.
- Baked-in defaults per user: Peak Sensitivity 25, EMAs OFF, Info Table OFF,
  Zone Border Width 2, colours: entry `#D4AF37` golden, target `#22AB94` green,
  SL red, B `#22AB94`. **Unified colours across all trades — no per-trade
  colour coding** (his explicit requirement).
- Info table extras he values: **Active R:R** and **per-setup Depth %**.

## 6. THE NEW TASK: short-only strategy — "reversing the rules completely"

His words: long-only today; build a SHORT-ONLY mirror. Everything reverses.

**CONFIRMED BY USER (2026-07-04, before starting the new chat):** he reviewed
this exact mapping table and confirmed it matches his intent: A = trough(s),
B = the peak, Fib marked from trough to peak, short entry on a close BELOW
0.382. He also explicitly settled the one open nuance: **B = the highest HIGH
(wick), not the highest close** — the exact mirror of the long side (where B
was always the lowest wick). Treat the table below as agreed, not a proposal;
still sanity-check details with him as you build.

Suggested mapping (confirmed):

| Long (V2) | Short mirror |
|---|---|
| Sharp DECLINE then recovery | Sharp RALLY then rollover |
| B = lowest low of recent confirmed decline | **B = highest high of recent confirmed rally** |
| Nested peaks (lower-highs) ABOVE B, nearest-first | **Nested troughs (higher-lows) BELOW B, nearest-first (T1 = trough nearest B)** |
| Fib measured UP from B toward peak | **Fib measured DOWN from B toward trough** |
| Entry: close crosses ABOVE 0.382 | **Entry: close crosses BELOW the 0.382 retracement (measured down)** |
| Filter: close > EMA9 & EMA21 | **close < EMA9 & EMA21** |
| Volume > 1.2× avg | Likely same (confirm with him) |
| TP: high ≥ 0.618 | **TP: low ≤ 0.618 (measured down)** |
| SL: close < 0.236 | **SL: close ABOVE the 0.236 (measured down)** |
| Stop-at-lower-low (low below B ends walk) | **Stop-at-higher-high (high above B ends walk)** |
| Min-gap: keep the HIGHER peak | **Min-gap: keep the LOWER trough** |
| Expiry: close above top peak | **Expiry: close below the lowest trough** |
| Active trade = lowest peak not yet TP'd | **Active trade = nearest (highest) trough not yet TP'd** |

Practical approach: copy V2 as the starting template into the NEW file, rename
the indicator, then systematically invert: swap high/low roles in both ZigZag
scans, flip every comparison in detection + `stepTrade`, flip the level maths
(`level = B − fib × (B − A)`), flip plotshape directions/locations, and keep
the identical UX (active-bold/faint, unified colours, expiry, R:R, Depth %).
Verification is his job in TradingView — suggest he tests on charts that had
big rallies then rollovers, and have him compare against manual markings
exactly like he did for the long side.

⚠️ Shorting context: he trades NSE India. Cash-market short selling is
intraday-constrained there; sustained shorts are via F&O. Worth one gentle
mention that the short indicator marks SETUPS — instrument choice is his.

## 7. Parked / future items (do NOT start unless he asks)

1. **Anchored Volume Profile** overlay (default-OFF toggle, anchored B→active
   peak, TV colours, capped bins/lookback) — designed, deliberately deferred
   (he's wary of chart-load weight).
2. **Colour schematics polish** — "later."
3. **Intraday long-only variant** — same rules, re-tuned deviations. He will
   return for this AFTER the short version is done. Do not build now.
4. ZigZag pivot-confirmation investigation (see §4.8) before touching
   confirmation logic.
5. Python engine / dashboard integration of nested logic — far future; the
   Python side re-implements the OLD single-setup logic and must stay untouched.

## 8. Suggested first message for the new chat

> "Read HANDOFF_SHORT_STRATEGY.md in the project root, then help me build the
> short-only version as described in section 6."
