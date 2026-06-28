# s5_fractional_rotation  —  2y timeframe

_Window: 2024-06-24 -> 2026-06-24  ·  starting capital $20,000_

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
- Capital: $20,000  ->  **$25,421**
- Total return: **+27.10%**   ·   CAGR: +12.75%
- Max drawdown: 28.63%

## Trade outcomes
- Total trades: **369**
- Hit TARGET: **199**   ·   Hit STOP: **113**   ·   Rotated out: 49   ·   Still open at end: 8
- Win rate: 58.8%   ·   Avg R: 0.09   ·   Profit factor: 1.15
- Expectancy / trade: $15   ·   Avg holding: 11.2 days

## P&L detail
- Net P&L: $5,413
- Gross profit: $41,112   ·   Gross loss: $-35,700
- Avg win: $189   ·   Avg loss: $-235
- Best trade: $627   ·   Worst trade: $-1,544

## What the money-management rules did
- Rotations triggered: 49
- Signals skipped (no cash / no slot): 543
