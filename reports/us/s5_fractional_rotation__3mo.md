# s5_fractional_rotation  —  3mo timeframe

_Window: 2026-03-24 -> 2026-06-24  ·  starting capital $20,000_

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
- Capital: $20,000  ->  **$23,064**
- Total return: **+15.32%**   ·   CAGR: +76.11%
- Max drawdown: 4.92%

## Trade outcomes
- Total trades: **70**
- Hit TARGET: **33**   ·   Hit STOP: **15**   ·   Rotated out: 14   ·   Still open at end: 8
- Win rate: 64.3%   ·   Avg R: 0.20   ·   Profit factor: 1.71
- Expectancy / trade: $44   ·   Avg holding: 9.3 days

## P&L detail
- Net P&L: $3,056
- Gross profit: $7,356   ·   Gross loss: $-4,300
- Avg win: $163   ·   Avg loss: $-172
- Best trade: $492   ·   Worst trade: $-421

## What the money-management rules did
- Rotations triggered: 14
- Signals skipped (no cash / no slot): 164
