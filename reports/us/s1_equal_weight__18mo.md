# s1_equal_weight  —  18mo timeframe

_Window: 2024-12-24 -> 2026-06-24  ·  starting capital $20,000_

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
- Capital: $20,000  ->  **$27,700**
- Total return: **+38.50%**   ·   CAGR: +24.34%
- Max drawdown: 31.87%

## Trade outcomes
- Total trades: **327**
- Hit TARGET: **215**   ·   Hit STOP: **102**   ·   Rotated out: 0   ·   Still open at end: 10
- Win rate: 57.8%   ·   Avg R: 0.12   ·   Profit factor: 1.24
- Expectancy / trade: $24   ·   Avg holding: 13.2 days

## P&L detail
- Net P&L: $7,690
- Gross profit: $39,586   ·   Gross loss: $-31,897
- Avg win: $209   ·   Avg loss: $-231
- Best trade: $627   ·   Worst trade: $-1,388

## What the money-management rules did
- Rotations triggered: 0
- Signals skipped (no cash / no slot): 531
