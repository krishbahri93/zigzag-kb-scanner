# s2_capital_rotation  —  18mo timeframe

_Window: 2024-12-24 -> 2026-06-24  ·  starting capital $20,000_

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
- Capital: $20,000  ->  **$25,078**
- Total return: **+25.39%**   ·   CAGR: +16.34%
- Max drawdown: 31.87%

## Trade outcomes
- Total trades: **356**
- Hit TARGET: **181**   ·   Hit STOP: **109**   ·   Rotated out: 56   ·   Still open at end: 10
- Win rate: 59.0%   ·   Avg R: 0.10   ·   Profit factor: 1.15
- Expectancy / trade: $14   ·   Avg holding: 11.9 days

## P&L detail
- Net P&L: $5,068
- Gross profit: $39,727   ·   Gross loss: $-34,659
- Avg win: $189   ·   Avg loss: $-237
- Best trade: $627   ·   Worst trade: $-1,544

## What the money-management rules did
- Rotations triggered: 56
- Signals skipped (no cash / no slot): 489
