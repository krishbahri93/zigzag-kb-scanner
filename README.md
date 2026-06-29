# ZigZag Scanner — local app

A small app you run **on your own Windows laptop** to see the strategy's stock recommendations
(the **Scanner**) and how the strategies are doing on paper money (the **Forward test**). Nothing is
sent anywhere — it all runs locally, and your API key stays on your computer.

> You do **not** need to know anything about programming. Follow the steps below in order.

---

## 1. One-time setup (≈10 minutes, once)

**A. Install Python** (the language the app runs on):
1. Go to **https://www.python.org/downloads/** and click the big yellow **Download Python** button.
2. Run the file you downloaded.
3. **VERY IMPORTANT:** on the first screen, **tick the box that says "Add Python to PATH"**, then
   click **Install Now**. (If you miss this box, the app can't start — just re-run the installer.)

**B. Get the project folder:**
- You'll be given a folder (e.g. a ZIP file). **Unzip it** somewhere easy like your Desktop. Inside
  you should see a file called **`start.bat`**.

That's the whole setup. You won't repeat this.

---

## 2. Start the app

**Double-click `start.bat`.**

- **If Windows shows a blue "Windows protected your PC" box:** this is normal for a file Windows
  hasn't seen before — it is safe. Click the small **"More info"** link, then click the
  **"Run anyway"** button. (You only do this the first time.)
- A **black window** opens — this is the app running (it's called the "console"). The **first time
  only**, it spends a few minutes installing things and you'll see text scrolling — just leave it
  alone until it settles. After that, starting is quick.
- A **browser tab opens automatically** at `http://127.0.0.1:8000` — that tab *is* the app.
- **Keep the black window open** the whole time you use the app. **To stop the app, close that
  black window.**

> Tip: double-clicking `start.bat` again while it's already running just re-opens the browser tab —
> it won't start a second copy.

---

## 3. First use — add your key, then load data

1. In the app, click **Settings** (top-left).
2. Paste your **Polygon API key** into the box and click **Save keys**. *(How to get a free key is
   in section 6 below.)*
3. Click **Refresh data** (top bar).
   - **The first refresh downloads about 2 years of price history and can take 1–2 hours.** This is
     normal and only happens once. You can keep using your laptop; you can even close everything and
     come back later — it **continues where it left off**.
   - After that, daily refreshes take just a minute or two.
4. When it's done, open **Scanner** and **Forward test** — they'll be full of data.

---

## 4. Using the app

- **Scanner** — today's actionable setups: the tickers currently *in* or *near* their buy band, with
  the **entry band, target band, and stop**. These are the recommendations you'd place manually.
- **Forward test** — the 5 strategies paper-traded since a start date: their **return, win rate,
  open positions**, and how they compare to the market (S&P 500 / Nasdaq). This is the track record.
- **Top status bar** — always shows how fresh your data is, whether your keys are set, and what the
  app is doing right now. The **US / INDIA** links switch markets.

---

## 5. If a laptop shuts down (this is safe!)

The app is built so that **nothing breaks** if your laptop sleeps, shuts down, or loses power —
even in the middle of a download:
- Data files are written safely, so a shutdown can never leave a half-written/corrupt file.
- If the laptop is off for several days, the next **Refresh data** simply catches up the whole gap.
- **If anything ever looks wrong, just close the black window and double-click `start.bat` again.**
  That recovers it. (As a last resort, see Troubleshooting.)

---

## 6. Getting a free Polygon API key (for US stocks)

1. Go to **https://polygon.io/** and click **Sign up** (the free plan is enough).
2. After signing in, open the **Dashboard / API Keys** page and **copy your key** (a long string).
3. Paste it into the app's **Settings** page and click **Save keys**.

*(India/Dhan is optional and only needed if you want Indian stocks — paste your Dhan Client ID and
Access Token on Settings the same way. Without them, the app simply runs US-only.)*

---

## 7. Troubleshooting

| What you see | What to do |
|---|---|
| Blue **"Windows protected your PC"** box | Click **"More info"** then **"Run anyway"** — it's safe (just a new file Windows hasn't seen). |
| The black window closed, or shows red error text | Just **double-click `start.bat`** again. |
| Browser says "can't connect" | Wait ~5 seconds and **refresh** the page (the server is still starting). |
| "Python was not found" | Re-install Python from python.org and **tick "Add Python to PATH"**, then re-run `start.bat`. |
| Data looks old / pages say "no data yet" | Click **Refresh data** (top bar) and wait. |
| The very first refresh is slow | That's expected (downloading ~2 years of data). Leave it; closing/reopening continues it. |
| Pages won't load and re-running didn't help | Delete the **`venv`** folder next to `start.bat`, then double-click `start.bat` (it rebuilds). |
| It says the app is already running but no tab opened | Open your browser and go to **http://127.0.0.1:8000** |

Your data and keys live next to `start.bat` (in `data\`, `.polygon_key`, `.dhan_creds`) and are never
uploaded anywhere. Deleting `venv` is always safe (it only holds the installed program, not your data).

---

## 8. For developers — add a new scanner from a Pine script

The app is built around a **scanner registry**, so a new ported indicator shows up everywhere (the
Scanner page, the forward test, the selector) with no changes to the app:

1. **Port the Pine script to Python with the parity gate** (this is the careful part — see
   `PINE_PORTING.md` and the `pine-to-python` skill):
   - `python -m pinescan.core lint your_indicator.pine` — flags imports/traps + the series to verify.
   - Export a "golden" CSV from TradingView, then
     `python -m pinescan.core parity --csv golden.csv --port yourmodule:run` — must pass bar-for-bar.
2. **Register it:** add `pinescan/scanners/<name>.py` that builds a `Scanner(...)` (its `run`,
   `swing_levels`, `scan_symbol`, `default_params`, `min_bars`) and calls `register(...)`, then import
   it from `pinescan/scanners/__init__.py`. See `pinescan/scanners/nsv2.py` for the template.

That's it — it auto-appears in the Scanner page's selector and can be forward-tested.

Run the tests any time with `python -m pytest tests/ -q`.

---

## Disclaimer

This tool is for **informational and educational purposes only**. It is **not financial advice**.
The recommendations are generated by an algorithm and may be wrong. You place any trades yourself, at
your own risk. Past or simulated performance does not guarantee future results.
