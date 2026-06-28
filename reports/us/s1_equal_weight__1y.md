# s1_equal_weight  —  1y timeframe

_Window: 2025-06-24 -> 2026-06-24  ·  starting capital $20,000_

## Strategy (plain English — generated from the rules that ran)
```
Policy: s1_equal_weight — "Equal-weight, set-and-forget: spread the capital across up to 10 equal-sized positions and hold each to its V2 target or stop. No active capital management."
├── Capital: $20,000 · max 10 positions
├── Sizing: fixed_amount — "Allocate a fixed $2000 per trade."
├── Selection: free_capital_first — "Consider every fresh signal; cash and the position cap gate it downstream."
├── Rotation: none — "No rotation — never sell to fund a new entry."
└── Exit: scanner_default — "Exit on V2's own target or stop; no extra exit."
```

## Headline
- Capital: $20,000  ->  **$25,017**
- Total return: **+25.09%**   ·   CAGR: +25.11%
- Max drawdown: 17.12%

## Trade outcomes
- Total trades: **211**
- Hit TARGET: **133**   ·   Hit STOP: **68**   ·   Rotated out: 0   ·   Still open at end: 10
- Win rate: 55.0%   ·   Avg R: 0.12   ·   Profit factor: 1.24
- Expectancy / trade: $24   ·   Avg holding: 15.5 days

## P&L detail
- Net P&L: $5,007
- Gross profit: $25,713   ·   Gross loss: $-20,705
- Avg win: $222   ·   Avg loss: $-218
- Best trade: $650   ·   Worst trade: $-1,388

## What the money-management rules did
- Rotations triggered: 0
- Signals skipped (no cash / no slot): 371
