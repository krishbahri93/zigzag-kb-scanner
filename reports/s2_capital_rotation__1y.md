# s2_capital_rotation  —  1y timeframe

_Window: 2025-06-25 -> 2026-06-25  ·  starting capital Rs 2,000,000_

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
- Capital: Rs 2,000,000  ->  **Rs 2,042,994**
- Total return: **+2.15%**   ·   CAGR: +2.15%
- Max drawdown: 14.76%

## Trade outcomes
- Total trades: **116**
- Hit TARGET: **38**   ·   Hit STOP: **44**   ·   Rotated out: 24   ·   Still open at end: 10
- Win rate: 53.4%   ·   Avg R: 0.04   ·   Profit factor: 1.04
- Expectancy / trade: Rs 353   ·   Avg holding: 27.9 days

## P&L detail
- Net P&L: Rs 40,894
- Gross profit: Rs 1,032,717   ·   Gross loss: Rs -991,823
- Avg win: Rs 16,657   ·   Avg loss: Rs -18,367
- Best trade: Rs 35,430   ·   Worst trade: Rs -39,495

## What the money-management rules did
- Rotations triggered: 24
- Signals skipped (no cash / no slot): 218
