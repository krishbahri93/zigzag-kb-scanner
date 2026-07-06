# Automation Lab — answers to Krish's questions

Every number below is the average validation-window CAGR across all sweep
combinations sharing that setting — i.e. 'holding everything else mixed, does
turning this dial pay?'. The leaderboard (TOP20.md) has the exact winners.

## E1-E4 · Which entry filters actually pay?

**E1 — candle must close near the day's high (min position in range)**

| setting | avg val CAGR% | combos |
|---|---|---|
| 0.5 | 4.5 | 48 |
| 0.6 | 4.5 | 48 |
| 0.7 | 3.9 | 48 |
| off | 5.8 | 48 |

**E3 — skip red confirming candles**

| setting | avg val CAGR% | combos |
|---|---|---|
| off | 4.3 | 96 |
| True | 5.0 | 96 |

**E2 — volume stronger than recent days**

| setting | avg val CAGR% | combos |
|---|---|---|
| off | 4.5 | 64 |
| gt_1_2x20d | 4.5 | 64 |
| gt_prev | 4.9 | 64 |

**E4 — skip when remaining reward:risk is poor**

| setting | avg val CAGR% | combos |
|---|---|---|
| 0.75 | 4.8 | 48 |
| 1.0 | 4.1 | 48 |
| 1.5 | 7.9 | 48 |
| off | 1.9 | 48 |

## E5 · Enter at the 3:20 close, or the next day's open?

**entry timing**

| setting | avg val CAGR% | combos |
|---|---|---|
| close | 6.9 | 96 |
| next_open | 2.4 | 96 |

## X1-X3 · Exits (measured as the CHANGE vs the same combo without that exit)

**X1 — early target at % of the run**

| setting | avg val CAGR change vs parent | combos |
|---|---|---|
| 60 | -8.2 | 90 |
| 70 | -6.0 | 90 |
| 80 | -5.9 | 90 |
| off | -10.2 | 75 |

**X3 — move stop to breakeven after 1R**

| setting | avg val CAGR change vs parent | combos |
|---|---|---|
| 1.0 | -7.3 | 180 |
| off | -7.5 | 165 |

**X2 — trailing stop % below peak close**

| setting | avg val CAGR change vs parent | combos |
|---|---|---|
| 12 | -5.0 | 120 |
| 8 | -14.7 | 120 |
| off | -1.9 | 105 |

## S1 · Equal Rs 2L per trade, or a % of equity? Rotation?

**sizing (vs the parent's fixed Rs 2L)**

| setting | avg val CAGR change vs parent | combos |
|---|---|---|
| fixed2L | -1.1 | 10 |
| pct10 | -0.6 | 20 |

**rotation (vs the parent's none)**

| setting | avg val CAGR change vs parent | combos |
|---|---|---|
| band | -1.1 | 20 |
| none | 0.0 | 10 |

## The verdict

- **Raw V2.1, no judgment** -> validate CAGR 7.3% at 17.2% DD (FAILS the gate)
- **Krish encoded (manual rules)** -> validate CAGR 6.2% at 12.9% DD (passes the gate)
- **Best gated combo (B103)** -> validate CAGR 16.6% at 9.6% DD · train CAGR 17.6% at 10.1% DD
  - spec: close in top 40% of range; green candle only; remaining R:R >= 1.0 · early target at 70% of run · 3:20 close entry

If the verdict holds up to scrutiny, this spec becomes the **NDL-Auto v1** policy
(a committed JSON) and goes to paper-trading in the forward test before any capital.