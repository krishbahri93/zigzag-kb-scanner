# s3_concentrated  —  6mo timeframe

_Window: 2025-12-24 -> 2026-06-24  ·  starting capital $20,000_

## Strategy (plain English — generated from the rules that ran)
```
Policy: s3_concentrated — "High conviction, concentrated: fewer but bigger bets - up to 5 positions of $4k each, held to exit. More exposure per name, higher variance."
├── Capital: $20,000 · max 5 positions
├── Sizing: fixed_amount — "Allocate a fixed $4000 per trade."
├── Selection: free_capital_first — "Consider every fresh signal; cash and the position cap gate it downstream."
├── Rotation: none — "No rotation — never sell to fund a new entry."
└── Exit: scanner_default — "Exit on V2's own target or stop; no extra exit."
```

## Headline
- Capital: $20,000  ->  **$18,924**
- Total return: **-5.38%**   ·   CAGR: -10.56%
- Max drawdown: 22.97%

## Trade outcomes
- Total trades: **56**
- Hit TARGET: **34**   ·   Hit STOP: **17**   ·   Rotated out: 0   ·   Still open at end: 5
- Win rate: 50.0%   ·   Avg R: 0.02   ·   Profit factor: 0.90
- Expectancy / trade: $-19   ·   Avg holding: 12.9 days

## P&L detail
- Net P&L: $-1,086
- Gross profit: $10,301   ·   Gross loss: $-11,387
- Avg win: $368   ·   Avg loss: $-407
- Best trade: $984   ·   Worst trade: $-1,314

## What the money-management rules did
- Rotations triggered: 0
- Signals skipped (no cash / no slot): 325
