# s1_equal_weight  —  6wk timeframe

_Window: 2026-05-13 -> 2026-06-24  ·  starting capital $20,000_

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
- Capital: $20,000  ->  **$20,800**
- Total return: **+4.00%**   ·   CAGR: +40.67%
- Max drawdown: 5.01%

## Trade outcomes
- Total trades: **42**
- Hit TARGET: **25**   ·   Hit STOP: **7**   ·   Rotated out: 0   ·   Still open at end: 10
- Win rate: 52.4%   ·   Avg R: 0.12   ·   Profit factor: 1.24
- Expectancy / trade: $19   ·   Avg holding: 8.3 days

## P&L detail
- Net P&L: $790
- Gross profit: $4,090   ·   Gross loss: $-3,300
- Avg win: $186   ·   Avg loss: $-165
- Best trade: $446   ·   Worst trade: $-482

## What the money-management rules did
- Rotations triggered: 0
- Signals skipped (no cash / no slot): 50
