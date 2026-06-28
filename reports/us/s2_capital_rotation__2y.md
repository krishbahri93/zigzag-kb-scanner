# s2_capital_rotation  —  2y timeframe

_Window: 2024-06-24 -> 2026-06-24  ·  starting capital $20,000_

## Strategy (plain English — generated from the rules that ran)
```
Policy: s2_capital_rotation — "Equal-weight, but recycle capital: same 10 x $2k sizing, and when fully invested, sell the open position nearest its target (widening 10%->40% band) to fund a fresh setup instead of skipping it."
├── Capital: $20,000 · max 10 positions
├── Sizing: fixed_amount — "Allocate a fixed $2000 per trade."
├── Selection: free_capital_first — "Consider every fresh signal; cash and the position cap gate it downstream."
├── Rotation: nearest_to_target_band — "To fund a new entry, sell the open position closest to its target within 10%; widen the band by 10% up to 40%."
└── Exit: scanner_default — "Exit on V2's own target or stop; no extra exit."
```

## Headline
- Capital: $20,000  ->  **$26,044**
- Total return: **+30.22%**   ·   CAGR: +14.12%
- Max drawdown: 28.68%

## Trade outcomes
- Total trades: **422**
- Hit TARGET: **227**   ·   Hit STOP: **129**   ·   Rotated out: 56   ·   Still open at end: 10
- Win rate: 58.5%   ·   Avg R: 0.10   ·   Profit factor: 1.15
- Expectancy / trade: $14   ·   Avg holding: 11.6 days

## P&L detail
- Net P&L: $6,034
- Gross profit: $47,153   ·   Gross loss: $-41,119
- Avg win: $191   ·   Avg loss: $-235
- Best trade: $627   ·   Worst trade: $-1,544

## What the money-management rules did
- Rotations triggered: 56
- Signals skipped (no cash / no slot): 488
