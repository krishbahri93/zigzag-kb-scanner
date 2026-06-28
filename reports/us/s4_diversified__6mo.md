# s4_diversified  —  6mo timeframe

_Window: 2025-12-24 -> 2026-06-24  ·  starting capital $20,000_

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
- Capital: $20,000  ->  **$18,812**
- Total return: **-5.94%**   ·   CAGR: -11.63%
- Max drawdown: 21.26%

## Trade outcomes
- Total trades: **219**
- Hit TARGET: **132**   ·   Hit STOP: **68**   ·   Rotated out: 0   ·   Still open at end: 19
- Win rate: 52.5%   ·   Avg R: 0.04   ·   Profit factor: 0.90
- Expectancy / trade: $-5   ·   Avg holding: 12.4 days

## P&L detail
- Net P&L: $-1,198
- Gross profit: $10,497   ·   Gross loss: $-11,695
- Avg win: $91   ·   Avg loss: $-112
- Best trade: $295   ·   Worst trade: $-772

## What the money-management rules did
- Rotations triggered: 0
- Signals skipped (no cash / no slot): 152
