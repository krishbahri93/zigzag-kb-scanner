# s5_fractional_rotation  —  5y timeframe

_Window: 2021-06-25 -> 2026-06-25  ·  starting capital Rs 2,000,000_

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
- Capital: Rs 2,000,000  ->  **Rs 3,166,484**
- Total return: **+58.32%**   ·   CAGR: +9.65%
- Max drawdown: 17.86%

## Trade outcomes
- Total trades: **429**
- Hit TARGET: **156**   ·   Hit STOP: **158**   ·   Rotated out: 107   ·   Still open at end: 8
- Win rate: 59.7%   ·   Avg R: 0.13   ·   Profit factor: 1.36
- Expectancy / trade: Rs 2,715   ·   Avg holding: 25.5 days

## P&L detail
- Net P&L: Rs 1,164,804
- Gross profit: Rs 4,376,446   ·   Gross loss: Rs -3,211,642
- Avg win: Rs 17,095   ·   Avg loss: Rs -18,564
- Best trade: Rs 55,688   ·   Worst trade: Rs -48,046

## What the money-management rules did
- Rotations triggered: 107
- Signals skipped (no cash / no slot): 770
