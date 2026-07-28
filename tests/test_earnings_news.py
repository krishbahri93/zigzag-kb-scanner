"""
Acceptance for the Earnings calendar + per-stock news (Krish, 2026-07-28).
==========================================================================

Network-free: the pure parsers get canned NSE/Nasdaq payloads, the payload join gets
faked caches, and the news fetcher gets a canned Google-News RSS document. The live
fetchers are thin wrappers validated on the server before deploy.
"""
import json

import pytest

from pinescan import earnings, service


# ---------------------------------------------------------------------------
# pure parsers
# ---------------------------------------------------------------------------
def test_parse_nse_events_filters_and_normalises():
    items = [
        {"symbol": "LODHA", "company": "Macrotech Developers", "purpose": "Financial Results",
         "date": "30-Jul-2026"},
        {"symbol": "TCS", "company": "Tata Consultancy", "purpose": "Financial Results/Dividend",
         "date": "31-Jul-2026"},
        {"symbol": "LODHA", "company": "Macrotech", "purpose": "Fund Raising",     # not results
         "date": "30-Jul-2026"},
        {"symbol": "NOTOURS", "company": "Alien Corp", "purpose": "Financial Results",
         "date": "30-Jul-2026"},                                                   # not in universe
        {"symbol": "BADDATE", "company": "X", "purpose": "Financial Results", "date": None},
    ]
    rows = earnings.parse_nse_events(items, ["LODHA", "TCS", "BADDATE"])
    assert [(r["sym"], r["date"]) for r in rows] == [("LODHA", "2026-07-30"),
                                                     ("TCS", "2026-07-31")]
    assert rows[0]["purpose"] == "Financial Results"


def test_parse_nasdaq_earnings_filters_to_universe():
    payload = {"data": {"rows": [{"symbol": "NVDA", "name": "NVIDIA Corporation"},
                                 {"symbol": "ZZZZ", "name": "Not Ours"}]}}
    rows = earnings.parse_nasdaq_earnings(payload, "2026-08-03", ["NVDA", "AAPL"])
    assert rows == [{"sym": "NVDA", "name": "NVIDIA Corporation",
                     "date": "2026-08-03", "purpose": "Earnings"}]
    assert earnings.parse_nasdaq_earnings(None, "2026-08-03", ["NVDA"]) == []


def test_dedupe_sort():
    rows = [{"sym": "B", "date": "2026-08-01"}, {"sym": "A", "date": "2026-08-01"},
            {"sym": "B", "date": "2026-08-01"}, {"sym": "A", "date": "2026-07-30"}]
    out = earnings._dedupe_sort(rows)
    assert [(r["sym"], r["date"]) for r in out] == [
        ("A", "2026-07-30"), ("A", "2026-08-01"), ("B", "2026-08-01")]


# ---------------------------------------------------------------------------
# payload join — calendar rows tagged with our live scan state
# ---------------------------------------------------------------------------
def test_earnings_payload_tags_live_names(monkeypatch):
    monkeypatch.setattr(service.earnings, "read_earnings", lambda market: {
        "fetched_at": "2026-07-28T22:00:00+05:30",
        "rows": [{"sym": "LODHA", "name": "Macrotech", "date": "2026-07-30", "purpose": "Financial Results"},
                 {"sym": "QUIET", "name": "Quiet Co", "date": "2026-07-31", "purpose": "Financial Results"}]})
    monkeypatch.setattr(service, "read_scan", lambda market, scanner="nsv2": {"rows": [
        {"sym": "LODHA", "swings": [{"state": "IN", "bars_in_state": 4}]}]})
    p = service.earnings_payload("india")
    assert p["n_total"] == 2 and p["n_with_sig"] == 1
    assert p["rows"][0]["sig"] == "Active" and p["rows"][1]["sig"] is None


# ---------------------------------------------------------------------------
# news — RSS parse + per-symbol cache
# ---------------------------------------------------------------------------
_RSS = b"""<?xml version="1.0"?><rss version="2.0"><channel>
<item><title>Lodha zooms 9% on results beat</title><link>https://x/1</link>
<pubDate>Mon, 27 Jul 2026 09:00:00 GMT</pubDate><source url="https://bs">Business Standard</source></item>
<item><title>Second headline</title><link>https://x/2</link></item>
</channel></rss>"""


class _Resp:
    content = _RSS


def test_fetch_news_parses_and_caches(monkeypatch):
    calls = {"n": 0}

    def fake_get(*a, **kw):
        calls["n"] += 1
        return _Resp()

    monkeypatch.setattr(service.requests, "get", fake_get)
    monkeypatch.setattr(service.india, "get_names", lambda: {"LODHA": "Macrotech Developers"})
    service._NEWS_CACHE.clear()

    items = service.fetch_news("india", "LODHA")
    assert len(items) == 2
    assert items[0]["title"].startswith("Lodha zooms")
    assert items[0]["source"] == "Business Standard"
    assert items[0]["published"] is not None and items[1]["published"] is None

    service.fetch_news("india", "LODHA")           # second hit -> cache, no new request
    assert calls["n"] == 1
