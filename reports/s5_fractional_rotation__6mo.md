# s5_fractional_rotation  —  6mo timeframe

_Window: 2025-12-25 -> 2026-06-25  ·  starting capital Rs 2,000,000_

## Strategy (plain English — generated from the rules that ran)
```
Policy: s5_fractional_rotation — "Fixed-fractional + rotation: size every trade at 10% of capital, cap the book at 8 positions, and rotate capital out of near-target winners to fund fresh setups. A percent-sized, actively-recycled book."
├── Capital: ₹2,000,000 · max 8 positions
├── Sizing: percent_of_capital — "Allocate 10% of capital per trade."
├── Selection: free_capital_first — "Consider every fresh signal; cash and the position cap gate it downstream."
├── Rotation: nearest_to_target_band — "To fund a new entry, sell the open position closest to its target within 10%; widen the band by 10% up to 40%."
└── Exit: scanner_default — "Exit on V2's own target or stop; no extra exit."
```

## Headline
- Capital: Rs 2,000,000  ->  **Rs 1,880,554**
- Total return: **-5.97%**   ·   CAGR: -11.69%
- Max drawdown: 13.45%

## Trade outcomes
- Total trades: **64**
- Hit TARGET: **22**   ·   Hit STOP: **27**   ·   Rotated out: 7   ·   Still open at end: 8
- Win rate: 46.9%   ·   Avg R: -0.08   ·   Profit factor: 0.80
- Expectancy / trade: Rs -1,893   ·   Avg holding: 20.2 days

## P&L detail
- Net P&L: Rs -121,126
- Gross profit: Rs 488,660   ·   Gross loss: Rs -609,786
- Avg win: Rs 16,289   ·   Avg loss: Rs -17,935
- Best trade: Rs 26,377   ·   Worst trade: Rs -39,495

## What the money-management rules did
- Rotations triggered: 7
- Signals skipped (no cash / no slot): 179
