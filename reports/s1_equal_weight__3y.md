# s1_equal_weight  —  3y timeframe

_Window: 2023-06-25 -> 2026-06-25  ·  starting capital Rs 2,000,000_

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
- Capital: Rs 2,000,000  ->  **Rs 3,178,278**
- Total return: **+58.91%**   ·   CAGR: +16.71%
- Max drawdown: 16.05%

## Trade outcomes
- Total trades: **285**
- Hit TARGET: **166**   ·   Hit STOP: **109**   ·   Rotated out: 0   ·   Still open at end: 10
- Win rate: 57.9%   ·   Avg R: 0.19   ·   Profit factor: 1.52
- Expectancy / trade: Rs 4,127   ·   Avg holding: 33.1 days

## P&L detail
- Net P&L: Rs 1,176,178
- Gross profit: Rs 3,434,817   ·   Gross loss: Rs -2,258,639
- Avg win: Rs 20,817   ·   Avg loss: Rs -18,822
- Best trade: Rs 62,208   ·   Worst trade: Rs -39,495

## What the money-management rules did
- Rotations triggered: 0
- Signals skipped (no cash / no slot): 560
