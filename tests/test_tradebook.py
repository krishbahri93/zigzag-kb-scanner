"""
Acceptance for My TradeBook (Krish, 2026-07-28) + the Indices reference list.
=============================================================================

The book is the user's OFFICIAL record, so the arithmetic must be exact and the
storage boring: per-user JSON, atomic writes, per-user isolation, no path tricks
from the auth header. All network-y edges (scan rows, quotes, earnings) are faked.
"""
import json

import pandas as pd
import pytest

from pinescan import service, tradebook


@pytest.fixture
def clean(tmp_path, monkeypatch):
    """Run against a temp cwd; neutralise the live-scan/quote/earnings joins."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(tradebook, "_scan_row", lambda market, sym: {
        "sym": sym, "name": "Test Co", "sector": "Information Technology",
        "vol_x": 2.1, "day_pct": 1.5, "ltp": 110.0,
        "swings": [{"state": "wait", "in_band": True}]})
    monkeypatch.setattr(service, "next_earnings", lambda market, sym: "2026-08-05")
    return tmp_path


def _buy(user="krish", sym="TCS", price=100.0, **kw):
    p = dict(sym=sym, swing="T2", my_price=price, trigger_price=101.0,
             sl=90.0, target=120.0, amount=200000, notes="bias: strong PA", **kw)
    return tradebook.add(user, "india", p)


# ---------------------------------------------------------------------------
# add / close round-trip
# ---------------------------------------------------------------------------
def test_add_snapshots_context_and_persists(clean):
    t = _buy()
    on_disk = json.load(open(clean / "data/tradebook/krish.json"))
    assert on_disk[0]["id"] == t["id"]
    assert t["sector"] == "Information Technology"        # snapshotted from the scan
    assert t["context"]["vol_x"] == 2.1
    assert t["status"] == "open" and t["side"] == "long"


def test_duplicate_open_position_rejected(clean):
    _buy()
    with pytest.raises(ValueError, match="already open"):
        _buy(price=102.0)
    _buy(sym="INFY")                                       # other symbols still fine


def test_close_settles_pnl_exactly(clean):
    t = _buy(buy_date="2026-07-01")
    c = tradebook.close("krish", t["id"], 120.0, "target")
    assert c["pnl_pct"] == 20.0
    assert c["pnl_amt"] == 40000.0                        # 20% of 2L
    assert c["exit_reason"] == "target" and c["status"] == "closed"
    with pytest.raises(ValueError):                        # can't close twice
        tradebook.close("krish", t["id"], 121.0, "manual")


def test_close_validates_reason(clean):
    t = _buy()
    with pytest.raises(ValueError):
        tradebook.close("krish", t["id"], 90.0, "vibes")


# ---------------------------------------------------------------------------
# per-user isolation + header hygiene
# ---------------------------------------------------------------------------
def test_books_are_per_user(clean):
    _buy(user="krish")
    assert tradebook._load("mammen") == []
    assert len(tradebook._load("krish")) == 1


def test_username_is_sanitised(clean):
    p = tradebook._path("../../etc/passwd")
    assert "/.." not in p.replace("\\", "/") and p.endswith("etcpasswd.json")
    assert tradebook._path("") .endswith("guest.json")


# ---------------------------------------------------------------------------
# listing enrichment + stats windows
# ---------------------------------------------------------------------------
def test_listing_enriches_open_positions(clean, monkeypatch):
    _buy(buy_date="2026-07-20")
    out = tradebook.listing("krish", "india")
    row = out["open"][0]
    assert row["cmp"] == 110.0 and row["up_pct"] == 10.0
    assert row["up_amt"] == 20000.0
    assert row["earnings_date"] == "2026-08-05"
    assert row["scan_sig"] == "In Zone"
    assert out["patterns"]["n_total"] == 1
    assert out["patterns"]["avg_fill_vs_trigger_pct"] == pytest.approx(-0.99, abs=0.01)


def test_stats_period_filter_and_aggregates(clean, monkeypatch):
    import datetime as dt
    a = _buy(sym="AAA", buy_date="2026-07-01")
    b = _buy(sym="BBB", buy_date="2026-07-01")
    c = _buy(sym="CCC", buy_date="2026-01-01")
    tradebook.close("krish", a["id"], 120.0, "target")     # +20%
    tradebook.close("krish", b["id"], 90.0, "stop")        # -10%
    tradebook.close("krish", c["id"], 110.0, "manual")
    # push CCC's exit far into the past so the 30d window drops it
    trades = tradebook._load("krish")
    for t in trades:
        if t["sym"] == "CCC":
            t["exit_date"] = str(dt.date.today() - dt.timedelta(days=90))
    tradebook._save("krish", trades)

    s30 = tradebook.stats("krish", "india", days=30)
    assert s30["n"] == 2 and s30["n_win"] == 1 and s30["win_rate"] == 50.0
    assert s30["pnl_amt"] == pytest.approx(40000 - 20000)
    assert s30["by_reason"] == {"target": 1, "stop": 1, "manual": 0}

    s_all = tradebook.stats("krish", "india", days=0)
    assert s_all["n"] == 3 and s_all["by_reason"]["manual"] == 1


# ---------------------------------------------------------------------------
# CMP freshness (the JKPAPER 414-vs-392 incident)
# ---------------------------------------------------------------------------
def test_display_scan_goes_live_when_officials_are_behind(monkeypatch):
    monkeypatch.setattr(service, "data_status", lambda m: {"last_date": "2026-07-27"})
    monkeypatch.setattr(service, "_expected_asof", lambda m: "2026-07-28")
    assert service._display_scan_live("india") is True     # Dhan late -> keep intraday view
    monkeypatch.setattr(service, "data_status", lambda m: {"last_date": "2026-07-28"})
    assert service._display_scan_live("india") is False    # officials landed -> normal scan


def test_quote_prefers_intraday_when_cache_is_stale(tmp_path, monkeypatch):
    import datetime as dt
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(tradebook, "_scan_row", lambda m, s: None)   # no scanner row
    stale = pd.DataFrame({"Close": [414.55]},
                         index=pd.DatetimeIndex([dt.date.today() - dt.timedelta(days=1)]))
    monkeypatch.setattr(tradebook.io_safe, "read_parquet_safe", lambda fp: stale)
    fresh = pd.DataFrame({"Close": [392.35]}, index=pd.DatetimeIndex([dt.date.today()]))
    from pinescan.markets import india
    monkeypatch.setattr(india, "get_intraday", lambda s: fresh)
    assert tradebook._quote("india", "JKPAPER") == 392.35   # today's truth wins
    # intraday unavailable (pre-open) -> yesterday's official close is the honest latest
    monkeypatch.setattr(india, "get_intraday", lambda s: None)
    assert tradebook._quote("india", "JKPAPER") == 414.55


# ---------------------------------------------------------------------------
# Indices reference list
# ---------------------------------------------------------------------------
def test_index_list_covers_every_index(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    idx = pd.DatetimeIndex(["2026-07-24", "2026-07-27"])
    frame = pd.DataFrame({"Close": [100.0, 102.0]}, index=idx)
    monkeypatch.setattr(service.india, "load_index_cache", lambda: {"NIFTY IT": frame})
    monkeypatch.setattr(service, "_attach_index_members",
                        lambda market, rows: [r.update({"members": [{"sym": "TCS"}]})
                                              for r in rows])
    out = service.index_list("india")
    assert len(out["rows"]) == len(service.india.SECTORAL_INDICES)
    it = next(r for r in out["rows"] if r["sym"] == "NIFTY IT")
    assert it["ltp"] == 102.0 and it["day_pct"] == 2.0 and it["kind"] == "Sectoral"
    assert out["rows"][0]["kind"] == "Sectoral"            # sectoral group sorts first