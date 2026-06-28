# s1_equal_weight  —  6mo timeframe

_Window: 2025-12-24 -> 2026-06-24  ·  starting capital $20,000_

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
- Capital: $20,000  ->  **$19,601**
- Total return: **-1.99%**   ·   CAGR: -3.98%
- Max drawdown: 24.62%

## Trade outcomes
- Total trades: **119**
- Hit TARGET: **72**   ·   Hit STOP: **37**   ·   Rotated out: 0   ·   Still open at end: 10
- Win rate: 52.9%   ·   Avg R: 0.06   ·   Profit factor: 0.97
- Expectancy / trade: $-3   ·   Avg holding: 11.6 days

## P&L detail
- Net P&L: $-409
- Gross profit: $11,850   ·   Gross loss: $-12,258
- Avg win: $188   ·   Avg loss: $-219
- Best trade: $590   ·   Worst trade: $-1,544

## What the money-management rules did
- Rotations triggered: 0
- Signals skipped (no cash / no slot): 257
