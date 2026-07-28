"""
Acceptance for the Dhan pipeline resilience layer (the 2026-07-24..28 incident fixes).
======================================================================================

Covers the deterministic pieces without any network:
  * _classify_remarks — Dhan response dict -> failure class (DH-904 = rate_limited, etc.)
  * service._is_behind — the publish-wait / morning-self-heal trigger comparison
  * refresh_recent — failures are CLASSIFIED (rate-limited / unmapped / empty), the
    rate-limited tail gets a second sweep, and the returned summary counts are exact.
The live behaviours (backoff pacing, actual top-ups) are validated on the server by a
manual close-run — see the incident notes.
"""
import pandas as pd
import pytest

from pinescan.markets import india
from pinescan import service


# ---------------------------------------------------------------------------
# _classify_remarks — pure response classification
# ---------------------------------------------------------------------------
def test_classify_data_present_is_none():
    r = {"status": "success", "remarks": "", "data": {"close": [1.0, 2.0]}}
    assert india._classify_remarks(r) is None


def test_classify_rate_limit_and_other_codes():
    r904 = {"status": "failure", "remarks": {"error_code": "DH-904", "error_type": "Rate_Limit"}}
    assert india._classify_remarks(r904) == "rate_limited"
    r902 = {"status": "failure", "remarks": {"error_code": "DH-902"}}
    assert india._classify_remarks(r902) == "error:DH-902"


def test_classify_empty_variants():
    assert india._classify_remarks({"status": "success", "data": {}}) == "empty"
    assert india._classify_remarks({"status": "success", "data": {"close": []}}) == "empty"
    assert india._classify_remarks(None) == "empty"          # non-dict SDK surprise


# ---------------------------------------------------------------------------
# service._is_behind — the staleness trigger
# ---------------------------------------------------------------------------
def test_is_behind_comparisons():
    assert service._is_behind("2026-07-24", "2026-07-27") is True
    assert service._is_behind("2026-07-27", "2026-07-27") is False
    assert service._is_behind("2026-07-28", "2026-07-27") is False
    # None on either side must read NOT behind (first-install, never a heal loop)
    assert service._is_behind(None, "2026-07-27") is False
    assert service._is_behind("2026-07-24", None) is False


# ---------------------------------------------------------------------------
# refresh_recent — classification + the rate-limited second sweep
# ---------------------------------------------------------------------------
def _bars(last_day):
    idx = pd.DatetimeIndex([pd.Timestamp(last_day) - pd.Timedelta(days=1),
                            pd.Timestamp(last_day)])
    return pd.DataFrame({"Open": [1.0, 2.0], "High": [1.0, 2.0], "Low": [1.0, 2.0],
                         "Close": [1.0, 2.0], "Volume": [10, 20]}, index=idx)


def test_refresh_recent_classifies_and_retries_rate_limited(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(india, "CACHE_DIR", str(tmp_path))
    calls = {"RATE": 0}

    def fake_fetch(sym, days=15):
        if sym == "OK":
            india.LAST_FETCH_ERROR = None
            return _bars("2026-07-27")
        if sym == "RATE":                       # limited on the sweep, fine on the retry pass
            calls["RATE"] += 1
            if calls["RATE"] == 1:
                india.LAST_FETCH_ERROR = "rate_limited"
                return None
            india.LAST_FETCH_ERROR = None
            return _bars("2026-07-27")
        if sym == "GONE":
            india.LAST_FETCH_ERROR = "unmapped"
            return None
        india.LAST_FETCH_ERROR = "empty"        # "NOBAR"
        return None

    monkeypatch.setattr(india, "_fetch_dhan_daily", fake_fetch)
    summ = india.refresh_recent(["OK", "RATE", "GONE", "NOBAR"], days=15)

    assert summ["updated"] == 2                 # OK + RATE (via the second sweep)
    assert summ["rate_limited"] == 0            # cleared by the retry pass
    assert summ["unmapped"] == 1 and summ["empty"] == 1
    assert summ["latest_bar"] == "2026-07-27" and summ["on_latest"] == 2
    assert calls["RATE"] == 2
    assert (tmp_path / "OK.parquet").exists() and (tmp_path / "RATE.parquet").exists()
    out = capsys.readouterr().out
    assert "retrying 1 rate-limited" in out and "1 unmapped" in out


def test_refresh_recent_merges_with_existing_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(india, "CACHE_DIR", str(tmp_path))
    old = _bars("2026-07-26")                   # bars 25, 26
    from pinescan import io_safe
    io_safe.atomic_to_parquet(old, str(tmp_path / "OK.parquet"))

    def fake_fetch(sym, days=15):
        india.LAST_FETCH_ERROR = None
        return _bars("2026-07-27")              # bars 26, 27 — overlaps `old` on the 26th

    monkeypatch.setattr(india, "_fetch_dhan_daily", fake_fetch)
    summ = india.refresh_recent(["OK"], days=15)
    merged = pd.read_parquet(tmp_path / "OK.parquet")
    assert summ["updated"] == 1 and summ["latest_bar"] == "2026-07-27"
    assert len(merged) == 3                     # 25, 26, 27 — the overlap deduped (keep last)
    assert merged.index.is_monotonic_increasing
