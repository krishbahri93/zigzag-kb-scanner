# Deployment Guide — GitHub Actions + Netlify

How the pieces connect in production: a scheduled GitHub Action runs the scan and commits a fresh
`results.json`; the Netlify-hosted dashboard fetches that file. This doc covers the wiring, the
secrets, and the known console noise.

---

## The data flow

```
GitHub Actions (scan.yml, every ~5 min, NSE hours, Mon-Fri)
        │  runs run_scan.py  (KWM_DATA_SOURCE=dhan)
        ▼
   results.json   ──commit & push──►  GitHub repo (krishbahri93/kwm-scan, main)
        │
        │  served raw at raw.githubusercontent.com/.../results.json
        ▼
   Netlify-hosted dashboard  ──fetch every 90s──►  renders the screener
```

Two independent clocks: the **scan** refreshes the data file roughly every 5 minutes; the
**dashboard** polls that file every 90 seconds. They don't need to be in sync.

---

## Part A — GitHub Actions (the scan robot)

The workflow lives in `scan.yml` (in this folder; in the repo it belongs at
`.github/workflows/scan.yml`).

**What it does:** checks out the repo, sets up Python 3.11, installs deps
(`yfinance pandas numpy requests dhanhq`), runs `run_scan.py` with Dhan as the data source, then
commits and pushes `results.json` back to the repo.

**Schedule:** `cron: "*/5 3-10 * * 1-5"` — every 5 minutes, 03:00–10:00 UTC (≈ NSE 08:30–15:30 IST),
Monday–Friday. Also has `workflow_dispatch` so you can trigger it manually. GitHub's cron timing is
best-effort, so expect occasional drift.

**Secrets required** (repo → Settings → Secrets and variables → Actions):
- `DHAN_CLIENT_ID`
- `DHAN_ACCESS_TOKEN`

**Permissions:** the job needs `contents: write` (already set) so it can push the updated file.

**The token gotcha:** Dhan access tokens expire ~24h. When the scan starts producing empty or stale
results, regenerate the token in Dhan and update the `DHAN_ACCESS_TOKEN` secret. This is the single
most common cause of a "frozen" dashboard.

### Repo layout the action expects

```
kwm-scan/
├── .github/workflows/scan.yml
├── kwm_engine.py
├── run_scan.py
└── results.json        ← created/updated by the action
```

---

## Part B — Netlify (the dashboard host)

The dashboard is a single static `KWM_Auto_Screener.html`. Netlify serves it as-is — no build
command needed (it's CDN-React, no bundler).

**Project name:** `zigzag-kb-scanner` (visible in the Netlify URL).

**Deploy options:**
1. **Drag-and-drop:** drop the `.html` (renamed `index.html`) into Netlify's deploy zone. Fastest.
2. **Git-connected:** point Netlify at a repo containing `index.html`; it redeploys on push. Set
   build command to empty and publish directory to the folder containing the file.

**No environment variables needed on Netlify** — the dashboard reads data from the public GitHub raw
URL, not from any Netlify backend.

---

## Part C — Reading the browser console (what's noise vs real)

The captured console errors are almost entirely **Netlify's own dashboard UI**, not your screener:

- `secure.gravatar.com/avatar/... 404` — Netlify app avatars; harmless.
- `cnm-sw.js` / service-worker `Failed to fetch` / "Response with null body" — Netlify's service
  worker; harmless to your app.
- `grsm.io ... ERR_BLOCKED_BY_CLIENT` — a monitoring script blocked by an ad-blocker; harmless.

**What would be a real problem** (watch for these instead):
- A failed fetch of **your** `results.json` URL → check the file exists at the raw URL and the repo
  is public.
- A CORS error on the `results.json` request → GitHub raw is CORS-open, so this usually means a
  wrong/typo'd URL.
- JSX/Babel parse errors referencing the `text/babel` script → a syntax issue in the dashboard file
  itself.

Rule of thumb: if the erroring URL isn't your `results.json` or your HTML file, it's environment
noise, not a bug in the screener.

---

## Quick redeploy checklist

1. Engine changed? Push `kwm_engine.py` / `run_scan.py` to `kwm-scan`; the next cron run picks it up.
2. Dashboard changed? Re-drop `index.html` on Netlify (or push if git-connected).
3. Data frozen? Check (a) the Action's latest run succeeded, (b) the Dhan token isn't expired.
4. Want to force-refresh data? Trigger the workflow manually via `workflow_dispatch`.
