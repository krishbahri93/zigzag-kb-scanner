# Automation Lab — answers to Krish's questions (SHORT side)

Every number below is the average validation-window CAGR across all sweep
combinations sharing that setting — i.e. 'holding everything else mixed, does
turning this dial pay?'. The leaderboard (TOP20.md) has the exact winners.

## E1-E4 · Which entry filters actually pay?

**E1 — candle must close near the day's high (min position in range)**

| setting | avg val CAGR% | combos |
|---|---|---|
| 0.5 | -2.7 | 48 |
| 0.6 | -2.6 | 48 |
| 0.7 | -3.6 | 48 |
| off | -3.4 | 48 |

**E3 — skip red confirming candles**

| setting | avg val CAGR% | combos |
|---|---|---|
| off | -3.4 | 96 |
| True | -2.8 | 96 |

**E2 — volume stronger than recent days**

| setting | avg val CAGR% | combos |
|---|---|---|
| off | -2.6 | 64 |
| gt_1_2x20d | -2.6 | 64 |
| gt_prev | -4.1 | 64 |

**E4 — skip when remaining reward:risk is poor**

| setting | avg val CAGR% | combos |
|---|---|---|
| 0.75 | -4.5 | 48 |
| 1.0 | -1.1 | 48 |
| 1.5 | -1.0 | 48 |
| off | -5.7 | 48 |

## E5 · Enter at the 3:20 close, or the next day's open?

**entry timing**

| setting | avg val CAGR% | combos |
|---|---|---|
| close | -1.1 | 96 |
| next_open | -5.0 | 96 |

## X1-X3 · Exits (measured as the CHANGE vs the same combo without that exit)

**X1 — early target at % of the run**

| setting | avg val CAGR change vs parent | combos |
|---|---|---|
| 60 | -8.8 | 90 |
| 70 | -8.3 | 90 |
| 80 | -6.6 | 90 |
| off | -10.4 | 75 |

**X3 — move stop to breakeven after 1R**

| setting | avg val CAGR change vs parent | combos |
|---|---|---|
| 1.0 | -8.2 | 180 |
| off | -8.7 | 165 |

**X2 — trailing stop % below peak close**

| setting | avg val CAGR change vs parent | combos |
|---|---|---|
| 12 | -10.3 | 120 |
| 8 | -8.3 | 120 |
| off | -6.4 | 105 |

## S1 · Equal Rs 2L per trade, or a % of equity? Rotation?

**sizing (vs the parent's fixed Rs 2L)**

| setting | avg val CAGR change vs parent | combos |
|---|---|---|
| fixed2L | -1.9 | 10 |
| pct10 | -0.9 | 20 |

**rotation (vs the parent's none)**

| setting | avg val CAGR change vs parent | combos |
|---|---|---|
| band | -1.9 | 20 |
| none | 0.0 | 10 |

## The verdict

- **Raw V2.1, no judgment** -> validate CAGR -2.4% at 23.2% DD (FAILS the gate)
- **Krish encoded (manual rules)** -> validate CAGR -7.6% at 24.0% DD (FAILS the gate)
- **Best gated combo (C013)** -> validate CAGR 13.0% at 17.0% DD · train CAGR -0.7% at 30.5% DD
  - spec: close in top 30% of range; remaining R:R >= 0.75 · early target at 80% of run · next-day open entry · rotation on

If the verdict holds up to scrutiny, this spec becomes the frozen policy for this
side and goes to paper-trading in the forward test before any capital.