# Colab — How to Run the Scanner Interactively

The notebook `KWM_Auto_Screener.ipynb` (in this folder) runs the same engine as the GitHub Action,
but interactively, so you can scan on demand and download the results. Press ▶ on each cell, top to
bottom.

---

## The cells, in order

1. **Step 1 — setup:** installs `yfinance pandas numpy requests dhanhq`. Run once per session.

2. **Step 1b — turn on Dhan real-time (optional):** reads two Colab Secrets (🔑 in the left sidebar),
   `DHAN_CLIENT_ID` and `DHAN_ACCESS_TOKEN`, and sets `KWM_DATA_SOURCE=dhan`. **Skip this cell** to
   use free Yahoo data (~15-min delayed) instead.

3. **Step 2 — the engine:** the entire `kwm_engine.py` pasted inline. Just run it; it defines all the
   functions. (Wall of code — ignore it.)

4. **Step 3 — universe + timeframes:** `load_nifty500()` pulls the full live Nifty 500;
   `TIMEFRAMES = ["1D","1H","15m"]`. There's a commented line to run just 8 names for a quick test —
   uncomment it (keep it flush-left) to shorten the run.

5. **Step 4 — run the scan:** runs `scan(...)`, sorts, writes `results.json`, also saves
   `kwm_scan.csv` and `kwm_watchlist.txt`, and tries to auto-download `results.json`. An 8-name test
   takes ~1 min; the full Nifty 500 × 3 timeframes takes ~10–15 min — be patient.

---

## Getting the data into the dashboard

After Step 4, download `results.json` (auto-download, or use the Files panel on the left). Then
either:
- **Upload it** into the dashboard via its file input, or
- **Commit it** to the `kwm-scan` repo so the live dashboard picks it up from the raw URL.

---

## Notes

- **Token expiry:** the Dhan access token expires ~24h. Regenerate it in Dhan and update the Colab
  Secret when scans start failing or returning stale data.
- **Free vs real-time:** Yahoo is fine for end-of-day daily scans; use Dhan when you need
  intraday/real-time freshness.
- **Reproducibility:** the notebook and the GitHub Action call the *same* engine functions, so a
  notebook scan and a scheduled scan with the same data source and universe produce the same rows.
