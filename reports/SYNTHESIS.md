# Strategy x Timeframe — Synthesis

_India (NSE Nifty-500), data through 2026-06-25, capital Rs 20,00,000 fixed for all runs._

Five colloquial money-management strategies over the same V2 signals, each run on six
trailing windows. Capital and signals are identical across the board — only the sizing
and position-management rules differ, so any difference is the strategy's doing.

## The strategies
- **s1_equal_weight** — Equal-weight, set-and-forget: spread the capital across up to 10 equal-sized positions and hold each to its V2 target or stop. No active capital management.
- **s2_capital_rotation** — Equal-weight, but recycle capital: same 10 x 2L sizing, and when fully invested, sell the open position nearest its target (widening 10%->40% band) to fund a fresh setup instead of skipping it.
- **s3_concentrated** — High conviction, concentrated: fewer but bigger bets - up to 5 positions of 4L each, held to exit. More exposure per name, higher variance.
- **s4_diversified** — Maximum diversification: many small bets - up to 20 positions of 1L each, held to exit. Wide spread smooths the ride but dilutes each winner.
- **s5_fractional_rotation** — Fixed-fractional + rotation: size every trade at 10% of capital, cap the book at 8 positions, and rotate capital out of near-target winners to fund fresh setups. A percent-sized, actively-recycled book.

## Total return %
| Strategy | 5y | 3y | 1y | 6mo | 3mo | 6wk |
|---|---|---|---|---|---|---|
| s1_equal_weight | +72.3 | +58.9 | -6.5 | -5.1 | +7.9 | +8.0 |
| s2_capital_rotation | +76.1 | +69.9 | +2.1 | -7.8 | +10.8 | +6.6 |
| s3_concentrated | +113.8 | +98.5 | -15.6 | +14.9 | +12.3 | +13.1 |
| s4_diversified | +56.5 | +33.9 | -3.0 | -2.6 | +9.5 | +3.7 |
| s5_fractional_rotation | +58.3 | +57.6 | +1.1 | -6.0 | +10.1 | +7.5 |
| _Nifty 50 (buy & hold)_ | +51.7 | +28.9 | -4.7 | -8.0 | +3.2 | +1.5 |
| _Sensex (buy & hold)_ | +45.7 | +22.4 | -6.8 | -9.7 | +2.4 | +2.3 |

## CAGR %
| Strategy | 5y | 3y | 1y | 6mo | 3mo | 6wk |
|---|---|---|---|---|---|---|
| s1_equal_weight | +12 | +17 | -7 | -10 | +35 | +95 |
| s2_capital_rotation | +12 | +19 | +2 | -15 | +50 | +74 |
| s3_concentrated | +16 | +26 | -16 | +32 | +58 | +191 |
| s4_diversified | +9 | +10 | -3 | -5 | +43 | +37 |
| s5_fractional_rotation | +10 | +16 | +1 | -12 | +46 | +88 |

## Max drawdown %
| Strategy | 5y | 3y | 1y | 6mo | 3mo | 6wk |
|---|---|---|---|---|---|---|
| s1_equal_weight | 22.1 | 16.1 | 23.4 | 13.8 | 8.1 | 3.3 |
| s2_capital_rotation | 21.2 | 11.2 | 14.8 | 14.4 | 5.7 | 3.6 |
| s3_concentrated | 25.1 | 14.7 | 27.3 | 7.9 | 10.7 | 2.4 |
| s4_diversified | 14.3 | 15.3 | 16.6 | 10.7 | 6.2 | 3.0 |
| s5_fractional_rotation | 17.9 | 12.1 | 14.1 | 13.5 | 5.1 | 2.5 |

## Trades taken
| Strategy | 5y | 3y | 1y | 6mo | 3mo | 6wk |
|---|---|---|---|---|---|---|
| s1_equal_weight | 427 | 285 | 80 | 63 | 40 | 25 |
| s2_capital_rotation | 499 | 348 | 116 | 68 | 46 | 27 |
| s3_concentrated | 236 | 159 | 35 | 28 | 22 | 13 |
| s4_diversified | 705 | 473 | 167 | 111 | 71 | 38 |
| s5_fractional_rotation | 429 | 299 | 101 | 64 | 41 | 23 |

## Hit target
| Strategy | 5y | 3y | 1y | 6mo | 3mo | 6wk |
|---|---|---|---|---|---|---|
| s1_equal_weight | 247 | 166 | 34 | 26 | 22 | 12 |
| s2_capital_rotation | 187 | 131 | 38 | 23 | 16 | 9 |
| s3_concentrated | 144 | 98 | 13 | 15 | 13 | 7 |
| s4_diversified | 409 | 264 | 75 | 49 | 38 | 14 |
| s5_fractional_rotation | 156 | 105 | 32 | 22 | 14 | 9 |

## Hit stop
| Strategy | 5y | 3y | 1y | 6mo | 3mo | 6wk |
|---|---|---|---|---|---|---|
| s1_equal_weight | 170 | 109 | 37 | 28 | 8 | 3 |
| s2_capital_rotation | 184 | 118 | 44 | 29 | 8 | 3 |
| s3_concentrated | 87 | 56 | 18 | 8 | 4 | 1 |
| s4_diversified | 276 | 189 | 73 | 43 | 13 | 4 |
| s5_fractional_rotation | 158 | 101 | 39 | 27 | 8 | 2 |

## Win rate %
| Strategy | 5y | 3y | 1y | 6mo | 3mo | 6wk |
|---|---|---|---|---|---|---|
| s1_equal_weight | 57 | 58 | 45 | 46 | 60 | 72 |
| s2_capital_rotation | 60 | 62 | 53 | 46 | 65 | 63 |
| s3_concentrated | 60 | 62 | 43 | 61 | 64 | 77 |
| s4_diversified | 57 | 56 | 48 | 49 | 63 | 66 |
| s5_fractional_rotation | 60 | 62 | 54 | 47 | 66 | 70 |

## Rotations
| Strategy | 5y | 3y | 1y | 6mo | 3mo | 6wk |
|---|---|---|---|---|---|---|
| s1_equal_weight | 0 | 0 | 0 | 0 | 0 | 0 |
| s2_capital_rotation | 118 | 89 | 24 | 7 | 12 | 5 |
| s3_concentrated | 0 | 0 | 0 | 0 | 0 | 0 |
| s4_diversified | 0 | 0 | 0 | 0 | 0 | 0 |
| s5_fractional_rotation | 107 | 85 | 22 | 7 | 11 | 4 |

## Signals skipped
| Strategy | 5y | 3y | 1y | 6mo | 3mo | 6wk |
|---|---|---|---|---|---|---|
| s1_equal_weight | 775 | 560 | 257 | 180 | 137 | 36 |
| s2_capital_rotation | 692 | 490 | 218 | 175 | 130 | 34 |
| s3_concentrated | 973 | 692 | 304 | 216 | 155 | 48 |
| s4_diversified | 474 | 355 | 165 | 130 | 103 | 20 |
| s5_fractional_rotation | 770 | 544 | 235 | 179 | 135 | 38 |

## Best strategy per timeframe (by total return)
- **5y**: s3_concentrated  (+113.8%)
- **3y**: s3_concentrated  (+98.5%)
- **1y**: s2_capital_rotation  (+2.1%)
- **6mo**: s3_concentrated  (+14.9%)
- **3mo**: s3_concentrated  (+12.3%)
- **6wk**: s3_concentrated  (+13.1%)
