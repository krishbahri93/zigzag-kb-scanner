# s4_diversified  —  3y timeframe

_Window: 2023-06-25 -> 2026-06-25  ·  starting capital Rs 2,000,000_

## Strategy (plain English — generated from the rules that ran)
```
Policy: s4_diversified — "Maximum diversification: many small bets - up to 20 positions of 1L each, held to exit. Wide spread smooths the ride but dilutes each winner."
├── Capital: ₹2,000,000 · max 20 positions
├── Sizing: fixed_amount — "Allocate a fixed ₹100000 per trade."
├── Selection: free_capital_first — "Consider every fresh signal; cash and the position cap gate it downstream."
├── Rotation: none — "No rotation — never sell to fund a new entry."
└── Exit: scanner_default — "Exit on V2's own target or stop; no extra exit."
```

## Headline
- Capital: Rs 2,000,000  ->  **Rs 2,678,581**
- Total return: **+33.93%**   ·   CAGR: +10.24%
- Max drawdown: 15.29%

## Trade outcomes
- Total trades: **473**
- Hit TARGET: **264**   ·   Hit STOP: **189**   ·   Rotated out: 0   ·   Still open at end: 20
- Win rate: 55.8%   ·   Avg R: 0.15   ·   Profit factor: 1.33
- Expectancy / trade: Rs 1,430   ·   Avg holding: 36.1 days

## P&L detail
- Net P&L: Rs 676,481
- Gross profit: Rs 2,707,659   ·   Gross loss: Rs -2,031,178
- Avg win: Rs 10,256   ·   Avg loss: Rs -9,719
- Best trade: Rs 31,104   ·   Worst trade: Rs -26,034

## What the money-management rules did
- Rotations triggered: 0
- Signals skipped (no cash / no slot): 355
