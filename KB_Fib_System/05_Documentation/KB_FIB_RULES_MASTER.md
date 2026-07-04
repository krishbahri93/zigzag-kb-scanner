# KB Fib — Master Rule Set

**Purpose:** every rule that governs the system, stated explicitly in one place, so you can audit
it, defend it, and improve it. The final section is deliberately open-ended — it's where you
pressure-test the logic.

Two engines run the same idea: the **TradingView indicator** (manual execution on a chart) and the
**Python scanner** (Nifty 500 screening). Where they differ, it's noted — those differences are the
first place to look when chart and screener disagree.

---

## 1. The geometry (shared by both engines)

1.1. A setup is built on one **A→B swing**: a confirmed swing high **A** and a confirmed swing low **B**.

1.2. The indicator restricts to **down-swings** (A high → B low) and projects fib levels off the drop `A − B`.

1.3. The six levels off the A→B drop:

| Level | Indicator role |
|-------|----------------|
| 0.236 | T1 stop-loss |
| 0.32–0.382 | T1 entry zone |
| 0.618–0.68 | T1 take-profit **=** T2 entry zone |
| 1.0–1.05 | T2 take-profit |

1.4. **Golden zone** = the 0.618–0.68 band. It is the hinge of the whole system: T1 exits there, T2 enters there.

---

## 2. Trade 1 rules (indicator)

2.1. **Entry:** daily close **above 0.382**, AND close above EMA 9, AND close above EMA 21, AND volume **> 1.2×** the 20-bar average.

2.2. **Take profit:** high reaches the **0.618** zone (first touch counts — price need not reach the far 0.68 line).

2.3. **Stop loss:** close **below 0.236**.

2.4. After an SL hit, T1 returns to "waiting" and may re-trigger if conditions re-form.

---

## 3. Trade 2 rules (indicator)

3.1. **Sequential entry:** once T1's TP has fired, a close **above 0.68** with EMA + volume confirmation opens T2.

3.2. **Jump-in entry:** if price gaps past T1 entirely and closes above 0.68, T2 activates directly — catching T1 first is not required.

3.3. **Take profit:** high reaches the **1.0** zone.

3.4. **Stop loss:** close **below 0.618**.

---

## 4. Invalidation & re-anchoring

4.1. **Before activation:** a close below B re-anchors B to the new lower low and recalculates all zones. The macro A→B is preserved.

4.2. **After T2 TP:** the setup is "fully played" and stays dormant until a fresh A→B forms.

4.3. **Macro swing layer:** the highest-A / lowest-B-since-A pair is drawn dimmed in the background whenever it differs from the active swing, for context only — it does not generate signals.

---

## 5. Filters

5.1. **EMA filter (default ON):** entry requires close above both EMA 9 and EMA 21.

5.2. **Volume filter (default ON):** entry requires volume > 1.2× the 20-bar SMA.

5.3. Both are toggleable, but the strategy is **designed for both ON**. Turning one off changes the
character of the system and invalidates any expectations built on the default behavior.

---

## 6. Pivot / swing detection

6.1. **Indicator:** TradingView ZigZag library, **deviation % default 35**, plus a minimum-bars-between-pivots guard. Higher deviation on daily, lower on intraday.

6.2. **Scanner:** confirmed pivots via a left/right-bar window (`find_pivots`), with **per-timeframe pivot strength**:

| TF | Pivot strength (bars each side) | Dominant-swing lookback (bars) |
|----|-------------------------------|-------------------------------|
| 15m | 5 | 120 |
| 1H | 8 | 160 |
| 75m | 5 | 120 |
| 4H | 6 | 120 |
| 1D | 10 | 450 |
| 1W | 6 | 160 |

6.3. **This is the most important chart-vs-scanner difference.** The indicator uses ZigZag deviation; the scanner uses fixed-width pivots + a "dominant swing" pick (highest high / lowest low in the lookback). They will not always select the same A and B. Treat the scanner as a **surfacing tool** and the chart as the **source of truth** for execution.

---

## 7. Scanner signal classification

7.1. The scanner reports one of three signals based on where the **last close** sits relative to the entry pocket (`z_lo`–`z_hi`):

- **Triggered:** last close **above** the pocket high.
- **In Zone:** last close **inside** the pocket.
- **Approaching:** last close **below** the pocket but within **3%** (`PROX = 0.03`) of it.
- Anything further out is dropped from results.

7.2. **Volume spike** in the scanner = current volume **≥ 1.8×** (`VOL_SPIKE`) the 20-bar average. (Note this is a *display* spike threshold, distinct from the **1.2×** entry filter.)

7.3. **Since-trigger %** = how far price has moved since it first crossed above the pocket, with a count of confirmation bars.

7.4. Default scanned timeframes in the runner: **1D, 1H, 15m**.

---

## 8. Data rules

8.1. **Two sources, switchable by env var `KWM_DATA_SOURCE`:**
   - `yahoo` — free, ~15-minute delayed (default).
   - `dhan` — paid, real-time (requires `DHAN_CLIENT_ID` + `DHAN_ACCESS_TOKEN`).

8.2. The Dhan adapter is **read-only** — it only fetches candles and never imports or calls any order/trade function. (This is a deliberate safety boundary; preserve it.)

8.3. **75m and 4H are resampled**, not fetched natively — 75m from 15m bars (5 per bucket), 4H from 60m bars (4 per bucket), bucketed within each trading day.

8.4. Universe = **NSE Nifty 500**, fetched live from the NSE archives CSV, with a built-in 20-name fallback if the fetch fails.

---

## 9. Execution philosophy

9.1. The system **structures and surfaces** trades; it does not place them. Every signal is for manual review.

9.2. The chart (indicator) is authoritative for the actual entry/exit decision. The scanner narrows the watchlist.

9.3. State is only trusted **on confirmed (closed) bars**. Intra-bar flicker is expected and ignored.

---

## 10. Questions to pressure-test (your reflection space)

These are open and intentionally unanswered — the point is to revisit them as you gather data.

1. **Down-swings only.** The indicator trades A→B *down*-swings (mean-reversion long off a drop). Is there a symmetric up-swing variant worth testing, or does the edge live specifically in buying retracements?

2. **First-touch TP.** TP counts on first touch of 0.618, not a close there. Does that capture or leak edge versus requiring a close beyond the level?

3. **The two volume thresholds.** Entry filter is 1.2×; the scanner's "spike" flag is 1.8×. Are these intentionally different roles, or should they be reconciled?

4. **Pivot-method mismatch (§6.3).** The chart uses ZigZag deviation; the scanner uses fixed-width dominant-swing pivots. How often do they pick a different A/B, and does that produce false "Triggered" rows? Worth logging disagreements.

5. **Deviation tuning.** Default 35 is one number across a 500-name universe. Should deviation be per-tier (mega/large/mid/small) rather than per-timeframe only?

6. **Jump-in T2 (§3.2).** Entering T2 on a gap past T1 — does the data show those entries performing as well as sequential T2 entries, or worse (chasing)?

7. **SL definition.** Both SLs are "close below" a level. Have you tested intraday-low breaches vs close-only? Close-only avoids whipsaw but accepts deeper drawdown.

8. **Re-anchoring (§4.1).** Auto-re-anchoring B to a new low keeps setups alive — but does it ever "walk" a setup down indefinitely and dull the signal? Worth a cap.

9. **Timeframe weighting.** All scanned TFs are treated equally in the output. Should a 1D Triggered outrank a 15m Triggered in the ranking?

10. **Hit-rate truth.** The dashboard currently shows *sample* performance data. The single highest-value upgrade is wiring real trade outcomes back in (see roadmap) so these questions get answered with your own numbers, not intuition.

---

*Keep this document living. When you change a rule, change it here first, then in the code — and log
the why in `VERSION_HISTORY.md`.*
