# s1_equal_weight  —  3mo timeframe

_Window: 2026-03-25 -> 2026-06-25  ·  starting capital Rs 2,000,000_

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
- Capital: Rs 2,000,000  ->  **Rs 2,157,430**
- Total return: **+7.87%**   ·   CAGR: +35.10%
- Max drawdown: 8.13%

## Trade outcomes
- Total trades: **40**
- Hit TARGET: **22**   ·   Hit STOP: **8**   ·   Rotated out: 0   ·   Still open at end: 10
- Win rate: 60.0%   ·   Avg R: 0.27   ·   Profit factor: 1.60
- Expectancy / trade: Rs 3,883   ·   Avg holding: 19.8 days

## P&L detail
- Net P&L: Rs 155,330
- Gross profit: Rs 413,815   ·   Gross loss: Rs -258,485
- Avg win: Rs 17,242   ·   Avg loss: Rs -16,155
- Best trade: Rs 48,461   ·   Worst trade: Rs -26,691

## What the money-management rules did
- Rotations triggered: 0
- Signals skipped (no cash / no slot): 137
