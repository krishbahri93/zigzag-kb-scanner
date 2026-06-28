# s4_diversified  —  6wk timeframe

_Window: 2026-05-13 -> 2026-06-24  ·  starting capital $20,000_

## Strategy (plain English — generated from the rules that ran)
```
Policy: s4_diversified — "Maximum diversification: many small bets - up to 20 positions of $1k each, held to exit. Wide spread smooths the ride but dilutes each winner."
├── Capital: $20,000 · max 20 positions
├── Sizing: fixed_amount — "Allocate a fixed $1000 per trade."
├── Selection: free_capital_first — "Consider every fresh signal; cash and the position cap gate it downstream."
├── Rotation: none — "No rotation — never sell to fund a new entry."
└── Exit: scanner_default — "Exit on V2's own target or stop; no extra exit."
```

## Headline
- Capital: $20,000  ->  **$19,348**
- Total return: **-3.26%**   ·   CAGR: -25.03%
- Max drawdown: 10.96%

## Trade outcomes
- Total trades: **70**
- Hit TARGET: **37**   ·   Hit STOP: **15**   ·   Rotated out: 0   ·   Still open at end: 18
- Win rate: 47.1%   ·   Avg R: 0.09   ·   Profit factor: 0.83
- Expectancy / trade: $-9   ·   Avg holding: 7.8 days

## P&L detail
- Net P&L: $-661
- Gross profit: $3,123   ·   Gross loss: $-3,784
- Avg win: $95   ·   Avg loss: $-102
- Best trade: $223   ·   Worst trade: $-739

## What the money-management rules did
- Rotations triggered: 0
- Signals skipped (no cash / no slot): 19
