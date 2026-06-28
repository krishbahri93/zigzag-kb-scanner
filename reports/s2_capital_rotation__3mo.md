# s2_capital_rotation  —  3mo timeframe

_Window: 2026-03-25 -> 2026-06-25  ·  starting capital Rs 2,000,000_

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
- Capital: Rs 2,000,000  ->  **Rs 2,215,967**
- Total return: **+10.80%**   ·   CAGR: +50.25%
- Max drawdown: 5.72%

## Trade outcomes
- Total trades: **46**
- Hit TARGET: **16**   ·   Hit STOP: **8**   ·   Rotated out: 12   ·   Still open at end: 10
- Win rate: 65.2%   ·   Avg R: 0.28   ·   Profit factor: 1.88
- Expectancy / trade: Rs 4,649   ·   Avg holding: 17.2 days

## P&L detail
- Net P&L: Rs 213,867
- Gross profit: Rs 456,778   ·   Gross loss: Rs -242,911
- Avg win: Rs 15,226   ·   Avg loss: Rs -15,182
- Best trade: Rs 33,993   ·   Worst trade: Rs -26,691

## What the money-management rules did
- Rotations triggered: 12
- Signals skipped (no cash / no slot): 130
