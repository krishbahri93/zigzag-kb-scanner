# s2_capital_rotation  —  6mo timeframe

_Window: 2025-12-25 -> 2026-06-25  ·  starting capital Rs 2,000,000_

## Strategy (plain English — generated from the rules that ran)
```
Policy: s2_capital_rotation — "Equal-weight, but recycle capital: same 10 x 2L sizing, and when fully invested, sell the open position nearest its target (widening 10%->40% band) to fund a fresh setup instead of skipping it."
├── Capital: ₹2,000,000 · max 10 positions
├── Sizing: fixed_amount — "Allocate a fixed ₹200000 per trade."
├── Selection: free_capital_first — "Consider every fresh signal; cash and the position cap gate it downstream."
├── Rotation: nearest_to_target_band — "To fund a new entry, sell the open position closest to its target within 10%; widen the band by 10% up to 40%."
└── Exit: scanner_default — "Exit on V2's own target or stop; no extra exit."
```

## Headline
- Capital: Rs 2,000,000  ->  **Rs 1,843,706**
- Total return: **-7.81%**   ·   CAGR: -15.14%
- Max drawdown: 14.42%

## Trade outcomes
- Total trades: **68**
- Hit TARGET: **23**   ·   Hit STOP: **29**   ·   Rotated out: 7   ·   Still open at end: 9
- Win rate: 45.6%   ·   Avg R: -0.10   ·   Profit factor: 0.76
- Expectancy / trade: Rs -2,326   ·   Avg holding: 21.1 days

## P&L detail
- Net P&L: Rs -158,184
- Gross profit: Rs 504,874   ·   Gross loss: Rs -663,059
- Avg win: Rs 16,286   ·   Avg loss: Rs -17,921
- Best trade: Rs 26,377   ·   Worst trade: Rs -39,495

## What the money-management rules did
- Rotations triggered: 7
- Signals skipped (no cash / no slot): 175
