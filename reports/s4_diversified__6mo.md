# s4_diversified  —  6mo timeframe

_Window: 2025-12-25 -> 2026-06-25  ·  starting capital Rs 2,000,000_

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
- Capital: Rs 2,000,000  ->  **Rs 1,947,908**
- Total return: **-2.60%**   ·   CAGR: -5.19%
- Max drawdown: 10.70%

## Trade outcomes
- Total trades: **111**
- Hit TARGET: **49**   ·   Hit STOP: **43**   ·   Rotated out: 0   ·   Still open at end: 19
- Win rate: 48.6%   ·   Avg R: -0.00   ·   Profit factor: 0.89
- Expectancy / trade: Rs -487   ·   Avg holding: 24.1 days

## P&L detail
- Net P&L: Rs -54,087
- Gross profit: Rs 455,223   ·   Gross loss: Rs -509,310
- Avg win: Rs 8,430   ·   Avg loss: Rs -8,935
- Best trade: Rs 24,230   ·   Worst trade: Rs -19,747

## What the money-management rules did
- Rotations triggered: 0
- Signals skipped (no cash / no slot): 130
