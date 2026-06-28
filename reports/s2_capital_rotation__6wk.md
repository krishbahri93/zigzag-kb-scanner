# s2_capital_rotation  —  6wk timeframe

_Window: 2026-05-14 -> 2026-06-25  ·  starting capital Rs 2,000,000_

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
- Capital: Rs 2,000,000  ->  **Rs 2,131,697**
- Total return: **+6.58%**   ·   CAGR: +74.12%
- Max drawdown: 3.63%

## Trade outcomes
- Total trades: **27**
- Hit TARGET: **9**   ·   Hit STOP: **3**   ·   Rotated out: 5   ·   Still open at end: 10
- Win rate: 63.0%   ·   Avg R: 0.21   ·   Profit factor: 2.00
- Expectancy / trade: Rs 4,800   ·   Avg holding: 13.1 days

## P&L detail
- Net P&L: Rs 129,597
- Gross profit: Rs 259,083   ·   Gross loss: Rs -129,486
- Avg win: Rs 15,240   ·   Avg loss: Rs -12,949
- Best trade: Rs 22,359   ·   Worst trade: Rs -23,288

## What the money-management rules did
- Rotations triggered: 5
- Signals skipped (no cash / no slot): 34
