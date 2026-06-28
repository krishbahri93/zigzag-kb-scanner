# Strategy x Timeframe — Synthesis

_US (Polygon liquid-1000), data through 2026-06-24, capital $20,000 fixed for all runs._

Five colloquial money-management strategies over the same V2 signals, each run on six
trailing windows. Capital and signals are identical across the board — only the sizing
and position-management rules differ, so any difference is the strategy's doing.

## The strategies
- **s1_equal_weight** — Equal-weight, set-and-forget: spread the capital across up to 10 equal-sized positions and hold each to its V2 target or stop. No active capital management.
- **s2_capital_rotation** — Equal-weight, but recycle capital: same 10 x $2k sizing, and when fully invested, sell the open position nearest its target (widening 10%->40% band) to fund a fresh setup instead of skipping it.
- **s3_concentrated** — High conviction, concentrated: fewer but bigger bets - up to 5 positions of $4k each, held to exit. More exposure per name, higher variance.
- **s4_diversified** — Maximum diversification: many small bets - up to 20 positions of $1k each, held to exit. Wide spread smooths the ride but dilutes each winner.
- **s5_fractional_rotation** — Fixed-fractional + rotation: size every trade at 10% of capital, cap the book at 8 positions, and rotate capital out of near-target winners to fund fresh setups. A percent-sized, actively-recycled book.

## Total return %
| Strategy | 2y | 18mo | 1y | 6mo | 3mo | 6wk |
|---|---|---|---|---|---|---|
| s1_equal_weight | +52.4 | +38.5 | +25.1 | -2.0 | +19.6 | +4.0 |
| s2_capital_rotation | +30.2 | +25.4 | +14.6 | -4.8 | +15.4 | +6.6 |
| s3_concentrated | -4.5 | -4.7 | +24.5 | -5.4 | +25.5 | +0.4 |
| s4_diversified | +28.7 | +19.1 | +13.7 | -5.9 | +7.6 | -3.3 |
| s5_fractional_rotation | +27.1 | +22.3 | +22.2 | +3.9 | +15.3 | +6.2 |
| _S&P 500 (SPY) (buy & hold)_ | +34.7 | +21.9 | +20.8 | +6.2 | +12.3 | -1.2 |
| _Nasdaq-100 (QQQ) (buy & hold)_ | +48.3 | +34.1 | +31.6 | +13.9 | +21.7 | -0.6 |

## CAGR %
| Strategy | 2y | 18mo | 1y | 6mo | 3mo | 6wk |
|---|---|---|---|---|---|---|
| s1_equal_weight | +23 | +24 | +25 | -4 | +103 | +41 |
| s2_capital_rotation | +14 | +16 | +15 | -10 | +77 | +74 |
| s3_concentrated | -2 | -3 | +25 | -11 | +146 | +3 |
| s4_diversified | +13 | +12 | +14 | -12 | +34 | -25 |
| s5_fractional_rotation | +13 | +14 | +22 | +8 | +76 | +69 |

## Max drawdown %
| Strategy | 2y | 18mo | 1y | 6mo | 3mo | 6wk |
|---|---|---|---|---|---|---|
| s1_equal_weight | 28.7 | 31.9 | 17.1 | 24.6 | 4.8 | 5.0 |
| s2_capital_rotation | 28.7 | 31.9 | 21.1 | 27.8 | 6.2 | 7.4 |
| s3_concentrated | 50.5 | 48.7 | 18.9 | 23.0 | 6.5 | 7.7 |
| s4_diversified | 16.2 | 17.4 | 18.2 | 21.3 | 9.3 | 11.0 |
| s5_fractional_rotation | 28.6 | 31.3 | 18.5 | 21.5 | 4.9 | 4.7 |

## Trades taken
| Strategy | 2y | 18mo | 1y | 6mo | 3mo | 6wk |
|---|---|---|---|---|---|---|
| s1_equal_weight | 388 | 327 | 211 | 119 | 86 | 42 |
| s2_capital_rotation | 422 | 356 | 247 | 124 | 86 | 44 |
| s3_concentrated | 226 | 152 | 117 | 56 | 43 | 28 |
| s4_diversified | 581 | 515 | 379 | 219 | 145 | 70 |
| s5_fractional_rotation | 369 | 312 | 201 | 111 | 70 | 35 |

## Hit target
| Strategy | 2y | 18mo | 1y | 6mo | 3mo | 6wk |
|---|---|---|---|---|---|---|
| s1_equal_weight | 260 | 215 | 133 | 72 | 59 | 25 |
| s2_capital_rotation | 227 | 181 | 117 | 56 | 40 | 21 |
| s3_concentrated | 148 | 95 | 77 | 34 | 30 | 17 |
| s4_diversified | 387 | 336 | 240 | 132 | 91 | 37 |
| s5_fractional_rotation | 199 | 155 | 94 | 53 | 33 | 16 |

## Hit stop
| Strategy | 2y | 18mo | 1y | 6mo | 3mo | 6wk |
|---|---|---|---|---|---|---|
| s1_equal_weight | 118 | 102 | 68 | 37 | 17 | 7 |
| s2_capital_rotation | 129 | 109 | 75 | 38 | 17 | 7 |
| s3_concentrated | 74 | 53 | 35 | 17 | 8 | 6 |
| s4_diversified | 174 | 159 | 119 | 68 | 35 | 15 |
| s5_fractional_rotation | 113 | 97 | 62 | 33 | 15 | 5 |

## Win rate %
| Strategy | 2y | 18mo | 1y | 6mo | 3mo | 6wk |
|---|---|---|---|---|---|---|
| s1_equal_weight | 59 | 58 | 55 | 53 | 62 | 52 |
| s2_capital_rotation | 59 | 59 | 58 | 53 | 63 | 57 |
| s3_concentrated | 53 | 51 | 55 | 50 | 63 | 46 |
| s4_diversified | 58 | 57 | 55 | 53 | 58 | 47 |
| s5_fractional_rotation | 59 | 59 | 58 | 57 | 64 | 57 |

## Rotations
| Strategy | 2y | 18mo | 1y | 6mo | 3mo | 6wk |
|---|---|---|---|---|---|---|
| s1_equal_weight | 0 | 0 | 0 | 0 | 0 | 0 |
| s2_capital_rotation | 56 | 56 | 45 | 21 | 19 | 6 |
| s3_concentrated | 0 | 0 | 0 | 0 | 0 | 0 |
| s4_diversified | 0 | 0 | 0 | 0 | 0 | 0 |
| s5_fractional_rotation | 49 | 52 | 37 | 17 | 14 | 6 |

## Signals skipped
| Strategy | 2y | 18mo | 1y | 6mo | 3mo | 6wk |
|---|---|---|---|---|---|---|
| s1_equal_weight | 532 | 531 | 371 | 257 | 147 | 50 |
| s2_capital_rotation | 488 | 489 | 325 | 249 | 145 | 47 |
| s3_concentrated | 699 | 713 | 467 | 325 | 193 | 66 |
| s4_diversified | 316 | 318 | 183 | 152 | 83 | 19 |
| s5_fractional_rotation | 543 | 538 | 374 | 263 | 164 | 58 |

## Best strategy per timeframe (by total return)
- **2y**: s1_equal_weight  (+52.4%)
- **18mo**: s1_equal_weight  (+38.5%)
- **1y**: s1_equal_weight  (+25.1%)
- **6mo**: s5_fractional_rotation  (+3.9%)
- **3mo**: s3_concentrated  (+25.5%)
- **6wk**: s2_capital_rotation  (+6.6%)
