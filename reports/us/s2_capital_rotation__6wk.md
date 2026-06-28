# s2_capital_rotation  —  6wk timeframe

_Window: 2026-05-13 -> 2026-06-24  ·  starting capital $20,000_

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
- Capital: $20,000  ->  **$21,319**
- Total return: **+6.59%**   ·   CAGR: +74.24%
- Max drawdown: 7.39%

## Trade outcomes
- Total trades: **44**
- Hit TARGET: **21**   ·   Hit STOP: **7**   ·   Rotated out: 6   ·   Still open at end: 10
- Win rate: 56.8%   ·   Avg R: 0.18   ·   Profit factor: 1.41
- Expectancy / trade: $30   ·   Avg holding: 7.8 days

## P&L detail
- Net P&L: $1,309
- Gross profit: $4,506   ·   Gross loss: $-3,198
- Avg win: $180   ·   Avg loss: $-168
- Best trade: $446   ·   Worst trade: $-482

## What the money-management rules did
- Rotations triggered: 6
- Signals skipped (no cash / no slot): 47
