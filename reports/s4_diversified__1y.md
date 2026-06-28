# s4_diversified  —  1y timeframe

_Window: 2025-06-25 -> 2026-06-25  ·  starting capital Rs 2,000,000_

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
- Capital: Rs 2,000,000  ->  **Rs 1,939,864**
- Total return: **-3.01%**   ·   CAGR: -3.01%
- Max drawdown: 16.57%

## Trade outcomes
- Total trades: **167**
- Hit TARGET: **75**   ·   Hit STOP: **73**   ·   Rotated out: 0   ·   Still open at end: 19
- Win rate: 47.9%   ·   Avg R: -0.01   ·   Profit factor: 0.93
- Expectancy / trade: Rs -372   ·   Avg holding: 37.2 days

## P&L detail
- Net P&L: Rs -62,131
- Gross profit: Rs 773,955   ·   Gross loss: Rs -836,086
- Avg win: Rs 9,674   ·   Avg loss: Rs -9,610
- Best trade: Rs 24,230   ·   Worst trade: Rs -19,747

## What the money-management rules did
- Rotations triggered: 0
- Signals skipped (no cash / no slot): 165
