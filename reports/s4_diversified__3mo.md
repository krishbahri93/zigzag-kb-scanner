# s4_diversified  —  3mo timeframe

_Window: 2026-03-25 -> 2026-06-25  ·  starting capital Rs 2,000,000_

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
- Capital: Rs 2,000,000  ->  **Rs 2,189,831**
- Total return: **+9.49%**   ·   CAGR: +43.33%
- Max drawdown: 6.19%

## Trade outcomes
- Total trades: **71**
- Hit TARGET: **38**   ·   Hit STOP: **13**   ·   Rotated out: 0   ·   Still open at end: 20
- Win rate: 63.4%   ·   Avg R: 0.31   ·   Profit factor: 1.93
- Expectancy / trade: Rs 2,644   ·   Avg holding: 21.4 days

## P&L detail
- Net P&L: Rs 187,731
- Gross profit: Rs 389,834   ·   Gross loss: Rs -202,103
- Avg win: Rs 8,663   ·   Avg loss: Rs -7,773
- Best trade: Rs 24,230   ·   Worst trade: Rs -13,700

## What the money-management rules did
- Rotations triggered: 0
- Signals skipped (no cash / no slot): 103
