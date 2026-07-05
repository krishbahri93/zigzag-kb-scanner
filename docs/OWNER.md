# Owner's Playbook (for Krish — no code knowledge needed)

This is your one-page guide to the scanner system. It grows as we build.
Last updated: 2026-07-05 (end of Phase 1 — the system is LIVE).

## The essentials

- **Your dashboard:** https://kwmscanner.com — works on phone, tablet, laptop, anywhere.
- **Logins:** krish, mammen, kinny, vishnu, kambdi (each person has their own password;
  ask Claude to change or remove any of them — takes seconds).
- **It runs itself:** 08:30 AM the Dhan token renews; 3:45 PM (Mon–Fri) prices refresh,
  the scan re-runs, and the paper-money standings update. A backup is taken nightly at 2 AM.
- **Your daily involvement: zero.** Open the site whenever you like.

## If something looks wrong

| What you see | What to do |
|---|---|
| Site won't load at all | Log into lightsail.aws.amazon.com → click **kwm-scanner** → press **Reboot**. Wait 2 minutes. Everything restarts and catches up by itself. |
| Data looks old | Click **Refresh data** in the top bar of the site and wait. |
| Login not accepted | Ask Claude to reset that person's password (seconds). |
| Anything else, or unsure | Tell Claude what you see, in plain words. Screenshots help. |

## What's coming next (the master plan, in order)

2. **The beautiful dashboard** — your KWM Auto Screener design becomes the face of the live
   site: cards, filters, volume spikes, Copy-for-TradingView, chart links.
3. Live scanning through the market day (9:15 AM – 3:45 PM).
4. Telegram pings (temporary vs confirmed entries).
5. The Short strategy + Long/Short toggle.
6. Paper-money results by week / month / year + star ratings.
7. US market · 8. News-on-demand · 9. Intraday versions.

## Things only you can do (when we reach them)

- **Now (3 min):** create the free watchdog account (healthchecks.io) — Claude gives the steps.
- **Phase 4:** create a Telegram bot (~5 min, guided).
- **Phases 5 & 9:** export chart data from TradingView when asked (guided).

## House rules (how we work)

- Changes are built on a side branch, shown to you, and only then go live — via a deploy
  system that tests itself and automatically rolls back if anything's wrong.
- Your keys and PINs are never in git, chat, or email — you type them only into your own
  dashboard's Settings page, and the site never displays them back to anyone.
- Nothing here is financial advice; the scanner is an information tool and trades are your call.
