# Automation Lab — combined long+short book (Rs 20L clubbed)

_Data through 2026-07-03 · rule spec both sides = the long winner (candle top-40%, confirming candle, R:R >= 1, early target 70%) · only the CAPITAL MANAGEMENT varies · gate: DD <= 15% + profitable in both windows._

SHORT REALISM: shorts modelled at full-notional margin on the whole NSE universe;
real overnight shorts need stock futures (F&O names, lots, ~20-25% margin). Treat
short P&L as a structure signal, not a bankable number, until the F&O pass.

| # | scheme | sizing | val CAGR% | val DD% | val PF | val trades | L pnl (val) | S pnl (val) | train CAGR% | train DD% | pass |
|---|--------|--------|-----------|---------|--------|------------|-------------|-------------|-------------|-----------|------|
| 1 | REF_long_only | fixed2L | 16.6 | 9.6 | 1.45 | 151 | +5.2L | +0.0L | 17.6 | 10.1 | YES |
| 2 | REF_short_only | fixed2L | -6.3 | 24.8 | 0.81 | 81 | +0.0L | -1.9L | -6.3 | 37.0 | no |
| 3 | 8 long / 2 short | pctEq10 | 14.7 | 7.2 | 1.33 | 149 | +5.2L | -0.7L | 17.1 | 9.2 | YES |
| 4 | 7 long / 3 short | pctEq10 | 14.0 | 5.8 | 1.32 | 148 | +4.6L | -0.3L | 14.0 | 8.9 | YES |
| 5 | 8 long / 2 short | fixed2L | 13.4 | 5.8 | 1.35 | 146 | +4.9L | -0.8L | 14.2 | 8.7 | YES |
| 6 | 7 long / 3 short | fixed2L | 13.1 | 5.0 | 1.33 | 148 | +4.4L | -0.3L | 12.1 | 7.7 | YES |
| 7 | shared pool | fixed2L | 7.4 | 9.6 | 1.17 | 140 | +1.5L | +0.8L | 9.5 | 10.1 | YES |
| 8 | 6 long / 4 short | fixed2L | 6.9 | 5.3 | 1.16 | 143 | +2.0L | +0.1L | 11.4 | 6.2 | YES |
| 9 | 5 long / 5 short | pctEq10 | 2.9 | 9.3 | 1.06 | 142 | +1.0L | -0.1L | 10.6 | 9.6 | YES |
| 10 | 6 long / 4 short | pctEq10 | 2.9 | 8.7 | 1.06 | 141 | +0.7L | +0.1L | 15.3 | 7.2 | YES |
| 11 | 5 long / 5 short | fixed2L | 1.7 | 8.4 | 1.04 | 142 | +0.2L | +0.3L | 9.2 | 7.0 | YES |
| 12 | shared pool | pctEq10 | 1.7 | 10.0 | 1.03 | 131 | +0.2L | +0.3L | 10.7 | 12.2 | YES |

**Best gated scheme: 8 long / 2 short · pctEq10** — validate CAGR 14.7% at 7.2% DD (train 17.1% at 9.2%).

Winner's calendar years (validate window): 2025: +16.1%  2026: +5.8%
