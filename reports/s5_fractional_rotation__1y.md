# s5_fractional_rotation  —  1y timeframe

_Window: 2025-06-25 -> 2026-06-25  ·  starting capital Rs 2,000,000_

## Strategy (plain English — generated from the rules that ran)
```
Policy: s5_fractional_rotation — "Fixed-fractional + rotation: size every trade at 10% of capital, cap the book at 8 positions, and rotate capital out of near-target winners to fund fresh setups. A percent-sized, actively-recycled book."
├── Capital: ₹2,000,000 · max 8 positions
├── Sizing: percent_of_capital — "Allocate 10% of capital per trade."
├── Selection: free_capital_first — "Consider every fresh signal; cash and the position cap gate it downstream."
├── Rotation: nearest_to_target_band — "To fund a new entry, sell the open position closest to its target within 10%; widen the band by 10% up to 40%."
└── Exit: scanner_default — "Exit on V2's own target or stop; no extra exit."
```

## Headline
- Capital: Rs 2,000,000  ->  **Rs 2,022,322**
- Total return: **+1.12%**   ·   CAGR: +1.12%
- Max drawdown: 14.09%

## Trade outcomes
- Total trades: **101**
- Hit TARGET: **32**   ·   Hit STOP: **39**   ·   Rotated out: 22   ·   Still open at end: 8
- Win rate: 54.5%   ·   Avg R: 0.04   ·   Profit factor: 1.02
- Expectancy / trade: Rs 204   ·   Avg holding: 27.3 days

## P&L detail
- Net P&L: Rs 20,642
- Gross profit: Rs 904,668   ·   Gross loss: Rs -884,026
- Avg win: Rs 16,449   ·   Avg loss: Rs -19,218
- Best trade: Rs 35,430   ·   Worst trade: Rs -39,495

## What the money-management rules did
- Rotations triggered: 22
- Signals skipped (no cash / no slot): 235
