"""
service.py — the one facade the CLIs AND the web app call (so neither duplicates orchestration).
================================================================================================

ROLE IN THE FLOW
  The scan, forward-test, refresh, and key-writing orchestration used to live inside the CLI
  `main()`s. It lives HERE now as plain functions returning plain data (dicts/lists), so:
    - scripts/scan.py and scripts/forward_run.py are thin CLIs over it, and
    - app/ (the web layer) calls the SAME functions — no logic is duplicated between CLI and web.

  Everything below reuses the validated pieces: the scanner registry (which scanner to run), the
  per-market data + benchmark wiring in pinescan.study, the backtest engine/metrics, and the
  markets' cache + key loaders. Writes go through io_safe (crash-safe).

WHAT EACH FUNCTION RETURNS (the UI/CLI contract)
  data_status(market)        -> {last_date, days_old, n_cached, keys:{polygon,dhan}}
  scan_market(market,sc)     -> the flat scan dict (engine, params, actionable, rows, ...) — same
                                shape scan.py wrote, so its JSON is byte-identical.
  forward_standings(market)  -> {meta, standings:[...], positions:{strat:[...]}, benchmark:[...]}
  refresh_market(market)     -> {ok, msg}   (gap-aware: backfills the whole gap since the last bar)
  write_polygon_key / write_dhan_creds       -> persist a user's key (atomic), reload it

HOW TO EXTEND
  Add a market by registering it in pinescan.study.MARKETS; add a scanner via pinescan.scanners.
  Both flow through here unchanged.
"""
import os
import glob
import json
import datetime as dt

import pandas as pd

from pinescan import io_safe, study
from pinescan.backtest.rules.registry import load_policy
from pinescan.backtest import engine, events, metrics
from pinescan.scanners import registry
from pinescan.markets import us, india

FORWARD_DIR = "data/forward"        # per-market forward state (git-ignored under data/)
WARM_MONTHS = 6                     # "warm" forward start seeds this many months of history
# The subset of engine params the scan surfaces (matches scan.py's original output exactly).
_SCAN_PARAM_KEYS = ("minDeclinePct", "pivotSensPct", "zigDepth", "maxSwings",
                    "minGapPct", "useEmaFilter", "useVolFilter")


# ===========================================================================
# data status (cheap — for the always-visible status strip)
# ===========================================================================
def _keys_present():
    """Whether each provider key is available (env OR a creds file) — WITHOUT loading/printing, so
    it's safe to call on every status poll."""
    poly = bool(os.environ.get("POLYGON_API_KEY") or os.path.exists(".polygon_key"))
    dhan = bool((os.environ.get("DHAN_CLIENT_ID") and os.environ.get("DHAN_ACCESS_TOKEN"))
                or os.path.exists(".dhan_creds"))
    return {"polygon": poly, "dhan": dhan}


def data_status(market):
    """Freshness of the market's cache + which keys are set. Cheap: reads filenames (US) or the
    newest parquet's last date (India), not the whole cache."""
    if market == "us":
        files = sorted(glob.glob(os.path.join(us.CACHE_DIR, "*.parquet")))
        last_date = os.path.splitext(os.path.basename(files[-1]))[0] if files else None
        n = len(files)
    else:
        files = glob.glob(os.path.join(india.CACHE_DIR, "*.parquet"))
        n = len(files)
        last_date = None
        if files:
            df = io_safe.read_parquet_safe(max(files, key=os.path.getmtime))
            if df is not None and len(df):
                last_date = str(df.index.max().date())
    days_old = (dt.date.today() - dt.date.fromisoformat(last_date)).days if last_date else None
    return {"last_date": last_date, "days_old": days_old, "n_cached": n, "keys": _keys_present()}


# ===========================================================================
# live scan (the actionable recommendations)
# ===========================================================================
def _universe_cache(market):
    """(symbols, {sym: df}) for SCANNING — the market's raw (untrimmed) cache, matching scan.py."""
    if market == "us":
        syms, _ = us.select_liquid_universe()
        return syms, us.load_cache(syms)
    syms = [os.path.splitext(os.path.basename(f))[0]
            for f in glob.glob(f"{india.CACHE_DIR}/*.parquet")]
    cache = india.load_cache(syms)
    cache = {s: df[~df.index.duplicated(keep="last")].sort_index()
             for s, df in cache.items() if df is not None}
    return syms, cache


def scan_market(market, scanner="nsv2"):
    """Run a scanner over a market's cached universe → the flat scan dict (same shape scan.py wrote).
    Reuses the registry scanner's scan_symbol + min_bars + default_params, so a new scanner works
    here with no change."""
    sc = registry.get(scanner)
    syms, cache = _universe_cache(market)
    rows, scanned, asof_dates = [], 0, set()
    for s in syms:
        df = cache.get(s)
        if df is None or len(df) < sc.min_bars:
            continue
        try:
            r = sc.scan_symbol(s, df, sc.default_params)
        except Exception:
            continue
        scanned += 1
        if r is not None:
            rows.append(r)
            asof_dates.add(r["asof"])
    rows.sort(key=lambda r: (not r["in_band"], not r["approaching"], -(r["n_swings"])))
    actionable = [r for r in rows if (r["in_band"] or r["approaching"] or r["fired_entry"])
                  and not r["expired"]]
    return {
        "engine": f"{sc.name} ({sc.display}, faithful port)",
        "generated_for_date": str(pd.Timestamp.now(tz="America/New_York").date()),
        "data_asof": max(asof_dates) if asof_dates else None,
        "params": {k: sc.default_params[k] for k in _SCAN_PARAM_KEYS if k in sc.default_params},
        "universe_size": len(syms),
        "scanned_ok": scanned,
        "setups_total": len(rows),
        "actionable_count": len(actionable),
        "actionable": [r["sym"] for r in actionable],
        "rows": rows,
    }


def _scan_path(market, scanner):
    return f"data/results/{scanner}_{market}.json"


def read_scan(market, scanner="nsv2"):
    """Read the CACHED scan JSON (written by Refresh / scan.py) — None if not generated yet. The web
    app serves this so a page load never re-scans the whole universe (which takes ~1 min)."""
    p = _scan_path(market, scanner)
    if not os.path.exists(p):
        return None
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return None


def read_forward(market):
    """Read the CACHED forward standings (written by forward_standings) — None if not generated yet.
    Served by the web app so a page load doesn't re-run the 5 backtests."""
    p = os.path.join(FORWARD_DIR, market, "standings.json")
    if not os.path.exists(p):
        return None
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return None


# ===========================================================================
# forward test (the paper-trading track record)
# ===========================================================================
def _state_path(market):
    return os.path.join(FORWARD_DIR, market, "state.json")


def _load_state(market):
    p = _state_path(market)
    if not os.path.exists(p):
        return None
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return None                          # corrupt state -> treat as first run (re-init), never crash


def _save_state(market, state):
    os.makedirs(os.path.dirname(_state_path(market)), exist_ok=True)
    io_safe.atomic_write_text(_state_path(market), json.dumps(state, indent=2))


def _resolve_start(start_arg, last):
    """--start -> a concrete (tz-aware) FORWARD_START, first init only. 'warm' seeds ~WARM_MONTHS
    back; 'today' starts empty; a YYYY-MM-DD string is localized to the cache's timezone."""
    last_ts = pd.Timestamp(last)
    if start_arg in (None, "warm"):
        return last_ts - pd.DateOffset(months=WARM_MONTHS)
    if start_arg == "today":
        return last_ts
    ws = pd.Timestamp(start_arg)
    if last_ts.tz is not None and ws.tz is None:
        ws = ws.tz_localize(last_ts.tz)
    return ws


def forward_standings(market, start_arg=None):
    """Replay the 5 policies from the locked FORWARD_START on the current cache and return the
    standings + open positions + benchmark as plain data. FORWARD_START is locked in state.json on
    the first call (warm by default); thereafter start_arg is ignored. Pure function of the cache —
    re-running is safe + deterministic. Returns None if the cache is empty (caller shows "refresh").
    """
    mkt = study.MARKETS[market]()
    cache = mkt.load_cache()
    cache = {s: df for s, df in cache.items() if df is not None and len(df) >= study.MIN_BARS}
    if not cache:
        return None
    last = max(df.index.max() for df in cache.values())
    last_date = str(pd.Timestamp(last).date())

    state = _load_state(market)
    if state is None:                        # first run: lock the start
        state = {"forward_start": str(_resolve_start(start_arg, last)), "last_run_date": last_date}
    ws = pd.Timestamp(state["forward_start"])

    all_trades = []
    for sym in sorted(cache):                # sorted -> deterministic
        all_trades += events.trades_for(sym, cache[sym])

    standings, positions = [], {}
    for strat in study.STRATEGIES:
        policy = load_policy(f"{mkt.policy_dir}/{strat}.json")
        result = engine.run_backtest(cache, policy, window_start=ws, trades=all_trades)
        m = result.metrics
        eq = result.equity_curve[-1][1] if result.equity_curve else policy.total_capital
        opens = [c for c in result.closed if c.outcome == "open_at_end"]      # currently-held book
        realized = [c for c in result.closed if c.outcome != "open_at_end"]   # truly closed trades
        rstats = metrics.summarize(result.equity_curve, realized, policy.total_capital, result.counters)
        wr = rstats["win_rate"]
        standings.append({"strategy": strat, "equity": eq, "return_pct": m["total_return_pct"],
                          "win_pct": None if wr is None else wr * 100.0, "pf": rstats["profit_factor"],
                          "n_open": len(opens), "n_closed": len(realized)})
        positions[strat] = [
            {"symbol": c.symbol, "entry": c.entry_price, "now": c.exit_price, "pnl": c.pnl,
             "days": (pd.Timestamp(c.exit_date) - pd.Timestamp(c.entry_date)).days, "swing": c.swing}
            for c in sorted(opens, key=lambda c: c.pnl, reverse=True)
        ]

    fwd_window = [("since_start", pd.Timestamp(last) - ws)]
    bench_raw = study.benchmark_returns(mkt.bench_series(last, fwd_window), last, fwd_window)
    benchmark = [{"name": name, "return_pct": rets.get("since_start")} for name, rets in bench_raw.items()]

    state["last_run_date"] = last_date
    _save_state(market, state)
    result = {
        "meta": {"title": mkt.title, "since": str(pd.Timestamp(ws).date()), "last": last_date,
                 "capital": mkt.capital_label, "currency": mkt.money_sym},
        "standings": standings, "positions": positions, "benchmark": benchmark,
    }
    # Cache the structured result so the web app's forward page serves it instantly (the CLI
    # forward_run renders its own markdown from the returned dict).
    io_safe.atomic_write_text(os.path.join(FORWARD_DIR, market, "standings.json"),
                              json.dumps(result, default=str))
    return result


# ===========================================================================
# refresh (gap-aware) + key entry
# ===========================================================================
def refresh_market(market, on_progress=None):
    """Pull the latest bars into the cache with the user's key. GAP-AWARE: the lookback covers the
    whole gap since the cache's last bar (so a laptop off for days fills it all). US backfill is
    per-date + resumable; India refresh_recent is per-symbol. Non-fatal if the key is missing."""
    def _say(msg):
        if on_progress:
            on_progress(msg)
    st = data_status(market)
    gap = (st["days_old"] or 0) + 5          # cover the whole gap since the last bar + a buffer
    if market == "us":
        if not us.ensure_api_key():
            return {"ok": False, "msg": "No Polygon key set — add it on Settings."}
        _say("Refreshing US (Polygon) — this can take a while on the first run …")
        syms, _ = us.select_liquid_universe()
        us.backfill(syms, days=max(5, gap))
    else:
        if not india.ensure_dhan_creds():
            return {"ok": False, "msg": "No Dhan creds set — add them on Settings."}
        _say("Refreshing India (Dhan) …")
        syms = [os.path.splitext(os.path.basename(f))[0]
                for f in glob.glob(f"{india.CACHE_DIR}/*.parquet")]
        india.refresh_recent(syms, days=max(15, gap))
    # Recompute + cache the scan and forward results so the pages serve them instantly.
    _say("Scanning the universe …")
    try:
        os.makedirs("data/results", exist_ok=True)
        io_safe.atomic_write_text(_scan_path(market, "nsv2"),
                                  json.dumps(scan_market(market), allow_nan=False))
    except Exception:
        pass
    _say("Updating the forward test …")
    try:
        forward_standings(market)
    except Exception:
        pass
    return {"ok": True, "msg": f"Refreshed {market}."}


def write_polygon_key(key):
    """Persist a Polygon key to .polygon_key (atomic) and reload it (so it takes effect now)."""
    io_safe.atomic_write_text(".polygon_key", key.strip() + "\n")
    os.environ.pop("POLYGON_API_KEY", None)  # drop any stale env value so the file wins
    us.ensure_api_key()


def write_dhan_creds(client_id, token):
    """Persist Dhan creds to .dhan_creds (atomic) and reload them; reset the cached client so the
    new token takes effect in this process."""
    io_safe.atomic_write_text(".dhan_creds",
                              f"DHAN_CLIENT_ID={client_id.strip()}\nDHAN_ACCESS_TOKEN={token.strip()}\n")
    os.environ.pop("DHAN_CLIENT_ID", None)
    os.environ.pop("DHAN_ACCESS_TOKEN", None)
    india._dhan = None                       # rebuild the Dhan client with the new token next call
    india.ensure_dhan_creds()
