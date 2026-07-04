# KB Fib System — Master Folder

**Owner:** KB (krishbahri) · **Compiled:** June 2026 · **Market:** NSE Indian equities

This folder is the single source of truth for the KB Fibonacci golden-ratio reversal trading
system: the published TradingView indicator, the Python scanning engine, the web dashboard, and
the deployment plumbing that ties them together.

---

## What this system is, in one paragraph

A single A→B price down-swing is turned into **two sequential trades**. The same Fibonacci
levels that define the first trade's take-profit also define the second trade's entry, so one
clean swing produces a layered T1 → T2 structure. The **TradingView indicator** draws and tracks
this live on a chart for manual execution. The **Python engine** ports the same geometry to scan
the whole Nifty 500 and flag which names are Approaching / In Zone / Triggered. The **dashboard**
reads the engine's output and presents it as a screener. Everything keys off the same golden-zone
math so the chart and the screener never disagree.

---

## Folder map

| Folder | What's inside | Start with |
|--------|---------------|------------|
| `01_Indicator/` | The published Pine Script indicator: link, spec, full rule set | `INDICATOR_SUMMARY.md` |
| `02_Engine_Backend/` | The Python scanner (`kwm_engine.py`), runner, and rebuild spec | `ENGINE_REBUILD_GUIDE.md` |
| `03_Dashboard_Frontend/` | The React/HTML dashboard and its rebuild spec | `DASHBOARD_REBUILD_GUIDE.md` |
| `04_Deployment_GitHub_Netlify/` | GitHub Actions workflow, Netlify hosting, data flow | `DEPLOYMENT_GUIDE.md` |
| `05_Documentation/` | Cross-cutting docs: full rules, trade thesis, glossary, roadmap | `KB_FIB_RULES_MASTER.md` |
| `06_Colab/` | The Google Colab notebook for running scans interactively | the `.ipynb` |

Every written doc is provided in **both** `.md` (editable) and `.docx` (shareable) form.

---

## The three things you asked to be able to do

1. **Find everything in one place** — links, code, parameters, all collected here.
2. **Rebuild the dashboard + engine from scratch** — see the two `*_REBUILD_GUIDE` docs, which
   carry both the working code and a from-zero spec so a fresh build matches the original exactly.
3. **Reflect on and improve the rules** — see `05_Documentation/KB_FIB_RULES_MASTER.md`, which
   states every rule explicitly and ends with an open "Questions to pressure-test" section.

---

## Live links

- **Indicator (TradingView):** https://in.tradingview.com/script/s0BdSUIs-ZigZag-KB-Fib-Dual-Trade/
- **Data feed (GitHub raw):** `https://raw.githubusercontent.com/krishbahri93/kwm-scan/main/results.json`
- **Dashboard host:** Netlify (see `04_Deployment_GitHub_Netlify/DEPLOYMENT_GUIDE.md`)

---

## Important note on naming

The system is referred to two ways across the files, and both mean the same thing:

- **"KB Fib" / "ZigZag KB Fib Dual Trade"** — the TradingView indicator (the published, current version).
- **"KWM" / "KWM Auto Screener"** — the Python engine + dashboard that scan for the same setups.

They share one geometry. Where an older doc says "v10.2 / v11.0 / A1-A2-A3 queue," that describes an
**earlier single-trade lineage** of the indicator. The **current published indicator** uses the
**dual-trade (T1 → T2)** model described throughout this folder. See
`05_Documentation/VERSION_HISTORY.md` for how the two relate.

---

## Disclaimer

This system is an educational and informational tool. Its operator is **not a SEBI-registered
investment adviser**, and nothing here is investment advice or a recommendation to buy, sell, or
hold any security. All outputs are automatically generated technical signals that may be
inaccurate, delayed, or incomplete. Trading carries substantial risk of loss; past performance
does not indicate future results. Do your own due diligence.
