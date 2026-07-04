# Indicator Parameters — Quick Reference Card

A one-page lookup of every tunable and every fixed level in the ZigZag KB Fib Dual Trade indicator.
For the narrative, see `INDICATOR_SUMMARY.md`.

---

## Fib levels (off the A→B drop)

| Level | Role | Editable? |
|-------|------|-----------|
| 0.236 | T1 stop-loss line | yes |
| 0.32 | T1 entry zone (lower) | yes |
| 0.382 | T1 entry zone (upper) — entry trigger reference | yes |
| 0.618 | T1 TP / T2 entry zone (lower) | yes |
| 0.68 | T1 TP / T2 entry zone (upper) | yes |
| 1.0 | T2 TP zone (lower) | yes |
| 1.05 | T2 TP zone (upper) | yes |

## Entry / exit triggers

| Event | Condition |
|-------|-----------|
| T1 entry | close > 0.382 + close > EMA9 + close > EMA21 + vol > 1.2× 20-bar avg |
| T1 TP | high reaches 0.618 (first touch) |
| T1 SL | close < 0.236 |
| T2 entry (sequential) | after T1 TP: close > 0.68 + EMA + volume confirmation |
| T2 entry (jump-in) | price gaps past T1, closes > 0.68 |
| T2 TP | high reaches 1.0 |
| T2 SL | close < 0.618 |

## Filters

| Filter | Default | Condition |
|--------|---------|-----------|
| EMA | ON | close > EMA9 AND close > EMA21 |
| Volume | ON | volume > 1.2× 20-bar SMA |

## Moving averages

| MA | Period |
|----|--------|
| Fast EMA | 9 |
| Slow EMA | 21 |

## Pivot detection (ZigZag)

| Setting | Default | Notes |
|---------|---------|-------|
| Deviation % | 35 | higher for daily, lower for intraday |
| Min bars between pivots | (tunable) | guard against over-frequent pivots |

## Display toggles

Zone extension bars · info-table on/off · A/B labels on/off · ZigZag debug line · entry/TP/dimmed
zone colors · border width · fill transparency · SL line color & width · EMA colors & widths.

## Alerts (6)

`T1 Entry` · `T1 TP` · `T1 SL` · `T2 Entry` · `T2 TP` · `T2 SL`

## Recommended settings by timeframe

| TF | Deviation % guidance |
|----|----------------------|
| 1D (primary) | higher (≈35+) — major swings |
| 4H | moderate |
| 1H | lower |
| 15m | lowest — most sensitive |
