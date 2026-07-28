"""
Acceptance for the Index Scanner (sectoral indices / sector ETFs through the nsv2 engine).
==========================================================================================

  * universe sanity — curated dicts are well-formed (unique ids, kinds, key names)
  * scan_indices — volume filter BYPASSED for India (indices print no volume) but kept
    for US ETFs; payload lands at data/results/nsv2idx_<market>.json in the scan_market
    shape; rows carry kind-as-sector + the explicit TradingView code; alerts fire once.

Network-free: cache loaders, the registry scanner, and the alert sender are all faked.
"""
import json

import pandas as pd
import pytest

from pinescan.markets import india, us
from pinescan import service


# ---------------------------------------------------------------------------
# universe sanity
# ---------------------------------------------------------------------------
def test_india_index_universe_shape():
    assert len(india.SECTORAL_INDICES) >= 25
    sids = [m["sid"] for m in india.SECTORAL_INDICES.values()]
    assert len(sids) == len(set(sids))                       # no duplicate Dhan ids
    assert "NIFTY IT" in india.SECTORAL_INDICES
    for name, m in india.SECTORAL_INDICES.items():
        assert m["kind"] in ("Sectoral", "Broad"), name
        assert m["sid"].isdigit() and m["tv"] and m["full"], name
    assert sum(1 for m in india.SECTORAL_INDICES.values() if m["kind"] == "Sectoral") >= 20


def test_us_sector_etf_universe_shape():
    assert len(us.SECTOR_ETFS) >= 15
    for sym, m in us.SECTOR_ETFS.items():
        assert sym.isupper() and m["kind"] in ("Sectoral", "Broad") and m["full"], sym
    assert {"XLK", "XLF", "XLE", "SPY"} <= set(us.SECTOR_ETFS)


# ---------------------------------------------------------------------------
# scan_indices — vol-filter policy, payload, alerts
# ---------------------------------------------------------------------------
def _frame(days=80):
    idx = pd.date_range("2026-03-01", periods=days, freq="D")
    return pd.DataFrame({"Open": 100.0, "High": 101.0, "Low": 99.0,
                         "Close": 100.0, "Volume": 0.0}, index=idx)


class _FakeScanner:
    name, display, min_bars = "nsv2", "fake", 60
    default_params = {"useVolFilter": True, "minRallyPct": 35.0}

    def __init__(self, rec):
        self.rec = rec

    def scan_symbol(self, sym, df, params):
        self.rec["params"] = dict(params)
        # one minimal actionable row, in the shape _enrich_row/flatten expect
        return {"sym": sym, "in_band": True, "approaching": False, "fired_entry": False,
                "expired": False, "n_swings": 1, "asof": "2026-07-27", "ltp": 100.0,
                "swings": [{"swing": "T1", "state": "wait", "in_band": True,
                            "approaching": False, "bars_in_state": 1, "entry_lo": 98.0,
                            "entry_hi": 100.0, "sl": 90.0, "tp_lo": 120.0, "tp_hi": 125.0,
                            "depth_pct": 40.0}]}


@pytest.fixture
def wired(tmp_path, monkeypatch):
    """Fake the network-y edges; run scan_indices in a temp cwd it can write into."""
    monkeypatch.chdir(tmp_path)
    rec = {"alerts": 0}
    monkeypatch.setattr(service.registry, "get", lambda name="nsv2": _FakeScanner(rec))
    monkeypatch.setattr(service.notify, "process_scan_alerts",
                        lambda scan, market, live=False: rec.__setitem__("alerts", rec["alerts"] + 1))
    monkeypatch.setattr(service.india, "refresh_indices", lambda days=1100: {"updated": 0})
    monkeypatch.setattr(service.us, "refresh_indices", lambda days=760: {"updated": 0})
    monkeypatch.setattr(service.india, "load_index_cache",
                        lambda: {"NIFTY IT": _frame()})
    monkeypatch.setattr(service.us, "load_index_cache", lambda: {"XLK": _frame()})
    return rec


def test_india_scan_bypasses_volume_filter_and_persists(wired, tmp_path):
    payload = service.scan_indices("india", refresh=True)
    assert wired["params"]["useVolFilter"] is False           # indices have no volume
    assert payload["universe_size"] == len(india.SECTORAL_INDICES)
    assert payload["scanned_ok"] == 1 and payload["data_asof"] == "2026-07-27"
    row = payload["rows"][0]
    assert row["sector"] == "Sectoral" and row["tv_sym"] == "NSE:CNXIT"
    assert row["name"] == "Nifty IT"
    on_disk = json.load(open(tmp_path / "data/results/nsv2idx_india.json"))
    assert on_disk["actionable"] == ["NIFTY IT"]
    assert wired["alerts"] == 1


def test_us_scan_keeps_volume_filter(wired, tmp_path):
    service.scan_indices("us", refresh=False)
    assert wired["params"]["useVolFilter"] is True            # ETFs trade real volume
    on_disk = json.load(open(tmp_path / "data/results/nsv2idx_us.json"))
    assert on_disk["rows"][0]["sector"] == "Sectoral"
    assert on_disk["rows"][0]["name"].startswith("Technology")
