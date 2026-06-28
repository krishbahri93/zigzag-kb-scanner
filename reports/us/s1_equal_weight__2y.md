# s1_equal_weight  —  2y timeframe

_Window: 2024-06-24 -> 2026-06-24  ·  starting capital $20,000_

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
- Capital: $20,000  ->  **$30,479**
- Total return: **+52.39%**   ·   CAGR: +23.47%
- Max drawdown: 28.68%

## Trade outcomes
- Total trades: **388**
- Hit TARGET: **260**   ·   Hit STOP: **118**   ·   Rotated out: 0   ·   Still open at end: 10
- Win rate: 58.8%   ·   Avg R: 0.13   ·   Profit factor: 1.29
- Expectancy / trade: $27   ·   Avg holding: 12.7 days

## P&L detail
- Net P&L: $10,469
- Gross profit: $46,886   ·   Gross loss: $-36,417
- Avg win: $206   ·   Avg loss: $-228
- Best trade: $627   ·   Worst trade: $-1,388

## What the money-management rules did
- Rotations triggered: 0
- Signals skipped (no cash / no slot): 532
