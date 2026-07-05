# AGENTS.md — runbook for AI agents working on this repo

Read this first. It is the single source of truth for how agents work here.
Update it at the end of every phase (that update is part of the phase's definition of done).

## What this is

A TradingView Pine-Script strategy ("ZigZag KB Nested Swings") ported to Python and run as a
stock scanner over NSE Nifty 500 (India) and US equities, with a FastAPI dashboard, a paper-money
forward test, and a policy backtester. The owner (Krish) understands markets, not code — all code
is written and maintained by AI agents, and every design choice should favor agent maintainability
(machine-readable state, one-command verbs, tests as gates) over human aesthetics.

## Master plan / phase status

The phased master plan lives with the owner's Claude Code sessions
(`~/.claude/plans/hi-claude-parallel-parrot.md`). Summary of phases and status:

| Phase | Deliverable | Status |
|---|---|---|
| 0 | Housekeeping: Pine sources committed, AGENTS.md + OWNER.md seeded | done (2026-07-05) |
| 1 | Hosting: AWS Lightsail Mumbai, HTTPS + per-user auth, systemd timers, auto Dhan token, watchdogs | next |
| 2 | Rich dashboard merged into the FastAPI app | pending |
| 3 | Market-hours scanning 09:15–15:45 IST, provisional/confirmed states | pending |
| 4 | Telegram alerts | pending |
| 5 | Short daily strategy port (parity-gated) + Long/Short toggle | pending |
| 6 | Forward-test weekly/monthly/yearly views + trade rating | pending |
| 7 | US market rollout | pending |
| 8 | News on demand (Google News RSS, fetch-on-click) | pending |
| 9 | Intraday 5m/15m strategies (long + short) | pending |

## Repo map

- `pinescan/` — the Python package
  - `core/` — Pine→Python toolkit: `runtime.py` (Pine builtins), `tv_zigzag.py`, `lint.py`, `parity.py`
  - `nsv2_engine.py` / `nsv2_scanner.py` — the one ported strategy (long-only, daily)
  - `scanners/registry.py` — plugin registry; a new ported strategy self-registers and
    auto-appears in the app and forward test (template: `scanners/nsv2.py`)
  - `markets/` — data layers: `us.py` (Polygon EOD), `india.py` (Dhan; Nifty 500 + sectors)
  - `backtest/` — day-by-day portfolio simulator, rules registry, JSON policies, metrics
  - `service.py` — orchestration facade (scan, refresh, forward standings, key storage)
- `app/` — FastAPI + Jinja2 local web app (scanner / forward / settings pages), `jobs.py` =
  single-flight background jobs
- `scripts/` — CLI entry points: `scan.py`, `forward_run.py`, `refresh_data.py`,
  `refresh_dhan_token.py` (headless daily Dhan token via TOTP), `setup_schedule.ps1` (Windows-era
  scheduling; superseded by systemd in Phase 1)
- `New Scripts/` — the 5 Pine sources = strategy source-of-truth (only NSV2 is ported so far)
- `pine/` — instrumented Pine + ZigZag library source used for the NSV2 parity work
- `fixtures/` — golden parity data (`nsv2_golden.json`, 24 parity CSVs). Never regenerate casually.
- `docs/` — `PINE_PORTING.md` (the porting/parity pipeline — read before any port),
  `PLAN.md` (original architecture plan), `OWNER.md` (owner's plain-English playbook)
- `index.html` — the OLD cloud dashboard (rich UI, dead data feed). Being merged into `app/` in
  Phase 2; treat as reference material, do not extend it in place.

## One-command verbs

- Tests: `python -m pytest tests/ -q`
- Pine lint: `python -m pinescan.core lint <file.pine>`
- Parity gate: `python -m pinescan.core parity --csv <golden.csv> --port <module>:run`
- Local app: `start.bat` (Windows) → http://127.0.0.1:8000
- Deploy: `scripts/deploy.sh` — DOES NOT EXIST YET (Phase 1). Until then there is no server.

## Hard invariants

1. **Never commit secrets.** `.polygon_key`, `.dhan_creds` (contains Dhan PIN + TOTP seed) are
   git-ignored and must stay that way. The repo is currently PUBLIC. Collaborators: the owner
   (krishbahri93) and his infra partner (MammenK) — coordinate, don't clobber.
2. **Never delete `data/forward/`** — the paper-trading track record is not regenerable.
3. **Never commit directly to `main`.** Branch per phase/change; the owner approves merges and
   pushes. Do not push/merge/delete branches without his explicit OK.
4. **A strategy port is only "done" when the bar-for-bar parity gate is green** against a
   TradingView-exported golden CSV (see `docs/PINE_PORTING.md`). No exceptions; code review and
   unit tests are not proof.
5. **The owner is non-technical.** Anything he must do gets click-by-click instructions; anything
   that can be automated instead, automate.

## Working style per phase

Plan → discuss with owner → execute on a branch → verify (tests + phase's Done-when) →
owner approves → merge → agent-optimize (update this file + OWNER.md) → next phase.
