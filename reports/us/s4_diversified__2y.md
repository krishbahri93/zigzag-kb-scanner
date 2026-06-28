# s4_diversified  —  2y timeframe

_Window: 2024-06-24 -> 2026-06-24  ·  starting capital $20,000_

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
- Capital: $20,000  ->  **$25,745**
- Total return: **+28.73%**   ·   CAGR: +13.47%
- Max drawdown: 16.18%

## Trade outcomes
- Total trades: **581**
- Hit TARGET: **387**   ·   Hit STOP: **174**   ·   Rotated out: 0   ·   Still open at end: 20
- Win rate: 57.7%   ·   Avg R: 0.12   ·   Profit factor: 1.20
- Expectancy / trade: $10   ·   Avg holding: 14.0 days

## P&L detail
- Net P&L: $5,735
- Gross profit: $34,154   ·   Gross loss: $-28,418
- Avg win: $102   ·   Avg loss: $-116
- Best trade: $313   ·   Worst trade: $-772

## What the money-management rules did
- Rotations triggered: 0
- Signals skipped (no cash / no slot): 316
