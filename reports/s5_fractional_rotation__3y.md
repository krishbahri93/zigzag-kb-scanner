# s5_fractional_rotation  —  3y timeframe

_Window: 2023-06-25 -> 2026-06-25  ·  starting capital Rs 2,000,000_

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
- Capital: Rs 2,000,000  ->  **Rs 3,152,402**
- Total return: **+57.62%**   ·   CAGR: +16.39%
- Max drawdown: 12.06%

## Trade outcomes
- Total trades: **299**
- Hit TARGET: **105**   ·   Hit STOP: **101**   ·   Rotated out: 85   ·   Still open at end: 8
- Win rate: 62.2%   ·   Avg R: 0.18   ·   Profit factor: 1.55
- Expectancy / trade: Rs 3,849   ·   Avg holding: 25.9 days

## P&L detail
- Net P&L: Rs 1,150,722
- Gross profit: Rs 3,256,455   ·   Gross loss: Rs -2,105,733
- Avg win: Rs 17,508   ·   Avg loss: Rs -18,635
- Best trade: Rs 52,143   ·   Worst trade: Rs -48,046

## What the money-management rules did
- Rotations triggered: 85
- Signals skipped (no cash / no slot): 544
