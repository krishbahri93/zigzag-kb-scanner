"""
io_safe.py — crash-safe file writes + tolerant reads (the data-integrity layer).
================================================================================

ROLE IN THE FLOW
  EVERY cache / state / key / JSON write in the app goes through here, so a laptop that shuts down
  mid-write can never leave a half-written (corrupt) file. The trick is the standard
  write-temp-then-rename: write the new bytes to a sibling `.<name>.tmp.<pid>`, flush them to disk
  (`os.fsync`), then `os.replace(tmp, path)` — and `os.replace` is an ATOMIC filesystem rename on
  the same volume (Windows + POSIX). So at any instant the real file is either the old complete
  version or the new complete version — never a truncated mix.

  `read_parquet_safe` is the read side of the same story: a parquet left corrupt by some OTHER
  cause (an older crash, a disk error) must not crash the app — it returns None so the caller can
  skip + re-fetch that one file (self-healing).

WHO USES IT
  `markets/us.py` + `markets/india.py` (parquet cache writes + tolerant load), `scripts/forward_run.py`
  (state.json), `pinescan/service.py` (key files), the web app. If you add a new writer of data that
  must survive a crash, route it through `atomic_write_*` / `atomic_to_parquet` — never call
  `df.to_parquet(path)` or `open(path, "w")` directly on such a file.

HOW TO EXTEND
  Add a new `atomic_<format>` helper that follows the same temp -> fsync -> `os.replace` skeleton;
  the no-corruption guarantee then comes for free.
"""
import os


def _tmp_path(path):
    """A hidden temp filename in the SAME directory as `path` (same volume → os.replace is atomic).
    PID-suffixed so two processes never collide on the temp."""
    d = os.path.dirname(path) or "."
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, f".{os.path.basename(path)}.tmp.{os.getpid()}")


def _cleanup(tmp):
    if os.path.exists(tmp):
        try:
            os.remove(tmp)
        except OSError:
            pass


def atomic_write_bytes(path, data):
    """Atomically write raw bytes: temp file → flush+fsync → os.replace. On any error the original
    `path` is left untouched and the temp is removed."""
    tmp = _tmp_path(path)
    try:
        with open(tmp, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())          # force the new bytes to physical disk before the swap
        os.replace(tmp, path)             # atomic same-volume rename (Windows + POSIX)
    except BaseException:
        _cleanup(tmp)
        raise


def atomic_write_text(path, text, encoding="utf-8"):
    """Atomically write a text file (state.json, the key files, the dashboard markdown). Encodes to
    bytes ourselves so there is no platform newline translation surprise."""
    atomic_write_bytes(path, text.encode(encoding))


def atomic_to_parquet(df, path, **kwargs):
    """Atomically write a DataFrame to parquet (the cache write). Same content as
    `df.to_parquet(path, **kwargs)` — just crash-safe via temp → fsync → os.replace. `**kwargs`
    forwards to_parquet options (e.g. `index=False`), so callers keep their exact on-disk format."""
    tmp = _tmp_path(path)
    try:
        df.to_parquet(tmp, **kwargs)
        with open(tmp, "rb+") as f:        # fsync the parquet pandas just wrote, then swap
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        _cleanup(tmp)
        raise


def read_parquet_safe(path):
    """Read a parquet file, returning None instead of raising if it is missing or CORRUPT.

    Lets a single bad file (older crash, disk error) be skipped + re-fetched rather than breaking
    the whole load — `load_cache` deletes the file on None so the next refresh rewrites it. pandas
    is imported lazily so this module stays import-cheap.
    """
    import pandas as pd
    if not os.path.exists(path):
        return None
    try:
        return pd.read_parquet(path)
    except Exception:
        return None
