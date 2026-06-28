# s2_capital_rotation  —  5y timeframe

_Window: 2021-06-25 -> 2026-06-25  ·  starting capital Rs 2,000,000_

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
- Capital: Rs 2,000,000  ->  **Rs 3,521,679**
- Total return: **+76.08%**   ·   CAGR: +12.01%
- Max drawdown: 21.19%

## Trade outcomes
- Total trades: **499**
- Hit TARGET: **187**   ·   Hit STOP: **184**   ·   Rotated out: 118   ·   Still open at end: 10
- Win rate: 59.7%   ·   Avg R: 0.14   ·   Profit factor: 1.41
- Expectancy / trade: Rs 3,045   ·   Avg holding: 26.6 days

## P&L detail
- Net P&L: Rs 1,519,579
- Gross profit: Rs 5,250,198   ·   Gross loss: Rs -3,730,619
- Avg win: Rs 17,618   ·   Avg loss: Rs -18,560
- Best trade: Rs 55,688   ·   Worst trade: Rs -48,046

## What the money-management rules did
- Rotations triggered: 118
- Signals skipped (no cash / no slot): 692
