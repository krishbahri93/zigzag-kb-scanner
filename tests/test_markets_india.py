"""
Offline acceptance test for the India daily-data cache (U6).

No live Dhan call is made here: CACHE_DIR is monkeypatched to a tmp dir and a stub
parquet stands in for fetched data. We verify the two cache primitives the scanner
relies on:
  - load_cache round-trips exactly what was written (same rows), and
  - backfill is resumable — a symbol whose parquet already exists is skipped
    WITHOUT touching the network (the live smoke runs separately with real creds).
"""
import os

import pandas as pd

from pinescan.markets import india


def _stub_ohlcv():
    """A tiny daily OHLCV frame shaped like _fetch_dhan_daily's output:
    Open/High/Low/Close/Volume on a (tz-aware) DatetimeIndex."""
    idx = pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"]).tz_localize("Asia/Kolkata")
    return pd.DataFrame(
        {"Open": [100.0, 101.0, 102.5], "High": [101.0, 102.0, 103.0],
         "Low": [99.5, 100.5, 101.0], "Close": [100.5, 101.5, 102.0],
         "Volume": [1_000.0, 1_500.0, 1_200.0]},
        index=idx,
    )


def test_load_cache_roundtrips(tmp_path, monkeypatch):
    monkeypatch.setattr(india, "CACHE_DIR", str(tmp_path))
    df = _stub_ohlcv()
    df.to_parquet(tmp_path / "FAKE.parquet")

    out = india.load_cache(["FAKE", "MISSING"])   # MISSING has no parquet → skipped
    assert list(out) == ["FAKE"]
    pd.testing.assert_frame_equal(out["FAKE"], df, check_freq=False)


def test_backfill_skips_cached_without_network(tmp_path, monkeypatch):
    monkeypatch.setattr(india, "CACHE_DIR", str(tmp_path))
    _stub_ohlcv().to_parquet(tmp_path / "FAKE.parquet")

    def _boom(*args, **kwargs):
        raise AssertionError("backfill must not fetch a symbol that is already cached")

    monkeypatch.setattr(india, "_fetch_dhan_daily", _boom)

    india.backfill(["FAKE"])                       # cached → skipped → no network, no raise
    assert (tmp_path / "FAKE.parquet").exists()    # left untouched


def _write_creds(path, token):
    path.write_text(f"DHAN_CLIENT_ID=cid\nDHAN_ACCESS_TOKEN={token}\n", encoding="utf-8")


def test_reload_token_picks_up_a_rotated_token(tmp_path, monkeypatch):
    """A long-lived process must adopt the daily-minted token: when .dhan_creds changes on disk,
    the stale token in os.environ is overwritten and the cached client is dropped for a rebuild."""
    creds = tmp_path / ".dhan_creds"
    _write_creds(creds, "OLD_TOKEN")
    monkeypatch.setattr(india, "_creds_file", lambda: str(creds))
    monkeypatch.setattr(india, "_dhan", object())          # a live cached client
    monkeypatch.setattr(india, "_creds_mtime", None)
    monkeypatch.setenv("DHAN_ACCESS_TOKEN", "OLD_TOKEN")

    # First look: file matches env → nothing to heal, cached client preserved.
    india._reload_token_if_changed()
    assert india._dhan is not None
    assert os.environ["DHAN_ACCESS_TOKEN"] == "OLD_TOKEN"

    # The 08:30 mint rewrites the file with a fresh token (bump mtime so the guard trips).
    _write_creds(creds, "NEW_TOKEN")
    st = os.stat(creds)
    os.utime(creds, (st.st_mtime + 10, st.st_mtime + 10))

    india._reload_token_if_changed()
    assert os.environ["DHAN_ACCESS_TOKEN"] == "NEW_TOKEN"   # env now authoritative
    assert india._dhan is None                             # cached client dropped → rebuild next call


def test_reload_token_noop_without_creds_file(tmp_path, monkeypatch):
    """No .dhan_creds anywhere → the heal is a silent no-op (backtests/tests run cache-only)."""
    monkeypatch.setattr(india, "_creds_file", lambda: None)
    sentinel = object()
    monkeypatch.setattr(india, "_dhan", sentinel)
    india._reload_token_if_changed()
    assert india._dhan is sentinel
