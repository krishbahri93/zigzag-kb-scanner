"""
Acceptance test for U8 — the backtest CLI (run.py) + report (report.py).
========================================================================

The CLI is glue, so these tests pin the glue, not the signal/portfolio math (those are
covered by the engine/metrics suites). We monkeypatch run._load_market to inject a tiny
synthetic cache — a couple of symbols carrying a known V2 setup, adapted from
tests/test_scanner.py's `_df` — so run() never touches the network or real data files and
the run is fully deterministic.

  * run('india', ['baseline'])            -> one Result, real metric keys, equity curve.
  * run('india', ['baseline','rotation']) -> two Results (both scored on the same cache).
  * english_tree(rotation policy)         -> generated from the rule descriptions, so it
                                             names the rotation rule AND its filled param.
  * comparison_table([...])               -> exactly one row per policy.
"""
import os

import numpy as np
import pandas as pd

from pinescan.backtest import run, report
from pinescan.backtest.rules.registry import load_policy

# Metric keys metrics.summarize() always emits (None where undefined) — report.py and the
# engine both depend on these existing, so we assert run() surfaces them on every Result.
EXPECTED_METRIC_KEYS = {
    "total_return_pct", "cagr", "max_drawdown_pct", "win_rate",
    "avg_r", "profit_factor", "avg_holding_days", "num_trades",
}


def _df(rally_to):
    """Adapted from tests/test_scanner.py: early low -> rise to A~100 -> fall to B~50 ->
    rally up to `rally_to`. This shape is a known V2 setup (the scanner suite verifies a
    T1 swing forms and sits in its entry band at rally_to=68)."""
    pre = [70, 67, 63, 58, 53, 49, 47, 49, 53, 58, 63, 68]   # early low = first pivot
    base = [72, 80, 90, 100]                                 # rise into A=100
    down = list(np.linspace(100, 50, 14))[1:]                # A -> B=50
    rally = list(np.linspace(50.5, rally_to, 30))
    px = pre + base + down + rally
    idx = pd.date_range("2024-01-01", periods=len(px), freq="D", tz="UTC")
    vol = [1e6] * (len(pre) + len(base) + len(down)) + list(np.linspace(3e6, 30e6, 30))
    return pd.DataFrame({"Open": px, "High": [x * 1.01 for x in px],
                         "Low": [x * 0.99 for x in px], "Close": px, "Volume": vol},
                        index=idx)


def _synthetic_cache():
    """Two-to-three symbols of OHLCV with a known V2 setup, the shape both market loaders
    produce. One rallies into its entry band, one past its peak — enough timeline for the
    engine to mark equity every day regardless of whether an entry ultimately fires."""
    return {
        "SYN1": _df(rally_to=68),     # rallies into the T1 entry band
        "SYN2": _df(rally_to=72),     # slightly higher rally
        "SYN3": _df(rally_to=115),    # blows past the peak
    }


def _patch_market(monkeypatch):
    """Make run._load_market return the synthetic cache, so run() does no I/O. The lambda
    swallows (market, years) — the injected cache is independent of both."""
    monkeypatch.setattr(run, "_load_market", lambda *a, **k: _synthetic_cache())


def _rotation_policy():
    """Load the shipped rotation policy straight from policies/ (its real params drive the
    description fill the english_tree assertion checks)."""
    return load_policy(os.path.join(run.POLICIES_DIR, "rotation.json"))


# --------------------------------------------------------------------------------------
# run() — one policy: a single scored Result with real metrics and a non-empty curve.
# --------------------------------------------------------------------------------------
def test_run_single_policy_returns_one_scored_result(monkeypatch):
    _patch_market(monkeypatch)

    results = run.run("india", ["baseline"], years=5)

    assert isinstance(results, list) and len(results) == 1
    result = results[0]
    assert result.policy_name == "baseline"
    # metrics.summarize keys are all present (the engine merges its counters in too).
    assert EXPECTED_METRIC_KEYS <= set(result.metrics)
    assert "rotations_triggered" in result.metrics
    assert "signals_skipped_no_cash" in result.metrics
    # The engine marks equity every day in the cache -> the curve is never empty.
    assert result.equity_curve


# --------------------------------------------------------------------------------------
# run() — compare: one Result per requested policy, in order, on the same cache.
# --------------------------------------------------------------------------------------
def test_run_compare_returns_one_result_per_policy(monkeypatch):
    _patch_market(monkeypatch)

    results = run.run("india", ["baseline", "rotation"], years=5)

    assert [r.policy_name for r in results] == ["baseline", "rotation"]
    for result in results:
        assert EXPECTED_METRIC_KEYS <= set(result.metrics)
        assert result.equity_curve


# --------------------------------------------------------------------------------------
# english_tree — generated from the rule descriptions: names the rule AND its filled param.
# --------------------------------------------------------------------------------------
def test_english_tree_is_generated_from_rule_descriptions():
    tree = report.english_tree(_rotation_policy())

    # The rotation RULE NAME appears (read off the policy) ...
    assert "nearest_to_target_band" in tree
    # ... and its description is filled with the policy's params: start=10 -> "within 10%".
    assert "within 10%" in tree
    # The policy header and every rule branch are present.
    assert tree.startswith("Policy: rotation")
    for label in ("Capital:", "Sizing:", "Selection:", "Rotation:", "Exit:"):
        assert label in tree


# --------------------------------------------------------------------------------------
# comparison_table — exactly one row per policy.
# --------------------------------------------------------------------------------------
def test_comparison_table_has_one_line_per_policy(monkeypatch):
    _patch_market(monkeypatch)
    results = run.run("india", ["baseline", "rotation"], years=5)

    table = report.comparison_table(results)
    lines = table.splitlines()

    # Each policy name lands on exactly one row (the header/rule lines carry neither).
    assert sum(1 for ln in lines if "baseline" in ln) == 1
    assert sum(1 for ln in lines if "rotation" in ln) == 1
    # Header + rule line + one row per policy.
    assert len(lines) == 2 + len(results)
    assert lines[0].startswith("Policy")


def test_metrics_table_renders_all_rows_for_a_policy(monkeypatch):
    _patch_market(monkeypatch)
    result = run.run("india", ["baseline"], years=5)[0]

    block = report.metrics_table(result)

    assert block.startswith("Metrics: baseline")
    # The derived + counter rows report.py is responsible for are all present.
    for label in ("Total return", "Max drawdown", "Profit factor", "# trades",
                  "Rotations triggered", "Signals skipped (no cash)",
                  "Capital utilization", "Avg holding days"):
        assert label in block
