# s4_diversified  —  5y timeframe

_Window: 2021-06-25 -> 2026-06-25  ·  starting capital Rs 2,000,000_

## Strategy (plain English — generated from the rules that ran)
```
Policy: s4_diversified — "Maximum diversification: many small bets - up to 20 positions of 1L each, held to exit. Wide spread smooths the ride but dilutes each winner."
├── Capital: ₹2,000,000 · max 20 positions
├── Sizing: fixed_amount — "Allocate a fixed ₹100000 per trade."
├── Selection: free_capital_first — "Consider every fresh signal; cash and the position cap gate it downstream."
├── Rotation: none — "No rotation — never sell to fund a new entry."
└── Exit: scanner_default — "Exit on V2's own target or stop; no extra exit."
```

## Headline
- Capital: Rs 2,000,000  ->  **Rs 3,129,836**
- Total return: **+56.49%**   ·   CAGR: +9.39%
- Max drawdown: 14.28%

## Trade outcomes
- Total trades: **705**
- Hit TARGET: **409**   ·   Hit STOP: **276**   ·   Rotated out: 0   ·   Still open at end: 20
- Win rate: 57.2%   ·   Avg R: 0.17   ·   Profit factor: 1.39
- Expectancy / trade: Rs 1,600   ·   Avg holding: 32.4 days

## P&L detail
- Net P&L: Rs 1,127,736
- Gross profit: Rs 4,016,507   ·   Gross loss: Rs -2,888,771
- Avg win: Rs 9,967   ·   Avg loss: Rs -9,565
- Best trade: Rs 31,104   ·   Worst trade: Rs -26,034

## What the money-management rules did
- Rotations triggered: 0
- Signals skipped (no cash / no slot): 474
