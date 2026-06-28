# s5_fractional_rotation  —  18mo timeframe

_Window: 2024-12-24 -> 2026-06-24  ·  starting capital $20,000_

## Strategy (plain English — generated from the rules that ran)
```
Policy: s5_fractional_rotation — "Fixed-fractional + rotation: size every trade at 10% of capital, cap the book at 8 positions, and rotate capital out of near-target winners to fund fresh setups. A percent-sized, actively-recycled book."
├── Capital: $20,000 · max 8 positions
├── Sizing: percent_of_capital — "Allocate 10% of capital per trade."
├── Selection: free_capital_first — "Consider every fresh signal; cash and the position cap gate it downstream."
├── Rotation: nearest_to_target_band — "To fund a new entry, sell the open position closest to its target within 10%; widen the band by 10% up to 40%."
└── Exit: scanner_default — "Exit on V2's own target or stop; no extra exit."
```

## Headline
- Capital: $20,000  ->  **$24,469**
- Total return: **+22.35%**   ·   CAGR: +14.44%
- Max drawdown: 31.29%

## Trade outcomes
- Total trades: **312**
- Hit TARGET: **155**   ·   Hit STOP: **97**   ·   Rotated out: 52   ·   Still open at end: 8
- Win rate: 59.0%   ·   Avg R: 0.10   ·   Profit factor: 1.15
- Expectancy / trade: $14   ·   Avg holding: 11.5 days

## P&L detail
- Net P&L: $4,461
- Gross profit: $34,883   ·   Gross loss: $-30,421
- Avg win: $190   ·   Avg loss: $-238
- Best trade: $627   ·   Worst trade: $-1,544

## What the money-management rules did
- Rotations triggered: 52
- Signals skipped (no cash / no slot): 538
