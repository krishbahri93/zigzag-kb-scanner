# Version History & Glossary

---

## Part 1 — Version history & lineage

The system has two naming lineages that describe the same underlying strategy at different stages.
Recording this prevents accidentally reintroducing retired logic.

### The two lineages

- **Single-trade lineage (earlier):** the original "KB Fib Daily" indicator family, versions up to
  ~v10.2 (auto-detect) and v11.0 (manual A/B input). This used an **A1/A2/A3 peak queue** that
  promoted to the next higher peak when the active setup's TP was hit, a single entry zone
  (0.32–0.382) and a single TP zone (0.618–0.68), with EMA 9/21 confirmation.

- **Dual-trade lineage (current, published):** "ZigZag KB Fib Dual Trade." Replaces the single
  entry/exit with **two sequential trades (T1 → T2)** off one A→B down-swing, where the 0.618–0.68
  band is simultaneously T1's TP and T2's entry, and T2 targets 1.0–1.05. Uses TradingView's ZigZag
  library for swing detection (deviation %, default 35) and a six-state visual machine with six
  alert conditions. This is the version at the published link and the one this folder documents as
  authoritative.

### Architectural decisions to preserve (do not silently reverse)

These were deliberate; reintroducing the old behavior would be a regression:

1. **Dual-trade structure over single-trade.** The current model intentionally layers two trades on
   one swing. Don't collapse it back to one entry/exit.
2. **ZigZag-library swing detection** in the indicator (vs the scanner's fixed-width dominant-swing
   pivots). The two methods are known to differ (rules §6.3); that's accepted, not a bug to "fix" by
   forcing them identical without testing.
3. **Read-only Dhan adapter.** The data layer fetches candles only and never imports an order
   function. This boundary is intentional and safety-relevant.
4. **First-touch TP** (target counts on first touch of the zone, not a close beyond it). A known,
   deliberate trade-off — see thesis and rules §10.
5. **Both filters ON by default.** The strategy's expectations assume EMA + volume both active.

### From earlier lineage, worth remembering

- **TP math reversion (historic v6):** an earlier change to the take-profit calculation was reverted;
  the current golden-zone TP math is the intended one.
- **Removed broken peak-threshold check (historic v10.2):** a peak threshold check that misbehaved
  was removed. Don't reintroduce it.
- **A1/A2/A3 queue:** belonged to the single-trade lineage. The dual-trade model handles sequencing
  via T1→T2 state instead. Note the conceptual replacement so the old queue isn't bolted back on.

---

## Part 2 — Glossary

**A** — the swing high that starts a setup (confirmed pivot high).

**B** — the swing low that ends the down-swing (confirmed pivot low). May be re-anchored to a new
lower low before activation.

**A→B down-swing** — a confirmed high followed by a confirmed low; the move the fibs are measured on.

**Golden zone** — the 0.618–0.68 retracement band. The hinge of the system: T1 take-profit and T2
entry.

**Entry pocket** — the scanner's term for the entry band it watches (0.618–0.68 in the engine
config); where a close determines Approaching / In Zone / Triggered.

**T1 / Trade 1** — the retracement-continuation leg: enter above 0.382, TP at 0.618, SL on close
below 0.236.

**T2 / Trade 2** — the breakout leg: enter above 0.68 (sequentially after T1 TP, or jump-in on a
gap), TP at 1.0, SL on close below 0.618.

**Sequential entry** — T2 entry that occurs after T1's TP has fired.

**Jump-in entry** — T2 entry taken when price gaps past T1 and closes above 0.68 without T1 having
triggered.

**Macro swing** — the highest-A / lowest-B-since-A pair, drawn dimmed for context; non-signaling.

**ZigZag deviation %** — the indicator's sensitivity for what counts as a swing (default 35); higher
= only bigger swings register.

**Pivot strength** — the scanner's left/right-bar window for confirming a pivot; set per timeframe.

**Dominant swing** — the scanner's choice of the highest pivot high and lowest pivot low within the
lookback window.

**Signal (scanner)** — Triggered (close above pocket), In Zone (close inside), Approaching (close
within 3% below).

**Spike** — scanner display flag for volume ≥ 1.8× the 20-bar average (distinct from the 1.2× entry
filter).

**Since-trigger %** — how far price has moved since first crossing above the pocket.

**confMin** — confirmation age in minutes (confirmation bars × minutes per bar for that timeframe).

**results.json** — the data contract file the engine writes and the dashboard reads.

**KWM** — the name used for the Python engine + dashboard side of the system.

**Dhan** — the paid real-time NSE data provider (read-only candle access here).

**yfinance / Yahoo** — the free, ~15-min-delayed default data source.
