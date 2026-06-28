# s3_concentrated  —  6wk timeframe

_Window: 2026-05-13 -> 2026-06-24  ·  starting capital $20,000_

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
- Capital: $20,000  ->  **$20,077**
- Total return: **+0.39%**   ·   CAGR: +3.41%
- Max drawdown: 7.72%

## Trade outcomes
- Total trades: **28**
- Hit TARGET: **17**   ·   Hit STOP: **6**   ·   Rotated out: 0   ·   Still open at end: 5
- Win rate: 46.4%   ·   Avg R: 0.05   ·   Profit factor: 1.02
- Expectancy / trade: $2   ·   Avg holding: 6.0 days

## P&L detail
- Net P&L: $67
- Gross profit: $4,518   ·   Gross loss: $-4,450
- Avg win: $348   ·   Avg loss: $-297
- Best trade: $891   ·   Worst trade: $-842

## What the money-management rules did
- Rotations triggered: 0
- Signals skipped (no cash / no slot): 66
