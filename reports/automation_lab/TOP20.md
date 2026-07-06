# Automation Lab — leaderboard

_Data through 2026-07-03 · train = history->2024-12-31 · validate = 2025-01-01->2026-07-03 · capital Rs 20L · gate: DD <= 15% and profitable in BOTH windows · 567 combos in 37.5 min_

## Baselines (the bot with no judgment, and Krish encoded)

| # | id | combo | val CAGR% | val DD% | val PF | val trades | train CAGR% | train DD% | pass |
|---|----|-------|-----------|---------|--------|------------|-------------|-----------|------|
| 1 | BASE_raw_v21 | no entry filter · V2 natural exits · 3:20 close entry | 7.3 | 17.2 | 1.17 | 149 | 16.4 | 19.1 | no |
| 2 | BASE_krish_manual | close in top 40% of range; green candle only; volume > previous day; remaining R:R >= 1.0 · early target at 70% of run · 3:20 close entry | 6.2 | 12.9 | 1.16 | 131 | 17.4 | 8.5 | YES |

## Top 20 of the sweep (390 of 567 passed the gate)

| # | id | combo | val CAGR% | val DD% | val PF | val trades | train CAGR% | train DD% | pass |
|---|----|-------|-----------|---------|--------|------------|-------------|-----------|------|
| 1 | B103 | close in top 40% of range; green candle only; remaining R:R >= 1.0 · early target at 70% of run · 3:20 close entry | 16.6 | 9.6 | 1.45 | 151 | 17.6 | 10.1 | YES |
| 2 | B106 | close in top 40% of range; green candle only; remaining R:R >= 1.0 · early target at 70% of run; breakeven after 1.0R · 3:20 close entry | 16.6 | 9.6 | 1.45 | 151 | 17.6 | 10.1 | YES |
| 3 | B126 | close in top 40% of range; green candle only; volume > 1.2x 20-day avg; remaining R:R >= 1.0 · early target at 70% of run · 3:20 close entry | 16.6 | 9.6 | 1.45 | 151 | 17.6 | 10.1 | YES |
| 4 | B129 | close in top 40% of range; green candle only; volume > 1.2x 20-day avg; remaining R:R >= 1.0 · early target at 70% of run; breakeven after 1.0R · 3:20 close entry | 16.6 | 9.6 | 1.45 | 151 | 17.6 | 10.1 | YES |
| 5 | C000 | close in top 40% of range; green candle only; remaining R:R >= 1.0 · early target at 70% of run · 3:20 close entry · size 10% of equity | 16.6 | 9.6 | 1.45 | 151 | 17.6 | 10.1 | YES |
| 6 | C003 | close in top 40% of range; green candle only; remaining R:R >= 1.0 · early target at 70% of run; breakeven after 1.0R · 3:20 close entry · size 10% of equity | 16.6 | 9.6 | 1.45 | 151 | 17.6 | 10.1 | YES |
| 7 | C006 | close in top 40% of range; green candle only; volume > 1.2x 20-day avg; remaining R:R >= 1.0 · early target at 70% of run · 3:20 close entry · size 10% of equity | 16.6 | 9.6 | 1.45 | 151 | 17.6 | 10.1 | YES |
| 8 | C009 | close in top 40% of range; green candle only; volume > 1.2x 20-day avg; remaining R:R >= 1.0 · early target at 70% of run; breakeven after 1.0R · 3:20 close entry · size 10% of equity | 16.6 | 9.6 | 1.45 | 151 | 17.6 | 10.1 | YES |
| 9 | B034 | close in top 40% of range; remaining R:R >= 0.75 · early target at 70% of run · 3:20 close entry | 16.5 | 9.1 | 1.42 | 163 | 19.1 | 8.6 | YES |
| 10 | B037 | close in top 40% of range; remaining R:R >= 0.75 · early target at 70% of run; breakeven after 1.0R · 3:20 close entry | 16.5 | 9.1 | 1.42 | 163 | 19.1 | 8.6 | YES |
| 11 | B057 | close in top 40% of range; volume > 1.2x 20-day avg; remaining R:R >= 0.75 · early target at 70% of run · 3:20 close entry | 16.5 | 9.1 | 1.42 | 163 | 19.1 | 8.6 | YES |
| 12 | B060 | close in top 40% of range; volume > 1.2x 20-day avg; remaining R:R >= 0.75 · early target at 70% of run; breakeven after 1.0R · 3:20 close entry | 16.5 | 9.1 | 1.42 | 163 | 19.1 | 8.6 | YES |
| 13 | C012 | close in top 40% of range; remaining R:R >= 0.75 · early target at 70% of run · 3:20 close entry · size 10% of equity | 16.5 | 9.1 | 1.42 | 163 | 19.1 | 8.6 | YES |
| 14 | C015 | close in top 40% of range; remaining R:R >= 0.75 · early target at 70% of run; breakeven after 1.0R · 3:20 close entry · size 10% of equity | 16.5 | 9.1 | 1.42 | 163 | 19.1 | 8.6 | YES |
| 15 | C018 | close in top 40% of range; volume > 1.2x 20-day avg; remaining R:R >= 0.75 · early target at 70% of run · 3:20 close entry · size 10% of equity | 16.5 | 9.1 | 1.42 | 163 | 19.1 | 8.6 | YES |
| 16 | C021 | close in top 40% of range; volume > 1.2x 20-day avg; remaining R:R >= 0.75 · early target at 70% of run; breakeven after 1.0R · 3:20 close entry · size 10% of equity | 16.5 | 9.1 | 1.42 | 163 | 19.1 | 8.6 | YES |
| 17 | B201 | remaining R:R >= 1.5 · early target at 80% of run · 3:20 close entry | 16.4 | 5.7 | 2.07 | 67 | 8.2 | 5.4 | YES |
| 18 | B204 | remaining R:R >= 1.5 · early target at 80% of run; breakeven after 1.0R · 3:20 close entry | 16.4 | 5.7 | 2.07 | 67 | 8.0 | 5.4 | YES |
| 19 | B224 | volume > 1.2x 20-day avg; remaining R:R >= 1.5 · early target at 80% of run · 3:20 close entry | 16.4 | 5.7 | 2.07 | 67 | 8.2 | 5.4 | YES |
| 20 | B227 | volume > 1.2x 20-day avg; remaining R:R >= 1.5 · early target at 80% of run; breakeven after 1.0R · 3:20 close entry | 16.4 | 5.7 | 2.07 | 67 | 8.0 | 5.4 | YES |

## Top 5 ignoring the drawdown gate (for reference only)

| # | id | combo | val CAGR% | val DD% | val PF | val trades | train CAGR% | train DD% | pass |
|---|----|-------|-----------|---------|--------|------------|-------------|-----------|------|
| 1 | B103 | close in top 40% of range; green candle only; remaining R:R >= 1.0 · early target at 70% of run · 3:20 close entry | 16.6 | 9.6 | 1.45 | 151 | 17.6 | 10.1 | YES |
| 2 | B106 | close in top 40% of range; green candle only; remaining R:R >= 1.0 · early target at 70% of run; breakeven after 1.0R · 3:20 close entry | 16.6 | 9.6 | 1.45 | 151 | 17.6 | 10.1 | YES |
| 3 | B126 | close in top 40% of range; green candle only; volume > 1.2x 20-day avg; remaining R:R >= 1.0 · early target at 70% of run · 3:20 close entry | 16.6 | 9.6 | 1.45 | 151 | 17.6 | 10.1 | YES |
| 4 | B129 | close in top 40% of range; green candle only; volume > 1.2x 20-day avg; remaining R:R >= 1.0 · early target at 70% of run; breakeven after 1.0R · 3:20 close entry | 16.6 | 9.6 | 1.45 | 151 | 17.6 | 10.1 | YES |
| 5 | C000 | close in top 40% of range; green candle only; remaining R:R >= 1.0 · early target at 70% of run · 3:20 close entry · size 10% of equity | 16.6 | 9.6 | 1.45 | 151 | 17.6 | 10.1 | YES |
