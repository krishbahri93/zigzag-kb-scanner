# s3_concentrated  —  1y timeframe

_Window: 2025-06-24 -> 2026-06-24  ·  starting capital $20,000_

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
- Capital: $20,000  ->  **$24,905**
- Total return: **+24.53%**   ·   CAGR: +24.54%
- Max drawdown: 18.87%

## Trade outcomes
- Total trades: **117**
- Hit TARGET: **77**   ·   Hit STOP: **35**   ·   Rotated out: 0   ·   Still open at end: 5
- Win rate: 54.7%   ·   Avg R: 0.10   ·   Profit factor: 1.23
- Expectancy / trade: $42   ·   Avg holding: 14.3 days

## P&L detail
- Net P&L: $4,895
- Gross profit: $26,249   ·   Gross loss: $-21,354
- Avg win: $410   ·   Avg loss: $-403
- Best trade: $1,193   ·   Worst trade: $-2,776

## What the money-management rules did
- Rotations triggered: 0
- Signals skipped (no cash / no slot): 467
