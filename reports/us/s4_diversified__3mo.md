# s4_diversified  —  3mo timeframe

_Window: 2026-03-24 -> 2026-06-24  ·  starting capital $20,000_

## Strategy (plain English — generated from the rules that ran)
```
Policy: s4_diversified — "Maximum diversification: many small bets - up to 20 positions of $1k each, held to exit. Wide spread smooths the ride but dilutes each winner."
├── Capital: $20,000 · max 20 positions
├── Sizing: fixed_amount — "Allocate a fixed $1000 per trade."
├── Selection: free_capital_first — "Consider every fresh signal; cash and the position cap gate it downstream."
├── Rotation: none — "No rotation — never sell to fund a new entry."
└── Exit: scanner_default — "Exit on V2's own target or stop; no extra exit."
```

## Headline
- Capital: $20,000  ->  **$21,527**
- Total return: **+7.64%**   ·   CAGR: +33.93%
- Max drawdown: 9.26%

## Trade outcomes
- Total trades: **145**
- Hit TARGET: **91**   ·   Hit STOP: **35**   ·   Rotated out: 0   ·   Still open at end: 19
- Win rate: 57.9%   ·   Avg R: 0.16   ·   Profit factor: 1.24
- Expectancy / trade: $10   ·   Avg holding: 10.0 days

## P&L detail
- Net P&L: $1,518
- Gross profit: $7,729   ·   Gross loss: $-6,211
- Avg win: $92   ·   Avg loss: $-102
- Best trade: $246   ·   Worst trade: $-739

## What the money-management rules did
- Rotations triggered: 0
- Signals skipped (no cash / no slot): 83
