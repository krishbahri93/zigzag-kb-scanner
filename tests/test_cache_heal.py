"""
Acceptance for the tolerant, self-healing cache reads (T1.4 / T1.5).

A parquet left corrupt by an earlier crash (or any cause) must NOT break load_cache — the bad file
is skipped + deleted (so the next refresh re-fetches it) and the good data still loads. CACHE_DIR is
monkeypatched to a tmp dir so the real cache is untouched.
"""
import pandas as pd

from pinescan import io_safe
from pinescan.markets import us, india


def test_us_load_cache_heals_corrupt(tmp_path, monkeypatch):
    monkeypatch.setattr(us, "CACHE_DIR", str(tmp_path))
    good = pd.DataFrame({"T": ["AAA"], "o": [1.0], "h": [2.0], "l": [0.5], "c": [1.5],
                         "v": [100.0], "t": [1_700_000_000_000]})
    io_safe.atomic_to_parquet(good, str(tmp_path / "2026-06-24.parquet"), index=False)
    bad = tmp_path / "2026-06-25.parquet"
    bad.write_bytes(b"not a parquet")

    cache = us.load_cache(["AAA"])
    assert "AAA" in cache and len(cache["AAA"]) == 1     # good data loaded
    assert not bad.exists()                              # corrupt file self-healed (deleted)


def test_india_load_cache_heals_corrupt(tmp_path, monkeypatch):
    monkeypatch.setattr(india, "CACHE_DIR", str(tmp_path))
    idx = pd.to_datetime(["2024-01-01"]).tz_localize("Asia/Kolkata")
    good = pd.DataFrame({"Open": [1.0], "High": [2.0], "Low": [0.5], "Close": [1.5], "Volume": [9.0]},
                        index=idx)
    io_safe.atomic_to_parquet(good, str(tmp_path / "GOOD.parquet"))
    (tmp_path / "BAD.parquet").write_bytes(b"not a parquet")

    cache = india.load_cache(["GOOD", "BAD"])
    assert list(cache) == ["GOOD"]
    assert not (tmp_path / "BAD.parquet").exists()
