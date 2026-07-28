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
import math
import traceback
import datetime as dt

import pandas as pd
import requests

from pinescan import earnings, io_safe, notify, study
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
def _dhan_creds_on_disk():
    """The KEY=VALUE contents of .dhan_creds as a dict ({} if absent). Same format the token mint
    (scripts/refresh_dhan_token.py) reads and rewrites."""
    out = {}
    if os.path.exists(".dhan_creds"):
        for line in open(".dhan_creds", encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip()
    return out


def _keys_present():
    """Whether each provider key is available (env OR the creds file). Cheap enough for every
    status poll (.dhan_creds is a 4-line file). `dhan` = can fetch data right now (has a token);
    `dhan_auto` = the long-lived secrets are saved, so the daily 08:30 token mint runs unattended."""
    poly = bool(os.environ.get("POLYGON_API_KEY") or os.path.exists(".polygon_key"))
    creds = _dhan_creds_on_disk()

    def have(k):
        return bool(os.environ.get(k) or creds.get(k))

    dhan = have("DHAN_CLIENT_ID") and have("DHAN_ACCESS_TOKEN")
    dhan_auto = have("DHAN_CLIENT_ID") and have("DHAN_PIN") and have("DHAN_TOTP_SECRET")
    return {"polygon": poly, "dhan": dhan, "dhan_auto": dhan_auto,
            "telegram": notify.configured()}


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


def _enrich_row(r, df, sector, vol_frac=1.0):
    """Add the display fields the dashboard shows (sector, day %, volume multiple, R:R,
    distance-to-entry). Pure derivation from data already in hand; never raises — a missing
    field renders as '—', it must not sink the scan.

    vol_frac: fraction of the trading session elapsed (live ticks only). Today's partial
    volume is compared against a session-proportional slice of the 20-day average, so at
    10:00 a normal stock reads ~1x instead of ~0.1x and spikes are visible all day."""
    r["sector"] = sector or ""
    try:
        c = df["Close"]
        v = float(c.iloc[-1] / c.iloc[-2] - 1.0) * 100 if len(c) >= 2 else None
        # round() passes NaN through untouched — a NaN close must yield None, never a NaN
        # in the payload (json.dumps(allow_nan=False) would reject the whole scan).
        r["day_pct"] = round(v, 2) if v is not None and math.isfinite(v) else None
    except Exception:
        r["day_pct"] = None
    try:
        avg = float(df["Volume"].tail(20).mean()) * vol_frac
        vx = float(df["Volume"].iloc[-1]) / avg if avg > 0 else None
        r["vol_x"] = round(vx, 2) if vx is not None and math.isfinite(vx) else None
    except Exception:
        r["vol_x"] = None
    # per-trade R:R + distance (every swing is an independent trade on the dashboard)
    for s in r.get("swings", []):
        s["rr"] = s["dist_pct"] = None
        try:
            risk = s["entry_hi"] - s["sl"]               # worst entry vs stop
            if risk > 0:
                s["rr"] = round((s["tp_lo"] - s["entry_hi"]) / risk, 2)
            if r.get("ltp"):
                # +ve: price must still climb to reach the band; ~0/-ve: at or above band-low
                s["dist_pct"] = round((s["entry_lo"] / r["ltp"] - 1.0) * 100, 2)
        except Exception:
            pass
    # row-level copies mirror the active trade (backwards compatibility)
    r["rr"] = r["dist_pct"] = None
    act = next((s for s in r.get("swings", []) if s.get("swing") == r.get("active")), None)
    if act:
        r["rr"], r["dist_pct"] = act["rr"], act["dist_pct"]


def _json_safe(o):
    """Recursively replace non-finite floats (NaN/Inf) with None. The scan JSON is written with
    allow_nan=False (strict, correct) — but that means ONE stray NaN in ONE row silently sank the
    whole scan write inside refresh_market's try/except (the 2026-07-09/10 stall). Belt-and-braces
    with the point fixes in _enrich_row."""
    if isinstance(o, float):
        return o if math.isfinite(o) else None
    if isinstance(o, dict):
        return {k: _json_safe(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_json_safe(v) for v in o]
    return o


_SIGNAL_STATE = "data/status/signal_state.json"


def _stamp_confirmed(market, scanner, rows):
    """Persist the FIRST time each (sym, swing) was seen actionable, so the dashboard can show
    'confirmed X ago' and flag FRESH entries — survives restarts and re-scans. Keys that are no
    longer actionable are dropped, so a setup that resets later counts as fresh again."""
    try:
        seen = json.loads(open(_SIGNAL_STATE, encoding="utf-8").read())
    except Exception:
        seen = {}
    now = dt.datetime.now().astimezone().isoformat(timespec="seconds")
    prefix = f"{market}:{scanner}:"
    live = set()
    for r in rows:
        if r.get("expired"):
            continue
        for s in r.get("swings", []):
            actionable = s.get("state") == "IN" or (s.get("state") == "wait" and s.get("in_band"))
            if not actionable:
                continue
            k = f"{prefix}{r['sym']}:{s['swing']}"
            live.add(k)
            if k not in seen:
                seen[k] = now
            s["confirmed_at"] = seen[k]
            s["fresh"] = seen[k] == now
            if s["swing"] == r.get("active"):          # row-level mirror (compat)
                r["confirmed_at"], r["fresh"] = seen[k], seen[k] == now
    seen = {k: v for k, v in seen.items() if (not k.startswith(prefix)) or k in live}
    try:
        os.makedirs(os.path.dirname(_SIGNAL_STATE), exist_ok=True)
        io_safe.atomic_write_text(_SIGNAL_STATE, json.dumps(seen))
    except Exception:
        pass


def _expected_asof(market):
    """The trading date the newest confirmed daily bar SHOULD carry: today once the session has
    closed (and the close-run had time to land), else the previous weekday. Exchange holidays are
    deliberately not modelled — the dashboard's stale banner copy allows for them."""
    tz = "Asia/Kolkata" if market == "india" else "America/New_York"
    now = pd.Timestamp.now(tz=tz)
    d = now.date()
    close_hour = 16 if market == "india" else 17     # NSE closes 15:30 IST, US 16:00 ET
    if now.hour < close_hour:                        # today's confirmed bar can't exist yet
        d -= dt.timedelta(days=1)
    while d.weekday() >= 5:                          # roll back over Sat/Sun
        d -= dt.timedelta(days=1)
    return str(d)


def _is_behind(last_date, expected):
    """True when the cache's newest official bar predates the expected trading date.
    Pure (ISO strings compare lexicographically) so the publish-wait and morning
    self-heal decisions are unit-testable. None on either side reads as NOT behind —
    an empty cache is first-install territory, not a staleness signal."""
    return bool(expected) and bool(last_date) and last_date < expected


# Once-a-day guard for the morning self-heal (see _self_heal_official_bars).
_SELFHEAL_STATE = "data/status/selfheal.json"


def _self_heal_official_bars(market):
    """Top up missed OFFICIAL daily bars before a live tick scans (India only).

    Since ~2026-07-24 Dhan publishes EOD bars late: the 15:55 close run can miss the whole
    day, leaving the dashboard on yesterday's confirmed data until a human pressed Refresh.
    This runs at most twice per day (second try only after 11:00, when late bars have
    usually landed) and only while the cache is actually behind the expected trading day —
    a market holiday therefore costs two cheap sweeps, never a loop. job_wrapper's flock
    keeps overlapping ticks out for the ~6 minutes a top-up takes."""
    if market != "india":
        return
    st = data_status(market)
    exp = _expected_asof(market)
    if not _is_behind(st["last_date"], exp):
        return
    today = str(dt.date.today())
    try:
        s = json.load(open(_SELFHEAL_STATE))
    except Exception:
        s = {}
    if s.get("date") != today:
        s = {"date": today, "attempts": 0}
    if s["attempts"] >= 2 or (s["attempts"] == 1 and dt.datetime.now().hour < 11):
        return
    s["attempts"] += 1
    os.makedirs(os.path.dirname(_SELFHEAL_STATE), exist_ok=True)
    io_safe.atomic_write_text(_SELFHEAL_STATE, json.dumps(s))
    print(f"  self-heal: official cache {st['last_date']} < expected {exp} — topping up …")
    syms = [os.path.splitext(os.path.basename(f))[0]
            for f in glob.glob(f"{india.CACHE_DIR}/*.parquet")]
    summ = india.refresh_recent(syms, days=15)
    print(f"  self-heal: {summ['updated']}/{summ['total']} updated, "
          f"newest bar {summ['latest_bar']} on {summ['on_latest']} symbols")


def scan_market(market, scanner="nsv2", live=False):
    """Run a scanner over a market's cached universe → the flat scan dict (same shape scan.py wrote).
    Reuses the registry scanner's scan_symbol + min_bars + default_params, so a new scanner works
    here with no change.

    live=True (market-hours tick): merge TODAY'S intraday partial bar into each frame IN MEMORY
    before scanning, so the engine sees live price action. Partial bars are NEVER persisted — the
    parquet cache holds only official daily bars (the 15:55 close run writes those)."""
    sc = registry.get(scanner)
    syms, cache = _universe_cache(market)
    sectors, names = {}, {}
    if market == "india":
        try:
            _, sectors = india.get_universe()      # disk-cached weekly; {} if unavailable
        except Exception:
            sectors = {}
        names = india.get_names()
    else:
        names = us.get_names()

    # during a live tick, judge today's PARTIAL volume against the session fraction elapsed
    # (NSE cash session 09:15-15:30 = 375 min); a full-day comparison reads ~0x all morning
    vol_frac = 1.0
    if live and market == "india":
        mins = (dt.datetime.now().hour * 60 + dt.datetime.now().minute) - (9 * 60 + 15)
        vol_frac = min(1.0, max(0.08, mins / 375.0))

    live_partials = 0
    if live and market == "india":
        today = dt.date.today()
        for s in list(cache.keys()):
            df = cache[s]
            try:
                if df is None or not len(df) or df.index[-1].date() >= today:
                    continue                       # official bar already posted (or no data)
                part = india.get_intraday(s)       # 1-row partial bar, or None (closed/holiday)
                if part is not None and len(part):
                    cache[s] = pd.concat([df, part])
                    live_partials += 1
            except Exception:
                continue
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
            _enrich_row(r, cache[s], sectors.get(s), vol_frac)   # cache[s] includes the live bar
            r["name"] = names.get(s, "")
            rows.append(r)
            asof_dates.add(r["asof"])
    rows.sort(key=lambda r: (not r["in_band"], not r["approaching"], -(r["n_swings"])))
    actionable = [r for r in rows if (r["in_band"] or r["approaching"] or r["fired_entry"])
                  and not r["expired"]]
    _stamp_confirmed(market, scanner, rows)
    return _json_safe({
        "engine": f"{sc.name} ({sc.display}, faithful port)",
        "generated_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "live_bar": bool(live_partials),           # last bar is today's forming bar, not a close
        "live_partials": live_partials,
        "generated_for_date": str(pd.Timestamp.now(          # market-LOCAL calendar date
            tz="Asia/Kolkata" if market == "india" else "America/New_York").date()),
        "data_asof": max(asof_dates) if asof_dates else None,
        "expected_asof": _expected_asof(market),     # dashboard stale-banner reference date
        "params": {k: sc.default_params[k] for k in _SCAN_PARAM_KEYS if k in sc.default_params},
        "universe_size": len(syms),
        "scanned_ok": scanned,
        "setups_total": len(rows),
        "actionable_count": len(actionable),
        "actionable": [r["sym"] for r in actionable],
        "rows": rows,
    })


def _scan_path(market, scanner):
    return f"data/results/{scanner}_{market}.json"


def earnings_payload(market):
    """The cached earnings calendar joined with the CURRENT scan — each reporting stock
    tagged with our live state (Active/Triggered/In Zone/Approaching), so 'who reports
    this week' doubles as 'which of MY names report this week'."""
    cal = earnings.read_earnings(market)
    scan = read_scan(market, "nsv2") or {}
    state = {r["sym"]: _best_sig(r) for r in scan.get("rows", [])}
    rows = cal.get("rows", [])
    for r in rows:
        r["sig"] = state.get(r["sym"])
    return {"fetched_at": cal.get("fetched_at"), "rows": rows,
            "n_total": len(rows), "n_with_sig": sum(1 for r in rows if r.get("sig"))}


# per-(market,symbol) headline cache — the web process is long-lived, 30 min is plenty
_NEWS_CACHE = {}
_NEWS_TTL_S = 30 * 60


def fetch_news(market, sym):
    """Latest headlines for one stock via Google News RSS (no key, verified reachable).

    Queries by COMPANY NAME (the universe caches store them) rather than the ticker —
    'Lodha Developers stock' finds news, 'LODHA stock' mostly doesn't. Cached ~30 min per
    symbol; fetched on demand when a dashboard row expands, so we never bulk-poll 752
    symbols. Returns [{title, link, source, published}] (≤8), [] on any failure."""
    import time
    import xml.etree.ElementTree as ET
    key = (market, sym.upper())
    hit = _NEWS_CACHE.get(key)
    if hit and time.time() - hit["at"] < _NEWS_TTL_S:
        return hit["items"]
    try:
        names = india.get_names() if market == "india" else us.get_names()
        q = (names.get(sym.upper()) or sym) + " stock"
        gl = "IN" if market == "india" else "US"
        r = requests.get("https://news.google.com/rss/search",
                         params={"q": q, "hl": f"en-{gl}", "gl": gl, "ceid": f"{gl}:en"},
                         headers=earnings._UA, timeout=12)
        items = []
        for it in ET.fromstring(r.content).findall(".//item")[:8]:
            pub = it.findtext("pubDate")
            try:
                ts = pd.to_datetime(pub) if pub else None
                pub = ts.isoformat() if ts is not None and not pd.isna(ts) else None
            except Exception:
                pub = None
            items.append({"title": (it.findtext("title") or "")[:160],
                          "link": it.findtext("link") or "",
                          "source": (it.findtext("source") or "")[:40],
                          "published": pub})
        _NEWS_CACHE[key] = {"at": time.time(), "items": items}
        return items
    except Exception:
        return hit["items"] if hit else []


def _best_sig(row):
    """One display state per stock, best-first, mirroring the dashboard's flatten():
    Triggered > In Zone > Active > Approaching > None."""
    best, rank = None, 99
    order = {"Triggered": 0, "In Zone": 1, "Active": 2, "Approaching": 3}
    for s in row.get("swings", []):
        sig = None
        if s.get("state") == "IN":
            sig = "Triggered" if s.get("bars_in_state", 99) <= 1 else "Active"
        elif s.get("state") == "wait":
            sig = "In Zone" if s.get("in_band") else ("Approaching" if s.get("approaching") else None)
        if sig is not None and order[sig] < rank:
            best, rank = sig, order[sig]
    return best


def _attach_index_members(market, rows):
    """Attach r["members"] to every index row that has a membership source: the stocks a
    trader would drill into when that index fires — OUR universe's members of the sector
    (India) or the ETF's representative holdings (US), each tagged with the stock
    scanner's CURRENT signal, price and day%. Sorted setups-first, then day% — the
    "leading stocks" read. Never raises: the Index tab must render without members."""
    try:
        stock_scan = read_scan(market, "nsv2") or {}
        srow = {r["sym"]: r for r in stock_scan.get("rows", [])}
        if market == "india":
            syms, sectors = india.get_universe()
            by_sector = {}
            for s in syms:
                by_sector.setdefault(sectors.get(s, ""), []).append(s)
            # quotes for members without setups come off the cache tail (2 closes)
            def quote(sym):
                df = io_safe.read_parquet_safe(os.path.join(india.CACHE_DIR, f"{sym}.parquet"))
                if df is None or len(df) < 2:
                    return None, None
                c = df["Close"]
                dp = float(c.iloc[-1] / c.iloc[-2] - 1.0) * 100
                return float(c.iloc[-1]), (round(dp, 2) if math.isfinite(dp) else None)
            members_of = lambda name: sorted({m for lab in india.INDEX_SECTOR_MAP.get(name, [])
                                              for m in by_sector.get(lab, [])})
        else:
            def quote(sym):
                r = srow.get(sym)
                return (r.get("ltp"), r.get("day_pct")) if r else (None, None)
            members_of = lambda name: us.REP_HOLDINGS.get(name, [])

        order = {"Triggered": 0, "In Zone": 1, "Active": 2, "Approaching": 3, None: 9}
        for r in rows:
            mem = members_of(r["sym"])
            if not mem:
                r["members"] = None                       # thematic/broad: no drill-down
                continue
            out = []
            for sym in mem:
                sig = _best_sig(srow[sym]) if sym in srow else None
                ltp, dp = (srow[sym].get("ltp"), srow[sym].get("day_pct")) \
                    if sym in srow else quote(sym)
                out.append({"sym": sym, "ltp": ltp, "day_pct": dp, "sig": sig})
            out.sort(key=lambda m: (order.get(m["sig"], 9),
                                    -(m["day_pct"] if m["day_pct"] is not None else -1e9)))
            n_sig = sum(1 for m in out if m["sig"])
            r["members_note"] = f"{n_sig} of {len(out)} with live setups"
            r["members"] = out[:60]                       # cap the widest sectors
            if len(out) > 60:
                r["members_note"] += f" · showing top 60 of {len(out)}"
    except Exception:
        traceback.print_exc()
        for r in rows:
            r.setdefault("members", None)


def scan_indices(market, refresh=False):
    """Index Scanner: run the SAME nsv2 engine over the market's index universe — India's
    NSE/BSE sectoral indices (Dhan IDX_I) or the US sector ETFs (Polygon) — and persist
    the result as scanner "nsv2idx", so /api/scan?scanner=nsv2idx serves it with zero
    extra plumbing. Payload shape mirrors scan_market's exactly (same dashboard code,
    same stale-banner fields).

    Indices print no volume, so the engine's volume filter is BYPASSED for India (the
    same call the intraday Pine scripts made); US sector ETFs trade with real volume,
    so they keep the stock defaults. Alerts ride the normal pipeline — index names
    ("NIFTY METAL") are self-describing in the Telegram message and can't collide with
    stock tickers in the dedupe state."""
    sc = registry.get("nsv2")
    if market == "india":
        if refresh:
            india.refresh_indices()
        cache = india.load_index_cache()
        meta = india.SECTORAL_INDICES
        params = dict(sc.default_params, useVolFilter=False)   # indices have no volume
    else:
        if refresh:
            us.refresh_indices()
        cache = us.load_index_cache()
        meta = us.SECTOR_ETFS
        params = dict(sc.default_params)                       # ETFs: real volume, keep filter
    rows, scanned, asof_dates = [], 0, set()
    for name, df in cache.items():
        if df is None or len(df) < sc.min_bars:
            continue
        try:
            r = sc.scan_symbol(name, df, params)
        except Exception:
            continue
        scanned += 1
        if r is not None:
            _enrich_row(r, df, meta[name]["kind"], 1.0)        # kind = Sectoral | Broad
            r["name"] = meta[name].get("full", "")
            r["tv_sym"] = meta[name].get("tv")                 # explicit TV chart code (India)
            rows.append(r)
            asof_dates.add(r["asof"])
    rows.sort(key=lambda r: (not r["in_band"], not r["approaching"], -(r["n_swings"])))
    actionable = [r for r in rows if (r["in_band"] or r["approaching"] or r["fired_entry"])
                  and not r["expired"]]
    _stamp_confirmed(market, "nsv2idx", rows)
    _attach_index_members(market, rows)       # the constituents drill-down (never raises)
    payload = _json_safe({
        "engine": f"{sc.name} on indices ({sc.display}, volume filter "
                  f"{'bypassed' if market == 'india' else 'active'})",
        "generated_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "live_bar": False,
        "live_partials": 0,
        "generated_for_date": str(pd.Timestamp.now(
            tz="Asia/Kolkata" if market == "india" else "America/New_York").date()),
        "data_asof": max(asof_dates) if asof_dates else None,
        "expected_asof": _expected_asof(market),
        "params": {k: params[k] for k in _SCAN_PARAM_KEYS if k in params},
        "universe_size": len(meta),
        "scanned_ok": scanned,
        "setups_total": len(rows),
        "actionable_count": len(actionable),
        "actionable": [r["sym"] for r in actionable],
        "rows": rows,
    })
    os.makedirs("data/results", exist_ok=True)
    io_safe.atomic_write_text(_scan_path(market, "nsv2idx"), json.dumps(payload, allow_nan=False))
    notify.process_scan_alerts(payload, market, live=False)
    return payload


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
        # brand-new install: nothing cached, so seed the full ~2y history (same trap the
        # India path had — an empty cache must mean "download everything", not "top up 5 days")
        us.backfill(syms, days=730 if st["n_cached"] == 0 else max(5, gap))
    else:
        if not india.ensure_dhan_creds():
            return {"ok": False, "msg": "No Dhan creds set — add them on Settings."}
        syms = [os.path.splitext(os.path.basename(f))[0]
                for f in glob.glob(f"{india.CACHE_DIR}/*.parquet")]
        if not syms:
            # brand-new install: nothing cached to top up, so seed the whole Total Market first
            # (resumable; same path as scripts/backfill_india.py)
            _say("First India run — downloading the Nifty Total Market history (10–30 min, resumable) …")
            syms, _sectors = india.get_universe()
            india.backfill(syms)
        else:
            _say("Refreshing India (Dhan) …")
            summ = india.refresh_recent(syms, days=max(15, gap))
            _say(f"Refreshed {summ['updated']}/{summ['total']} symbols — "
                 f"newest bar {summ['latest_bar']}")
            # Top up NEW universe constituents (index additions / a widened universe): the
            # scan universe is the cache DIRECTORY, and refresh_recent only tops up files
            # that already exist — without this, a new symbol never enters the cache and
            # the universe silently stays at its install-day size (was: stuck at 489).
            try:
                uni, _sectors = india.get_universe()
                cached = set(syms)
                missing = [s for s in uni if s not in cached]
                if missing:
                    _say(f"Universe has {len(missing)} new symbols — downloading their history …")
                    india.backfill(missing)          # resumable; skips already-cached symbols
            except Exception:
                print("  WARNING: universe top-up failed — scan continues on cached symbols:")
                traceback.print_exc()
    # Recompute + cache the scan and forward results so the pages serve them instantly.
    _say("Scanning the universe …")
    try:
        os.makedirs("data/results", exist_ok=True)
        scan = scan_market(market)
        io_safe.atomic_write_text(_scan_path(market, "nsv2"), json.dumps(scan, allow_nan=False))
        notify.process_scan_alerts(scan, market, live=False)   # ✅ confirms + 🎯/🛑 hits + EOD summary
    except Exception:
        # Never sink the refresh — but never fail SILENTLY either: a swallowed scan error
        # left the dashboard serving stale signals for two days (2026-07-09/10).
        print("  WARNING: the scan step failed — the dashboard keeps the PREVIOUS scan:")
        traceback.print_exc()
    _say("Scanning the index universe …")
    try:
        scan_indices(market, refresh=True)     # sectoral indices / sector ETFs + alerts
    except Exception:
        print("  WARNING: the index-scan step failed — the Index tab keeps its previous scan:")
        traceback.print_exc()
    _say("Updating the earnings calendar …")
    earnings.refresh_earnings(market)          # keeps its previous cache on any failure
    _say("Updating the forward test …")
    try:
        forward_standings(market)
    except Exception:
        print("  WARNING: the forward-test step failed (scan above already saved):")
        traceback.print_exc()
    return {"ok": True, "msg": f"Refreshed {market}."}


def intraday_tick(market="india", scanner="nsv2"):
    """One market-hours tick (the 15-min timer's job): scan the cached universe with today's
    LIVE partial bar merged in memory, and cache the result for the dashboard. Deliberately
    light: no data-cache writes, no forward test (both belong to the 15:55 close run) — with
    ONE exception: the late-EOD self-heal below may top up official bars the close run missed.
    Outside market hours every partial fetch returns None, so a tick degrades to a plain re-scan."""
    if market != "india":
        return {"ok": False, "msg": "intraday ticks are India-only for now"}
    if not india.ensure_dhan_creds():
        return {"ok": False, "msg": "No Dhan creds set — add them on Settings."}
    # Best-effort self-heal — a tick must still scan even if the top-up fails.
    try:
        _self_heal_official_bars(market)
    except Exception:
        traceback.print_exc()
    scan = scan_market(market, scanner, live=True)
    os.makedirs("data/results", exist_ok=True)
    io_safe.atomic_write_text(_scan_path(market, scanner), json.dumps(scan, allow_nan=False))
    notify.process_scan_alerts(scan, market, live=True)   # silent no-op without Telegram creds
    return {"ok": True,
            "msg": f"Live scan: {scan['live_partials']} live bars, "
                   f"{scan['actionable_count']} actionable of {scan['setups_total']} setups."}


def write_polygon_key(key):
    """Persist a Polygon key to .polygon_key (atomic) and reload it (so it takes effect now)."""
    io_safe.atomic_write_text(".polygon_key", key.strip() + "\n")
    os.environ.pop("POLYGON_API_KEY", None)  # drop any stale env value so the file wins
    us.ensure_api_key()


def write_dhan_creds(client_id="", token="", pin="", totp_secret=""):
    """MERGE the provided (non-empty) Dhan values into .dhan_creds (atomic) and reload. The file
    also holds the long-lived DHAN_PIN + DHAN_TOTP_SECRET that the daily token mint
    (scripts/refresh_dhan_token.py) needs — never clobber keys the caller didn't provide."""
    creds = _dhan_creds_on_disk()
    for k, v in (("DHAN_CLIENT_ID", client_id), ("DHAN_ACCESS_TOKEN", token),
                 ("DHAN_PIN", pin), ("DHAN_TOTP_SECRET", totp_secret)):
        if v and v.strip():
            creds[k] = v.strip()
    order = ["DHAN_CLIENT_ID", "DHAN_ACCESS_TOKEN", "DHAN_PIN", "DHAN_TOTP_SECRET"]
    lines = [f"{k}={creds[k]}" for k in order if k in creds]
    lines += [f"{k}={v}" for k, v in creds.items() if k not in order]
    io_safe.atomic_write_text(".dhan_creds", "\n".join(lines) + "\n")
    for k in order:
        os.environ.pop(k, None)              # the file is authoritative after a save
    india._dhan = None                       # rebuild the Dhan client with the new token next call
    india.ensure_dhan_creds()                # False while the token is still missing — mint fills it
