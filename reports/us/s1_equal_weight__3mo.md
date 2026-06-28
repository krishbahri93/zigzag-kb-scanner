# s1_equal_weight  —  3mo timeframe

_Window: 2026-03-24 -> 2026-06-24  ·  starting capital $20,000_

## Strategy (plain English — generated from the rules that ran)
```
Policy: s1_equal_weight — "Equal-weight, set-and-forget: spread the capital across up to 10 equal-sized positions and hold each to its V2 target or stop. No active capital management."
├── Capital: $20,000 · max 10 positions
├── Sizing: fixed_amount — "Allocate a fixed $2000 per trade."
├── Selection: free_capital_first — "Consider every fresh signal; cash and the position cap gate it downstream."
├── Rotation: none — "No rotation — never sell to fund a new entry."
└── Exit: scanner_default — "Exit on V2's own target or stop; no extra exit."
```

## Headline
- Capital: $20,000  ->  **$23,915**
- Total return: **+19.57%**   ·   CAGR: +103.35%
- Max drawdown: 4.83%

## Trade outcomes
- Total trades: **86**
- Hit TARGET: **59**   ·   Hit STOP: **17**   ·   Rotated out: 0   ·   Still open at end: 10
- Win rate: 61.6%   ·   Avg R: 0.22   ·   Profit factor: 1.67
- Expectancy / trade: $45   ·   Avg holding: 9.2 days

## P&L detail
- Net P&L: $3,905
- Gross profit: $9,735   ·   Gross loss: $-5,830
- Avg win: $184   ·   Avg loss: $-177
- Best trade: $492   ·   Worst trade: $-421

## What the money-management rules did
- Rotations triggered: 0
- Signals skipped (no cash / no slot): 147
