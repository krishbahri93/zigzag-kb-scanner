# s4_diversified  —  18mo timeframe

_Window: 2024-12-24 -> 2026-06-24  ·  starting capital $20,000_

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
- Capital: $20,000  ->  **$23,813**
- Total return: **+19.07%**   ·   CAGR: +12.38%
- Max drawdown: 17.41%

## Trade outcomes
- Total trades: **515**
- Hit TARGET: **336**   ·   Hit STOP: **159**   ·   Rotated out: 0   ·   Still open at end: 20
- Win rate: 56.7%   ·   Avg R: 0.11   ·   Profit factor: 1.15
- Expectancy / trade: $7   ·   Avg holding: 14.6 days

## P&L detail
- Net P&L: $3,803
- Gross profit: $29,876   ·   Gross loss: $-26,072
- Avg win: $102   ·   Avg loss: $-117
- Best trade: $313   ·   Worst trade: $-772

## What the money-management rules did
- Rotations triggered: 0
- Signals skipped (no cash / no slot): 318
