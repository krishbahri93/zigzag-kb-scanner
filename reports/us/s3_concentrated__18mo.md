# s3_concentrated  —  18mo timeframe

_Window: 2024-12-24 -> 2026-06-24  ·  starting capital $20,000_

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
- Capital: $20,000  ->  **$19,058**
- Total return: **-4.71%**   ·   CAGR: -3.18%
- Max drawdown: 48.66%

## Trade outcomes
- Total trades: **152**
- Hit TARGET: **95**   ·   Hit STOP: **53**   ·   Rotated out: 0   ·   Still open at end: 4
- Win rate: 51.3%   ·   Avg R: 0.02   ·   Profit factor: 0.97
- Expectancy / trade: $-6   ·   Avg holding: 12.0 days

## P&L detail
- Net P&L: $-950
- Gross profit: $31,701   ·   Gross loss: $-32,651
- Avg win: $406   ·   Avg loss: $-441
- Best trade: $1,193   ·   Worst trade: $-2,776

## What the money-management rules did
- Rotations triggered: 0
- Signals skipped (no cash / no slot): 713
