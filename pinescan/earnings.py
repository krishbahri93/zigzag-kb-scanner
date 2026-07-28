"""
earnings.py — the earnings calendar: who reports results, and when.
===================================================================

SOURCES (both verified reachable from the server, 2026-07-28):
  India  NSE's public event-calendar JSON (board meetings; purpose "Financial Results").
         Needs a cookie warm-up hop to www.nseindia.com first — the standard dance.
  US     Nasdaq's public earnings-calendar JSON, one request per date.

Both fetchers RETURN RAW rows; parsing is split into pure functions (unit-tested on
canned payloads) so a source hiccup never hides a parsing bug. refresh_earnings()
filters to OUR universe, normalises to {sym, name, date(YYYY-MM-DD), purpose} and
caches to data/cache/earnings_<market>.json — the dashboard reads only the cache, so
a blocked source degrades to yesterday's calendar, never an error page.
"""
import os
import json
import datetime as dt

import pandas as pd
import requests

from . import io_safe
from .markets import india, us

CACHE = "data/cache/earnings_{market}.json"
_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                     "(KHTML, like Gecko) Chrome/126.0 Safari/537.36",
       "Accept-Language": "en-US,en;q=0.9"}
HORIZON_DAYS = 21          # how far ahead the calendar looks


# ---------------------------------------------------------------------------
# pure parsers (unit-tested)
# ---------------------------------------------------------------------------
def parse_nse_events(items, universe):
    """NSE event-calendar rows -> normalised earnings rows for OUR universe.
    Keeps only 'Financial Results' purposes; dates normalised to YYYY-MM-DD."""
    out, uni = [], set(universe)
    for it in items or []:
        try:
            sym = str(it.get("symbol", "")).upper()
            purpose = str(it.get("purpose", ""))
            if sym not in uni or "result" not in purpose.lower():
                continue
            d = pd.to_datetime(it.get("date") or it.get("bm_date"), dayfirst=True)
            out.append({"sym": sym, "name": str(it.get("company", ""))[:60],
                        "date": str(d.date()), "purpose": purpose})
        except Exception:
            continue
    return out


def parse_nasdaq_earnings(payload, date_str, universe):
    """One Nasdaq calendar day -> normalised rows for OUR universe."""
    out, uni = [], set(universe)
    rows = (((payload or {}).get("data") or {}).get("rows")) or []
    for it in rows:
        try:
            sym = str(it.get("symbol", "")).upper()
            if sym not in uni:
                continue
            out.append({"sym": sym, "name": str(it.get("name", ""))[:60],
                        "date": date_str, "purpose": "Earnings"})
        except Exception:
            continue
    return out


def _dedupe_sort(rows):
    """One row per (sym, date), chronological then alphabetical."""
    seen, out = set(), []
    for r in sorted(rows, key=lambda r: (r["date"], r["sym"])):
        k = (r["sym"], r["date"])
        if k not in seen:
            seen.add(k)
            out.append(r)
    return out


# ---------------------------------------------------------------------------
# fetchers (network; loud-but-never-raising via refresh_earnings)
# ---------------------------------------------------------------------------
def _fetch_india(universe):
    s = requests.Session()
    s.headers.update(_UA)
    s.get("https://www.nseindia.com", timeout=12)              # cookie warm-up
    r = s.get("https://www.nseindia.com/api/event-calendar?index=equities", timeout=20)
    r.raise_for_status()
    return parse_nse_events(r.json(), universe)


def _fetch_us(universe):
    import time
    out, today = [], dt.date.today()
    for i in range(HORIZON_DAYS + 1):
        d = today + dt.timedelta(days=i)
        if d.weekday() >= 5:
            continue
        ds = str(d)
        try:
            r = requests.get(f"https://api.nasdaq.com/api/calendar/earnings?date={ds}",
                             headers=dict(_UA, Accept="application/json"), timeout=15)
            if r.ok:
                out += parse_nasdaq_earnings(r.json(), ds, universe)
        except Exception:
            pass                                               # one bad day ≠ no calendar
        time.sleep(0.5)
    return out


def refresh_earnings(market):
    """Fetch + cache the market's earnings calendar (filtered to our universe).
    Returns the row count; on ANY failure keeps the previous cache and returns None."""
    try:
        if market == "india":
            uni, _ = india.get_universe()
            rows = _fetch_india(uni)
        else:
            uni, _ = us.select_liquid_universe()
            rows = _fetch_us(uni)
        rows = _dedupe_sort(rows)
        # keep only today-forward within the horizon (NSE includes past meetings)
        today = str(dt.date.today())
        limit = str(dt.date.today() + dt.timedelta(days=HORIZON_DAYS))
        rows = [r for r in rows if today <= r["date"] <= limit]
        os.makedirs(os.path.dirname(CACHE.format(market=market)), exist_ok=True)
        io_safe.atomic_write_text(CACHE.format(market=market), json.dumps({
            "fetched_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
            "rows": rows}))
        print(f"  refresh_earnings ({market}): {len(rows)} results dated in the next "
              f"{HORIZON_DAYS} days")
        return len(rows)
    except Exception as e:
        print(f"  WARNING: earnings refresh failed for {market} ({str(e)[:120]}) — "
              f"keeping the previous calendar")
        return None


def read_earnings(market):
    """The cached calendar, or an empty shell if never fetched."""
    try:
        return json.load(open(CACHE.format(market=market), encoding="utf-8"))
    except Exception:
        return {"fetched_at": None, "rows": []}
