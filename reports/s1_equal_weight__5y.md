# s1_equal_weight  —  5y timeframe

_Window: 2021-06-25 -> 2026-06-25  ·  starting capital Rs 2,000,000_

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
- Capital: Rs 2,000,000  ->  **Rs 3,445,333**
- Total return: **+72.27%**   ·   CAGR: +11.52%
- Max drawdown: 22.11%

## Trade outcomes
- Total trades: **427**
- Hit TARGET: **247**   ·   Hit STOP: **170**   ·   Rotated out: 0   ·   Still open at end: 10
- Win rate: 57.1%   ·   Avg R: 0.16   ·   Profit factor: 1.42
- Expectancy / trade: Rs 3,380   ·   Avg holding: 31.0 days

## P&L detail
- Net P&L: Rs 1,443,233
- Gross profit: Rs 4,910,312   ·   Gross loss: Rs -3,467,079
- Avg win: Rs 20,124   ·   Avg loss: Rs -18,946
- Best trade: Rs 62,208   ·   Worst trade: Rs -48,046

## What the money-management rules did
- Rotations triggered: 0
- Signals skipped (no cash / no slot): 775
