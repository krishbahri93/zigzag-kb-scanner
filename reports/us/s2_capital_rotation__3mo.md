# s2_capital_rotation  —  3mo timeframe

_Window: 2026-03-24 -> 2026-06-24  ·  starting capital $20,000_

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
- Capital: $20,000  ->  **$23,086**
- Total return: **+15.43%**   ·   CAGR: +76.76%
- Max drawdown: 6.23%

## Trade outcomes
- Total trades: **86**
- Hit TARGET: **40**   ·   Hit STOP: **17**   ·   Rotated out: 19   ·   Still open at end: 10
- Win rate: 62.8%   ·   Avg R: 0.20   ·   Profit factor: 1.55
- Expectancy / trade: $36   ·   Avg holding: 9.3 days

## P&L detail
- Net P&L: $3,076
- Gross profit: $8,676   ·   Gross loss: $-5,600
- Avg win: $161   ·   Avg loss: $-175
- Best trade: $492   ·   Worst trade: $-660

## What the money-management rules did
- Rotations triggered: 19
- Signals skipped (no cash / no slot): 145
