# s1_equal_weight  —  1y timeframe

_Window: 2025-06-25 -> 2026-06-25  ·  starting capital Rs 2,000,000_

## Strategy (plain English — generated from the rules that ran)
```
Policy: s1_equal_weight — "Equal-weight, set-and-forget: spread the capital across up to 10 equal-sized positions and hold each to its V2 target or stop. No active capital management."
├── Capital: ₹2,000,000 · max 10 positions
├── Sizing: fixed_amount — "Allocate a fixed ₹200000 per trade."
├── Selection: free_capital_first — "Consider every fresh signal; cash and the position cap gate it downstream."
├── Rotation: none — "No rotation — never sell to fund a new entry."
└── Exit: scanner_default — "Exit on V2's own target or stop; no extra exit."
```

## Headline
- Capital: Rs 2,000,000  ->  **Rs 1,869,043**
- Total return: **-6.55%**   ·   CAGR: -6.55%
- Max drawdown: 23.41%

## Trade outcomes
- Total trades: **80**
- Hit TARGET: **34**   ·   Hit STOP: **37**   ·   Rotated out: 0   ·   Still open at end: 9
- Win rate: 45.0%   ·   Avg R: -0.05   ·   Profit factor: 0.84
- Expectancy / trade: Rs -1,661   ·   Avg holding: 37.7 days

## P&L detail
- Net P&L: Rs -132,847
- Gross profit: Rs 692,664   ·   Gross loss: Rs -825,510
- Avg win: Rs 19,241   ·   Avg loss: Rs -18,762
- Best trade: Rs 33,291   ·   Worst trade: Rs -39,495

## What the money-management rules did
- Rotations triggered: 0
- Signals skipped (no cash / no slot): 257
