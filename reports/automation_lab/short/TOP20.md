# Automation Lab — leaderboard (SHORT side)

_Data through 2026-07-03 · train = history->2024-12-31 · validate = 2025-01-01->2026-07-03 · capital Rs 20L · gate: DD <= 15% and profitable in BOTH windows · 567 combos in 41.3 min_

## Baselines (the bot with no judgment, and Krish encoded)

| # | id | combo | val CAGR% | val DD% | val PF | val trades | train CAGR% | train DD% | pass |
|---|----|-------|-----------|---------|--------|------------|-------------|-----------|------|
| 1 | BASE_raw_v21 | no entry filter · V2 natural exits · 3:20 close entry | -2.4 | 23.2 | 0.93 | 95 | -15.6 | 55.9 | no |
| 2 | BASE_krish_manual | close in top 40% of range; green candle only; volume > previous day; remaining R:R >= 1.0 · early target at 70% of run · 3:20 close entry | -7.6 | 24.0 | 0.78 | 84 | -8.2 | 42.5 | no |

## Top 20 of the sweep (0 of 567 passed the gate)

| # | id | combo | val CAGR% | val DD% | val PF | val trades | train CAGR% | train DD% | pass |
|---|----|-------|-----------|---------|--------|------------|-------------|-----------|------|
| 1 | C013 | close in top 30% of range; remaining R:R >= 0.75 · early target at 80% of run · next-day open entry · rotation on | 13.0 | 17.0 | 1.43 | 110 | -0.7 | 30.5 | no |
| 2 | C014 | close in top 30% of range; remaining R:R >= 0.75 · early target at 80% of run · next-day open entry · size 10% of equity · rotation on | 13.0 | 17.0 | 1.43 | 110 | -0.7 | 30.5 | no |
| 3 | C016 | close in top 30% of range; volume > 1.2x 20-day avg; remaining R:R >= 0.75 · early target at 80% of run · next-day open entry · rotation on | 13.0 | 17.0 | 1.43 | 110 | -0.7 | 30.5 | no |
| 4 | C017 | close in top 30% of range; volume > 1.2x 20-day avg; remaining R:R >= 0.75 · early target at 80% of run · next-day open entry · size 10% of equity · rotation on | 13.0 | 17.0 | 1.43 | 110 | -0.7 | 30.5 | no |
| 5 | C019 | close in top 30% of range; green candle only; remaining R:R >= 0.75 · early target at 80% of run · next-day open entry · rotation on | 13.0 | 17.0 | 1.43 | 110 | 0.9 | 30.5 | no |
| 6 | C020 | close in top 30% of range; green candle only; remaining R:R >= 0.75 · early target at 80% of run · next-day open entry · size 10% of equity · rotation on | 13.0 | 17.0 | 1.43 | 110 | 0.9 | 30.5 | no |
| 7 | C022 | close in top 30% of range; green candle only; volume > 1.2x 20-day avg; remaining R:R >= 0.75 · early target at 80% of run · next-day open entry · rotation on | 13.0 | 17.0 | 1.43 | 110 | 0.9 | 30.5 | no |
| 8 | C023 | close in top 30% of range; green candle only; volume > 1.2x 20-day avg; remaining R:R >= 0.75 · early target at 80% of run · next-day open entry · size 10% of equity · rotation on | 13.0 | 17.0 | 1.43 | 110 | 0.9 | 30.5 | no |
| 9 | C028 | close in top 30% of range; remaining R:R >= 0.75 · early target at 80% of run; breakeven after 1.0R · next-day open entry · rotation on | 10.9 | 17.8 | 1.34 | 110 | 0.8 | 29.9 | no |
| 10 | C029 | close in top 30% of range; remaining R:R >= 0.75 · early target at 80% of run; breakeven after 1.0R · next-day open entry · size 10% of equity · rotation on | 10.9 | 17.8 | 1.34 | 110 | 0.8 | 29.9 | no |
| 11 | A076 | close in top 50% of range; green candle only; remaining R:R >= 1.0 · V2 natural exits · 3:20 close entry | 10.1 | 18.7 | 1.44 | 70 | -8.4 | 41.4 | no |
| 12 | A092 | close in top 50% of range; green candle only; volume > 1.2x 20-day avg; remaining R:R >= 1.0 · V2 natural exits · 3:20 close entry | 10.1 | 18.7 | 1.44 | 70 | -8.4 | 41.4 | no |
| 13 | C000 | close in top 50% of range; green candle only; remaining R:R >= 1.0 · V2 natural exits · 3:20 close entry · size 10% of equity | 10.1 | 18.7 | 1.44 | 70 | -8.4 | 41.4 | no |
| 14 | C003 | close in top 50% of range; green candle only; volume > 1.2x 20-day avg; remaining R:R >= 1.0 · V2 natural exits · 3:20 close entry · size 10% of equity | 10.1 | 18.7 | 1.44 | 70 | -8.4 | 41.4 | no |
| 15 | A052 | close in top 50% of range; remaining R:R >= 1.0 · V2 natural exits · 3:20 close entry | 8.6 | 19.8 | 1.36 | 69 | -8.4 | 41.4 | no |
| 16 | A068 | close in top 50% of range; volume > 1.2x 20-day avg; remaining R:R >= 1.0 · V2 natural exits · 3:20 close entry | 8.6 | 19.8 | 1.36 | 69 | -8.4 | 41.4 | no |
| 17 | C006 | close in top 50% of range; remaining R:R >= 1.0 · V2 natural exits · 3:20 close entry · size 10% of equity | 8.6 | 19.8 | 1.36 | 69 | -8.4 | 41.4 | no |
| 18 | C009 | close in top 50% of range; volume > 1.2x 20-day avg; remaining R:R >= 1.0 · V2 natural exits · 3:20 close entry · size 10% of equity | 8.6 | 19.8 | 1.36 | 69 | -8.4 | 41.4 | no |
| 19 | B270 | close in top 30% of range; remaining R:R >= 0.75 · early target at 80% of run · next-day open entry | 7.2 | 18.4 | 1.24 | 94 | -1.8 | 33.8 | no |
| 20 | B293 | close in top 30% of range; volume > 1.2x 20-day avg; remaining R:R >= 0.75 · early target at 80% of run · next-day open entry | 7.2 | 18.4 | 1.24 | 94 | -1.8 | 33.8 | no |

## Top 5 ignoring the drawdown gate (for reference only)

| # | id | combo | val CAGR% | val DD% | val PF | val trades | train CAGR% | train DD% | pass |
|---|----|-------|-----------|---------|--------|------------|-------------|-----------|------|
| 1 | C013 | close in top 30% of range; remaining R:R >= 0.75 · early target at 80% of run · next-day open entry · rotation on | 13.0 | 17.0 | 1.43 | 110 | -0.7 | 30.5 | no |
| 2 | C014 | close in top 30% of range; remaining R:R >= 0.75 · early target at 80% of run · next-day open entry · size 10% of equity · rotation on | 13.0 | 17.0 | 1.43 | 110 | -0.7 | 30.5 | no |
| 3 | C016 | close in top 30% of range; volume > 1.2x 20-day avg; remaining R:R >= 0.75 · early target at 80% of run · next-day open entry · rotation on | 13.0 | 17.0 | 1.43 | 110 | -0.7 | 30.5 | no |
| 4 | C017 | close in top 30% of range; volume > 1.2x 20-day avg; remaining R:R >= 0.75 · early target at 80% of run · next-day open entry · size 10% of equity · rotation on | 13.0 | 17.0 | 1.43 | 110 | -0.7 | 30.5 | no |
| 5 | C019 | close in top 30% of range; green candle only; remaining R:R >= 0.75 · early target at 80% of run · next-day open entry · rotation on | 13.0 | 17.0 | 1.43 | 110 | 0.9 | 30.5 | no |
