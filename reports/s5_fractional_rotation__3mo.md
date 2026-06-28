# s5_fractional_rotation  —  3mo timeframe

_Window: 2026-03-25 -> 2026-06-25  ·  starting capital Rs 2,000,000_

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
- Capital: Rs 2,000,000  ->  **Rs 2,201,880**
- Total return: **+10.09%**   ·   CAGR: +46.49%
- Max drawdown: 5.08%

## Trade outcomes
- Total trades: **41**
- Hit TARGET: **14**   ·   Hit STOP: **8**   ·   Rotated out: 11   ·   Still open at end: 8
- Win rate: 65.9%   ·   Avg R: 0.28   ·   Profit factor: 1.89
- Expectancy / trade: Rs 4,883   ·   Avg holding: 15.7 days

## P&L detail
- Net P&L: Rs 200,200
- Gross profit: Rs 424,841   ·   Gross loss: Rs -224,641
- Avg win: Rs 15,735   ·   Avg loss: Rs -16,046
- Best trade: Rs 33,993   ·   Worst trade: Rs -26,691

## What the money-management rules did
- Rotations triggered: 11
- Signals skipped (no cash / no slot): 135
