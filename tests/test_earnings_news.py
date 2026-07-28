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
# news — tagging, dedupe, recency window, fallback, cache
# ---------------------------------------------------------------------------
def test_tag_headline_rules():
    assert service._tag_headline("Devyani Q1 FY27 profit doubles, revenue up 12%") == "Results"
    assert service._tag_headline("Devyani, Sapphire shares rise on merger approval") == "M&A"
    assert service._tag_headline("SEBI probe into XYZ accounting") == "⚠ Risk"
    assert service._tag_headline("Motilal Oswal sets target price of Rs 165") == "Broker"
    assert service._tag_headline("Company bags order worth Rs 500 crore") == "Orders"
    assert service._tag_headline("Promoter pledge falls to 4%") == "Ownership"
    assert service._tag_headline("Devyani opens 50 new KFC outlets") is None


def test_dedupe_collapses_rewrites_of_one_story():
    # Krish's DEVYANI screenshot: three outlets, one merger story -> keep the first.
    items = [
        {"title": "Devyani Intl, Sapphire Foods shares rise up to 9% on approval from NSE, BSE for merger - Moneycontrol"},
        {"title": "Devyani International, Sapphire Foods rally up to 9% on merger approval - Business Standard"},
        {"title": "Devyani International, Sapphire Foods India shares jumped up to 9% today; here's why - Business Today"},
        {"title": "Devyani International ESOP Grant Update; Shares Trade Flat - HDFC Sky"},
    ]
    kept = service._dedupe_headlines(items)
    assert len(kept) == 2
    assert kept[0]["title"].startswith("Devyani Intl, Sapphire")
    assert kept[1]["title"].startswith("Devyani International ESOP")


def _rss(items):
    rows = "".join(
        f"<item><title>{t}</title><link>https://x/{i}</link>"
        + (f"<pubDate>{p}</pubDate>" if p else "")
        + "<source>Src</source></item>"
        for i, (t, p) in enumerate(items))
    return f'<?xml version="1.0"?><rss version="2.0"><channel>{rows}</channel></rss>'.encode()


def test_fetch_news_windows_sorts_and_caches(monkeypatch):
    calls = []

    class _R:
        def __init__(self, content):
            self.content = content

    def fake_get(url, params=None, **kw):
        calls.append(params["q"])
        return _R(_rss([
            ("Old broker note on Lodha - X", "Mon, 01 Jun 2026 09:00:00 GMT"),
            ("Lodha Q1 profit doubles - Y", "Mon, 27 Jul 2026 09:00:00 GMT"),
            ("Lodha wins order worth Rs 100 crore - Z", "Sun, 20 Jul 2026 09:00:00 GMT"),
        ]))

    monkeypatch.setattr(service.requests, "get", fake_get)
    monkeypatch.setattr(service.india, "get_names", lambda: {"LODHA": "Macrotech Developers"})
    service._NEWS_CACHE.clear()

    items = service.fetch_news("india", "LODHA")
    assert calls == ["Macrotech Developers stock when:30d"]      # 30-day window, no fallback
    assert [i["title"][:9] for i in items] == ["Lodha Q1 ", "Lodha win", "Old broke"]  # newest first
    assert items[0]["tag"] == "Results" and items[1]["tag"] == "Orders"

    service.fetch_news("india", "LODHA")                          # cache hit -> no new request
    assert len(calls) == 1


def test_fetch_news_sparse_fallback_widens(monkeypatch):
    calls = []

    class _R:
        def __init__(self, content):
            self.content = content

    def fake_get(url, params=None, **kw):
        calls.append(params["q"])
        if "when:" in params["q"]:
            return _R(_rss([("Only one recent story - X", "Mon, 27 Jul 2026 09:00:00 GMT")]))
        return _R(_rss([("Older story one - X", "Mon, 01 Mar 2026 09:00:00 GMT"),
                        ("Older story two about results - Y", "Mon, 01 Feb 2026 09:00:00 GMT"),
                        ("Older story three entirely different - Z", None)]))

    monkeypatch.setattr(service.requests, "get", fake_get)
    monkeypatch.setattr(service.india, "get_names", lambda: {})
    service._NEWS_CACHE.clear()

    items = service.fetch_news("india", "TINYCO")
    assert len(calls) == 2 and "when:" not in calls[1]            # widened on sparse coverage
    assert len(items) == 3


def test_next_earnings_reads_our_calendar(monkeypatch):
    monkeypatch.setattr(service.earnings, "read_earnings", lambda market: {
        "rows": [{"sym": "DEVYANI", "date": "2026-07-29"}]})
    assert service.next_earnings("india", "devyani") == "2026-07-29"
    assert service.next_earnings("india", "NOPE") is None
