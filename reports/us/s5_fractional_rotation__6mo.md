# s5_fractional_rotation  —  6mo timeframe

_Window: 2025-12-24 -> 2026-06-24  ·  starting capital $20,000_

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
- Capital: $20,000  ->  **$20,775**
- Total return: **+3.87%**   ·   CAGR: +7.97%
- Max drawdown: 21.50%

## Trade outcomes
- Total trades: **111**
- Hit TARGET: **53**   ·   Hit STOP: **33**   ·   Rotated out: 17   ·   Still open at end: 8
- Win rate: 56.8%   ·   Avg R: 0.09   ·   Profit factor: 1.07
- Expectancy / trade: $7   ·   Avg holding: 11.5 days

## P&L detail
- Net P&L: $767
- Gross profit: $11,111   ·   Gross loss: $-10,344
- Avg win: $176   ·   Avg loss: $-215
- Best trade: $590   ·   Worst trade: $-1,544

## What the money-management rules did
- Rotations triggered: 17
- Signals skipped (no cash / no slot): 263
