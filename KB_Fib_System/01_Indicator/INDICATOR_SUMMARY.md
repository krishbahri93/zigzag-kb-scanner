# Indicator Summary — ZigZag KB Fib Dual Trade

**Published:** https://in.tradingview.com/script/s0BdSUIs-ZigZag-KB-Fib-Dual-Trade/
**Author:** krishbahri · **Type:** Open-source Pine Script · **Primary use:** Daily NSE equities

---

## One-line description

It automates a Fibonacci-based strategy that extracts **two sequential trades** from a single
**A→B down-swing**: when Trade 1 hits its take-profit, the same fib levels reframe into a Trade 2
setup automatically. Detection, zone calculation, state tracking, and signal generation are all
handled by the script — you watch the chart and execute manually.

---

## How it works

The script uses TradingView's official **ZigZag library** to identify confirmed price swings, then
filters for **A→B down-swings only** (a confirmed high A followed by a confirmed low B). On the most
recent confirmed down-swing it projects six Fibonacci levels and turns them into two trades.

### The fib projection (measured on the A→B drop)

| Fib level | Role |
|-----------|------|
| **0.236** | Trade 1 stop-loss line |
| **0.32 – 0.382** | Trade 1 Entry Zone |
| **0.618 – 0.68** | Trade 1 TP Zone — *and simultaneously* Trade 2 Entry Zone |
| **1.0 – 1.05** | Trade 2 TP Zone |

The elegance is in the overlap: the 0.618–0.68 band is the exit for the first trade and the entry
for the second. One swing, two layered opportunities.

---

## Trade 1

- **Entry:** Close above 0.382, with EMA 9 / EMA 21 confirmation and volume above 1.2× the 20-bar average.
- **Take Profit:** High reaches the 0.618 zone.
- **Stop Loss:** Close below 0.236.

## Trade 2

- **Sequential entry:** After Trade 1's TP fires, a close above 0.68 (with the same EMA + volume confirmation) opens Trade 2.
- **Jump-in entry:** If price gaps past Trade 1 entirely and closes above 0.68, Trade 2 activates directly — you don't have to have caught Trade 1.
- **Take Profit:** High reaches the 1.0 zone.
- **Stop Loss:** Close below 0.618.

---

## Visual state machine

The indicator tracks **six states** and recolors the zones live so the chart tells you the trade
status at a glance:

| State | What you see |
|-------|--------------|
| Waiting T1 entry | Entry Zone lit, T1 TP zone lit, T2 TP dimmed |
| In Trade 1 | Same, plus an entry arrow on the trigger bar |
| T1 played → Waiting T2 | Entry Zone dims; the 0.618–0.68 band switches to the T2-entry color; T2 TP lights up |
| In Trade 2 | Same, plus a T2 entry arrow |
| Fully played | All zones dimmed |

A **Macro swing layer** (the highest A paired with the lowest B since that A) draws in the
background as dimmed gray whenever it differs from the active swing — giving the bigger-picture
context behind the current setup.

---

## Setup invalidation rules

- **Pre-activation:** If price closes below B before any trade triggers, the indicator anchors B to
  the new lower low automatically and recalculates the zones. The macro A→B is preserved.
- **After an SL hit:** The setup returns to "waiting" and can re-trigger if entry conditions are met again.
- **After Trade 2 TP:** The setup is fully played until a brand-new A→B forms.

---

## Filters (both default ON)

- **EMA filter:** Require close > EMA 9 AND close > EMA 21 at entry.
- **Volume filter:** Require volume > 1.2× the 20-bar SMA at entry.

Both are toggleable, but the strategy was developed and is intended to be run with **both ON**.

---

## Info table (top-right on chart)

Shows live state, A and B prices, the drop %, all zone ranges, both SL levels, current price, EMA
filter status, volume filter status, and macro swing context when present.

---

## Alerts — six conditions

`T1 Entry` · `T1 TP` · `T1 SL` · `T2 Entry` · `T2 TP` · `T2 SL`

---

## Settings exposed

- **Pivot detection:** ZigZag deviation % (default 35, tunable), minimum bars between pivots.
- **Fibonacci levels:** all six levels editable.
- **Moving averages:** EMA 9 and EMA 21 colors and widths.
- **Zone styling:** entry / TP / dimmed colors, border width, fill transparency, SL line color and width.
- **Display:** zone extension bars, info-table toggle, A/B label toggle, ZigZag debug line.

---

## Recommended use

Built for the **daily timeframe on NSE equities**, but works on 4H, 1H, and 15-minute charts too.
**Tune the deviation %** by timeframe — higher for daily (catches major swings), lower for intraday.

It is designed to **surface and structure trades for manual review**, not to act as an automated
bot. It removes the decision fatigue of hand-calculating fib levels, watching for EMA + volume
confluence, and tracking trade state across two sequential setups.

---

## Author's notes / known caveats

- Not financial advice. Test on your own market and timeframe before risking capital.
- Past performance of the strategy does not guarantee future results.
- The script handles state correctly **on confirmed bars**; intra-bar transitions may flicker until
  the bar closes.
