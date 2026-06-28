# s4_diversified  —  1y timeframe

_Window: 2025-06-24 -> 2026-06-24  ·  starting capital $20,000_

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
- Capital: $20,000  ->  **$22,742**
- Total return: **+13.71%**   ·   CAGR: +13.72%
- Max drawdown: 18.17%

## Trade outcomes
- Total trades: **379**
- Hit TARGET: **240**   ·   Hit STOP: **119**   ·   Rotated out: 0   ·   Still open at end: 20
- Win rate: 55.4%   ·   Avg R: 0.10   ·   Profit factor: 1.14
- Expectancy / trade: $7   ·   Avg holding: 15.3 days

## P&L detail
- Net P&L: $2,732
- Gross profit: $21,609   ·   Gross loss: $-18,878
- Avg win: $103   ·   Avg loss: $-112
- Best trade: $325   ·   Worst trade: $-772

## What the money-management rules did
- Rotations triggered: 0
- Signals skipped (no cash / no slot): 183
