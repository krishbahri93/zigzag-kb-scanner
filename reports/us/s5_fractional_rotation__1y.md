# s5_fractional_rotation  —  1y timeframe

_Window: 2025-06-24 -> 2026-06-24  ·  starting capital $20,000_

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
- Capital: $20,000  ->  **$24,433**
- Total return: **+22.16%**   ·   CAGR: +22.18%
- Max drawdown: 18.45%

## Trade outcomes
- Total trades: **201**
- Hit TARGET: **94**   ·   Hit STOP: **62**   ·   Rotated out: 37   ·   Still open at end: 8
- Win rate: 57.7%   ·   Avg R: 0.13   ·   Profit factor: 1.22
- Expectancy / trade: $22   ·   Avg holding: 13.1 days

## P&L detail
- Net P&L: $4,425
- Gross profit: $24,195   ·   Gross loss: $-19,771
- Avg win: $209   ·   Avg loss: $-233
- Best trade: $650   ·   Worst trade: $-1,544

## What the money-management rules did
- Rotations triggered: 37
- Signals skipped (no cash / no slot): 374
