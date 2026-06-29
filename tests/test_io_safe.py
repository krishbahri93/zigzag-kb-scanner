"""
Acceptance test for the data-integrity layer (T1.1).

Proves the two guarantees the always-on app depends on:
  - atomic_write_* / atomic_to_parquet round-trip, and a FAILED swap leaves the original intact
    (no partial/corrupt file, no stray temp) — the "laptop shut down mid-write" case;
  - read_parquet_safe returns None (never raises) on a corrupt parquet — the self-healing read.
"""
import os

import pandas as pd
import pytest

from pinescan import io_safe


def _df():
    return pd.DataFrame({"a": [1, 2, 3], "b": [1.5, 2.5, 3.5]})


def test_atomic_text_roundtrip(tmp_path):
    p = str(tmp_path / "s.json")
    io_safe.atomic_write_text(p, '{"x": 1}')
    assert open(p, encoding="utf-8").read() == '{"x": 1}'
    assert not list(tmp_path.glob(".*tmp*"))          # no temp left behind


def test_atomic_parquet_roundtrip(tmp_path):
    p = str(tmp_path / "d.parquet")
    io_safe.atomic_to_parquet(_df(), p)
    pd.testing.assert_frame_equal(pd.read_parquet(p), _df())


def test_read_parquet_safe_on_corrupt(tmp_path):
    good = str(tmp_path / "ok.parquet")
    io_safe.atomic_to_parquet(_df(), good)
    pd.testing.assert_frame_equal(io_safe.read_parquet_safe(good), _df())

    bad = str(tmp_path / "bad.parquet")
    open(bad, "wb").write(b"not a parquet file at all")
    assert io_safe.read_parquet_safe(bad) is None      # tolerant, no raise
    assert io_safe.read_parquet_safe(str(tmp_path / "missing.parquet")) is None


def test_failed_swap_leaves_original(tmp_path, monkeypatch):
    p = str(tmp_path / "s.txt")
    io_safe.atomic_write_text(p, "ORIGINAL")
    # Simulate a crash exactly at the atomic swap: os.replace blows up.
    monkeypatch.setattr(io_safe.os, "replace", lambda *a, **k: (_ for _ in ()).throw(OSError("boom")))
    with pytest.raises(OSError):
        io_safe.atomic_write_text(p, "NEWDATA")
    assert open(p, encoding="utf-8").read() == "ORIGINAL"   # untouched
    assert not list(tmp_path.glob(".*tmp*"))                # temp cleaned up
