"""Golden-master parity: compare a Python port bar-for-bar against a
TradingView CSV export. This is the ONLY accepted proof of behavioral
equivalence — code review, synthetic tests, and agent reasoning are not.

Workflow:
  1. Instrument the Pine script: plot() every series you intend to verify.
  2. On TradingView: "Export chart data" -> CSV (paid plan; ~10-20k bar cap).
     Record symbol, timeframe, timezone, session, bar range.
  3. `load_tv_csv(path)` then `compare(golden, port_outputs)`.
     The LAST bar is dropped by default — the realtime bar repaints.
  4. On pass, `save_snapshot()` the outputs as a regression golden master.

Tolerance is explicit and empirical per indicator (start ~1e-8 absolute /
1e-5 relative, tighten over time); na-vs-value mismatches always diverge.

CLI: python -m pinescan.core parity --csv golden.csv --port mymodule:run
     (mymodule.run(df) must return {plot_title: [values...]} aligned to df)
"""
import json
import math

import pandas as pd


def load_tv_csv(path_or_buf):
    """Load a TradingView "Export chart data" CSV.

    Normalizes the time column to tz-aware datetimes (handles both ISO-8601
    strings and unix-seconds exports) and lowercases the OHLCV column names.
    Plot columns keep their exact titles — they are the comparison keys.
    """
    df = pd.read_csv(path_or_buf)
    rename = {}
    for c in df.columns[:6]:
        if c.strip().lower() in ("time", "open", "high", "low", "close", "volume"):
            rename[c] = c.strip().lower()
    df = df.rename(columns=rename)
    if "time" not in df.columns:
        raise ValueError(f"no 'time' column in CSV (columns: {list(df.columns)})")
    if pd.api.types.is_numeric_dtype(df["time"]):
        df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
    else:
        df["time"] = pd.to_datetime(df["time"], utc=True)
    return df


def _is_na(x):
    if x is None:
        return True
    try:
        return math.isnan(x)
    except TypeError:
        return False


def compare(golden_df, port_outputs, *, drop_last=True, abs_tol=1e-8,
            rel_tol=1e-5, max_report=20):
    """Bar-for-bar diff of `port_outputs` ({series_name: values}) against the
    matching columns of `golden_df`.

    Returns a report dict:
      passed         True iff every series matches on every compared bar
      bars_compared  number of bars diffed (last bar dropped by default)
      series         {name: {passed, n_diverged, divergences: [...]}}
    Each divergence: {bar, time, expected, got, diff} (first `max_report`).

    A bar matches when both values are na, or |expected - got| <=
    abs_tol + rel_tol * |expected|. na on one side only is a divergence.
    """
    n = len(golden_df) - (1 if drop_last else 0)
    report = {"passed": True, "bars_compared": n, "series": {}}
    for name, values in port_outputs.items():
        if name not in golden_df.columns:
            raise KeyError(
                f"series '{name}' not in the golden CSV (columns: "
                f"{list(golden_df.columns)}). Did you plot() it in the Pine "
                "script before exporting? Only plotted series export."
            )
        if len(values) < n:
            raise ValueError(
                f"series '{name}' has {len(values)} values but the golden CSV "
                f"has {n} compared bars — outputs must be bar-aligned to the CSV."
            )
        golden = golden_df[name].tolist()
        times = golden_df["time"].tolist()
        divergences = []
        n_diverged = 0
        for i in range(n):
            e, g = golden[i], values[i]
            if _is_na(e) and _is_na(g):
                continue
            if not _is_na(e) and not _is_na(g) and abs(e - g) <= abs_tol + rel_tol * abs(e):
                continue
            n_diverged += 1
            if len(divergences) < max_report:
                divergences.append({
                    "bar": i,
                    "time": str(times[i]),
                    "expected": None if _is_na(e) else float(e),
                    "got": None if _is_na(g) else float(g),
                    "diff": None if (_is_na(e) or _is_na(g)) else float(abs(e - g)),
                })
        ok = n_diverged == 0
        report["series"][name] = {
            "passed": ok, "n_diverged": n_diverged, "divergences": divergences,
        }
        report["passed"] = report["passed"] and ok
    return report


def format_report(report):
    """Human-readable rendering of a compare() report."""
    lines = [
        f"parity: {'PASS' if report['passed'] else 'FAIL'} "
        f"({report['bars_compared']} bars, last bar excluded as repainting)"
    ]
    for name, s in report["series"].items():
        if s["passed"]:
            lines.append(f"  ok   {name}")
        else:
            lines.append(f"  FAIL {name}: {s['n_diverged']} bars diverged; first:")
            for d in s["divergences"][:5]:
                lines.append(
                    f"         bar {d['bar']} ({d['time']}): "
                    f"expected={d['expected']} got={d['got']} diff={d['diff']}"
                )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# regression golden master
# ---------------------------------------------------------------------------

def save_snapshot(path, outputs):
    """Persist passing port outputs as a JSON regression golden master
    (na stored as null)."""
    payload = {
        name: [None if _is_na(v) else float(v) for v in values]
        for name, values in outputs.items()
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=1)


def load_snapshot(path):
    """Load a snapshot back, null -> nan."""
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    return {
        name: [float("nan") if v is None else v for v in values]
        for name, values in payload.items()
    }
