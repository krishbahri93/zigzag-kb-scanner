# s2_capital_rotation  —  3y timeframe

_Window: 2023-06-25 -> 2026-06-25  ·  starting capital Rs 2,000,000_

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
- Capital: Rs 2,000,000  ->  **Rs 3,398,268**
- Total return: **+69.91%**   ·   CAGR: +19.34%
- Max drawdown: 11.24%

## Trade outcomes
- Total trades: **348**
- Hit TARGET: **131**   ·   Hit STOP: **118**   ·   Rotated out: 89   ·   Still open at end: 10
- Win rate: 62.1%   ·   Avg R: 0.19   ·   Profit factor: 1.57
- Expectancy / trade: Rs 4,012   ·   Avg holding: 27.4 days

## P&L detail
- Net P&L: Rs 1,396,168
- Gross profit: Rs 3,857,414   ·   Gross loss: Rs -2,461,245
- Avg win: Rs 17,858   ·   Avg loss: Rs -18,646
- Best trade: Rs 52,143   ·   Worst trade: Rs -48,046

## What the money-management rules did
- Rotations triggered: 89
- Signals skipped (no cash / no slot): 490
