# s4_diversified  —  6wk timeframe

_Window: 2026-05-14 -> 2026-06-25  ·  starting capital Rs 2,000,000_

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
- Capital: Rs 2,000,000  ->  **Rs 2,073,935**
- Total return: **+3.70%**   ·   CAGR: +37.12%
- Max drawdown: 2.97%

## Trade outcomes
- Total trades: **38**
- Hit TARGET: **14**   ·   Hit STOP: **4**   ·   Rotated out: 0   ·   Still open at end: 20
- Win rate: 65.8%   ·   Avg R: 0.19   ·   Profit factor: 1.79
- Expectancy / trade: Rs 1,890   ·   Avg holding: 15.6 days

## P&L detail
- Net P&L: Rs 71,835
- Gross profit: Rs 163,175   ·   Gross loss: Rs -91,340
- Avg win: Rs 6,527   ·   Avg loss: Rs -7,026
- Best trade: Rs 11,179   ·   Worst trade: Rs -13,690

## What the money-management rules did
- Rotations triggered: 0
- Signals skipped (no cash / no slot): 20
