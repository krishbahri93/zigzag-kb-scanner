# s5_fractional_rotation  —  6wk timeframe

_Window: 2026-05-13 -> 2026-06-24  ·  starting capital $20,000_

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
- Capital: $20,000  ->  **$21,242**
- Total return: **+6.21%**   ·   CAGR: +68.88%
- Max drawdown: 4.71%

## Trade outcomes
- Total trades: **35**
- Hit TARGET: **16**   ·   Hit STOP: **5**   ·   Rotated out: 6   ·   Still open at end: 8
- Win rate: 57.1%   ·   Avg R: 0.18   ·   Profit factor: 1.55
- Expectancy / trade: $35   ·   Avg holding: 8.2 days

## P&L detail
- Net P&L: $1,234
- Gross profit: $3,485   ·   Gross loss: $-2,251
- Avg win: $174   ·   Avg loss: $-150
- Best trade: $446   ·   Worst trade: $-421

## What the money-management rules did
- Rotations triggered: 6
- Signals skipped (no cash / no slot): 58
