# s1_equal_weight  —  6wk timeframe

_Window: 2026-05-14 -> 2026-06-25  ·  starting capital Rs 2,000,000_

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
- Capital: Rs 2,000,000  ->  **Rs 2,159,449**
- Total return: **+7.97%**   ·   CAGR: +94.85%
- Max drawdown: 3.30%

## Trade outcomes
- Total trades: **25**
- Hit TARGET: **12**   ·   Hit STOP: **3**   ·   Rotated out: 0   ·   Still open at end: 10
- Win rate: 72.0%   ·   Avg R: 0.28   ·   Profit factor: 2.60
- Expectancy / trade: Rs 6,294   ·   Avg holding: 14.2 days

## P&L detail
- Net P&L: Rs 157,349
- Gross profit: Rs 255,795   ·   Gross loss: Rs -98,446
- Avg win: Rs 14,211   ·   Avg loss: Rs -14,064
- Best trade: Rs 22,359   ·   Worst trade: Rs -23,288

## What the money-management rules did
- Rotations triggered: 0
- Signals skipped (no cash / no slot): 36
