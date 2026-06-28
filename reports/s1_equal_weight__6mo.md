# s1_equal_weight  —  6mo timeframe

_Window: 2025-12-25 -> 2026-06-25  ·  starting capital Rs 2,000,000_

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
- Capital: Rs 2,000,000  ->  **Rs 1,898,353**
- Total return: **-5.08%**   ·   CAGR: -9.99%
- Max drawdown: 13.83%

## Trade outcomes
- Total trades: **63**
- Hit TARGET: **26**   ·   Hit STOP: **28**   ·   Rotated out: 0   ·   Still open at end: 9
- Win rate: 46.0%   ·   Avg R: -0.06   ·   Profit factor: 0.83
- Expectancy / trade: Rs -1,643   ·   Avg holding: 22.9 days

## P&L detail
- Net P&L: Rs -103,537
- Gross profit: Rs 494,610   ·   Gross loss: Rs -598,147
- Avg win: Rs 17,056   ·   Avg loss: Rs -17,593
- Best trade: Rs 29,351   ·   Worst trade: Rs -39,495

## What the money-management rules did
- Rotations triggered: 0
- Signals skipped (no cash / no slot): 180
