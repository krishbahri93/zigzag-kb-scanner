# Owner's Playbook (for Krish — no code knowledge needed)

This is your one-page guide to the scanner system. It grows as we build.
Last updated: 2026-07-05 (Phase 0).

## What exists right now

- **The scanner app on your laptop:** double-click `start.bat` → a browser tab opens with the
  Scanner, Forward test (paper money), and Settings pages.
- **The strategy:** "Nested Swings V2" (long-only, daily) — ported from your TradingView script
  and mathematically verified against the chart.
- **Your 5 TradingView scripts** are safely stored in the `New Scripts` folder in this project.

## What's coming (the master plan, in order)

1. The whole system moves to a small cloud computer in Mumbai — you'll open the dashboard from
   your phone anywhere, each person gets their own login, and the Dhan token renews itself every
   morning. Your daily involvement drops to zero.
2. The dashboard gets the professional look: cards, sorting, Copy-for-TradingView, chart links.
3. Live scanning through the market day (9:15 AM – 3:45 PM).
4. Telegram pings: "trading above entry (temporary)" and "closed above entry (confirmed)".
5. The Short strategy goes live with a Long/Short toggle.
6. Paper-money results by week / month / year + star ratings for trades.
7. Then: US market, news-on-demand, and the intraday versions.

## If something looks wrong

| What you see | What to do |
|---|---|
| App won't open on the laptop | Close the black window, double-click `start.bat` again. |
| Data looks old | Click **Refresh data** in the app and wait. |
| Anything else, or you're unsure | Just tell Claude what you see, in plain words. Screenshots help. |

*(Once we're on the cloud server in Phase 1, this table gets one more line: "Dashboard down →
press the Reboot button" — with a link.)*

## Things you'll be asked to do (only when we reach that phase)

- **Phase 1:** create the AWS account, buy the domain (~₹850/yr), enable TOTP on your Dhan
  profile, and type your three Dhan secrets into the app's Settings page. All guided click-by-click.
- **Phase 4:** create a Telegram bot (~5 minutes, guided).
- **Phases 5 & 9:** export chart data files from TradingView when asked (guided).

## House rules (how we work)

- Changes are always built on a side branch and shown to you before they touch the live system.
- Your keys and PINs are never put into git, chat, or email — you type them only into your own
  dashboard's Settings page.
- Nothing here is financial advice; the scanner is an information tool and trades are your call.
