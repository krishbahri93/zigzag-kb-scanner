# s2_capital_rotation  —  1y timeframe

_Window: 2025-06-24 -> 2026-06-24  ·  starting capital $20,000_

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
- Capital: $20,000  ->  **$22,926**
- Total return: **+14.63%**   ·   CAGR: +14.64%
- Max drawdown: 21.11%

## Trade outcomes
- Total trades: **247**
- Hit TARGET: **117**   ·   Hit STOP: **75**   ·   Rotated out: 45   ·   Still open at end: 10
- Win rate: 57.9%   ·   Avg R: 0.11   ·   Profit factor: 1.12
- Expectancy / trade: $12   ·   Avg holding: 12.9 days

## P&L detail
- Net P&L: $2,916
- Gross profit: $27,785   ·   Gross loss: $-24,870
- Avg win: $194   ·   Avg loss: $-239
- Best trade: $650   ·   Worst trade: $-1,544

## What the money-management rules did
- Rotations triggered: 45
- Signals skipped (no cash / no slot): 325
