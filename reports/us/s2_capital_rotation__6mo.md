# s2_capital_rotation  —  6mo timeframe

_Window: 2025-12-24 -> 2026-06-24  ·  starting capital $20,000_

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
- Capital: $20,000  ->  **$19,032**
- Total return: **-4.84%**   ·   CAGR: -9.52%
- Max drawdown: 27.77%

## Trade outcomes
- Total trades: **124**
- Hit TARGET: **56**   ·   Hit STOP: **38**   ·   Rotated out: 21   ·   Still open at end: 9
- Win rate: 53.2%   ·   Avg R: 0.05   ·   Profit factor: 0.92
- Expectancy / trade: $-8   ·   Avg holding: 11.1 days

## P&L detail
- Net P&L: $-977
- Gross profit: $11,832   ·   Gross loss: $-12,808
- Avg win: $179   ·   Avg loss: $-221
- Best trade: $590   ·   Worst trade: $-1,544

## What the money-management rules did
- Rotations triggered: 21
- Signals skipped (no cash / no slot): 249
