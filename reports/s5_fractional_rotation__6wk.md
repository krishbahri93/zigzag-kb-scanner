# s5_fractional_rotation  —  6wk timeframe

_Window: 2026-05-14 -> 2026-06-25  ·  starting capital Rs 2,000,000_

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
- Capital: Rs 2,000,000  ->  **Rs 2,149,928**
- Total return: **+7.50%**   ·   CAGR: +87.51%
- Max drawdown: 2.48%

## Trade outcomes
- Total trades: **23**
- Hit TARGET: **9**   ·   Hit STOP: **2**   ·   Rotated out: 4   ·   Still open at end: 8
- Win rate: 69.6%   ·   Avg R: 0.29   ·   Profit factor: 2.60
- Expectancy / trade: Rs 6,446   ·   Avg holding: 12.9 days

## P&L detail
- Net P&L: Rs 148,248
- Gross profit: Rs 240,628   ·   Gross loss: Rs -92,380
- Avg win: Rs 15,039   ·   Avg loss: Rs -13,197
- Best trade: Rs 22,359   ·   Worst trade: Rs -23,288

## What the money-management rules did
- Rotations triggered: 4
- Signals skipped (no cash / no slot): 38
