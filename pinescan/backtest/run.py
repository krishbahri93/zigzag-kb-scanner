"""
run.py — the backtester CLI: pick a market + policy, replay it, print the report.
=================================================================================

ROLE IN THE FLOW (see backtest/__init__.py for the whole picture)
  This is the ENTRY POINT a human (or CI) invokes. It is glue only: it loads a market's
  daily cache once, runs each requested policy through engine.run_backtest, and hands the
  Policy/Result to report.py to print. No trading logic lives here.

      _load_market(market, years) ─ daily-bar cache (one market's universe)
                                          │  (loaded ONCE, reused for every policy)
      policies/<name>.json ─ load_policy ─┤
                                          v
                              engine.run_backtest(cache, policy) ─> Result
                                          │
                                          v
              report.english_tree(policy) + report.metrics_table(result)
                              (+ report.comparison_table when --compare)

USAGE
    python -m pinescan.backtest.run                          # india, baseline, 5y
    python -m pinescan.backtest.run --market us --policy baseline
    python -m pinescan.backtest.run --compare baseline rotation   # side-by-side
    python -m pinescan.backtest.run --years 3 --policy rotation

  --market {india,us}   which data layer to load (default india)
  --policy NAME         a file stem in policies/ (default baseline); ignored if --compare
  --compare NAME ...    run several policies and also print the comparison table
  --years N             trim each symbol's history to its last N years (default 5)

TESTABILITY
  run(market, policy_names, years) does the load-once-then-replay work and returns the
  list of Results with NO argv and NO printing, so a test can drive it directly (and
  monkeypatch _load_market to inject a tiny synthetic cache). main() is the thin
  argv/printing wrapper around it.

HOW TO EXTEND
  * add a market   -> add a branch in _load_market (load its universe + daily cache to
                      {symbol: OHLCV df}); everything downstream is market-agnostic.
  * add a policy   -> drop a JSON in policies/ and pass its stem to --policy/--compare;
                      no code change here.
  * change history -> MIN_BARS (the too-little-history cutoff) and the --years trim are
                      the only data-shaping knobs; both live in _load_market.
"""
import os
import sys

# Windows consoles default to cp1252, which can't encode the ₹ / box-drawing glyphs in
# the English rule-tree. Force UTF-8 before anything prints (mirrors scripts/refresh_data.py).
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

import argparse

import pandas as pd

from . import report
from .engine import run_backtest
from .rules.registry import load_policy

# Where policy JSONs live (this file's sibling policies/ dir).
POLICIES_DIR = os.path.join(os.path.dirname(__file__), "policies")

# Drop symbols with fewer than this many daily bars of history — too little to produce a
# meaningful V2 setup, and they only add noise to the run.
MIN_BARS = 60


def _policy_path(name):
    """Resolve a policy file stem to its JSON path, or raise a useful error.

    Mirrors registry.get_rule's "list what IS available" style so a typo in --policy
    names the valid stems instead of a bare FileNotFoundError.
    """
    path = os.path.join(POLICIES_DIR, f"{name}.json")
    if not os.path.exists(path):
        avail = ", ".join(sorted(
            os.path.splitext(f)[0]
            for f in os.listdir(POLICIES_DIR) if f.endswith(".json")
        )) or "(none)"
        raise FileNotFoundError(f"no policy '{name}' in {POLICIES_DIR}. Available: {avail}")
    return path


def _load_market(market, years):
    """Load one market's daily cache, filter thin histories, trim to the last `years`.

    Returns {symbol: OHLCV DataFrame} ready for engine.run_backtest — the SAME shape both
    market loaders already produce, so the engine never knows which market it ran.

    To add a market, add a branch here that yields its (symbols -> daily df) cache; the
    filter/trim below is market-agnostic and applies to whatever the branch returns.
    """
    if market == "india":
        from ..markets import india
        symbols, _sectors = india.get_universe()
        cache = india.load_cache(symbols)
    elif market == "us":
        from ..markets import us
        symbols, _sectors = us.select_liquid_universe()
        cache = us.load_cache(symbols)
    else:
        raise ValueError(f"unknown market '{market}'. Use 'india' or 'us'.")

    trimmed = {}
    for sym, df in cache.items():
        if df is None or len(df) < MIN_BARS:
            continue                              # too little history -> skip the symbol
        df = df.sort_index()                      # ensure chronological before we window
        # Keep only the last `years` calendar years of bars. DateOffset(years=...) is
        # tz-safe, so this works on both the Asia/Kolkata and America/New_York indices.
        cutoff = df.index.max() - pd.DateOffset(years=years)
        trimmed[sym] = df.loc[df.index >= cutoff]
    return trimmed


def run(market, policy_names, years=5):
    """Replay each named policy over `market` and return their Results (no printing).

    Loads the market cache ONCE and reuses it for every policy, so a --compare run scores
    each policy on the identical bars. `policy_names` order is preserved in the output.

    Args:
        market:       "india" | "us" — selects the data layer in _load_market.
        policy_names: list of policy file stems (each resolved under policies/).
        years:        history window passed to _load_market for trimming.

    Returns:
        list[engine.Result], one per name in `policy_names`, in the same order.
    """
    cache = _load_market(market, years)           # one load, shared across policies
    results = []
    for name in policy_names:
        policy = load_policy(_policy_path(name))
        results.append(run_backtest(cache, policy))
    return results


def _parse_args(argv):
    """Build the CLI args (see the module header's USAGE for the full surface)."""
    parser = argparse.ArgumentParser(
        prog="python -m pinescan.backtest.run",
        description="Replay a V2 portfolio policy over a market's daily history "
                    "and print its rule tree + performance metrics.",
    )
    parser.add_argument("--market", choices=["india", "us"], default="india",
                        help="data layer to load (default: india)")
    parser.add_argument("--policy", default="baseline",
                        help="policy file stem in policies/ (default: baseline); "
                             "ignored when --compare is given")
    parser.add_argument("--compare", nargs="+", metavar="NAME",
                        help="run several policies and also print a comparison table")
    parser.add_argument("--years", type=int, default=5,
                        help="trim each symbol's history to its last N years (default: 5)")
    return parser.parse_args(argv)


def main(argv=None):
    """CLI wrapper: parse args, run the policies, print each report (+ comparison).

    --compare wins over --policy when both are present (you asked for several). Prints
    every policy's English rule-tree and metrics block; when more than one policy ran,
    follows with the side-by-side comparison table.
    """
    args = _parse_args(argv)
    policy_names = args.compare if args.compare else [args.policy]

    results = run(args.market, policy_names, args.years)

    # Per-policy: the generated English tree (needs the Policy) + its metrics block.
    for name, result in zip(policy_names, results):
        policy = load_policy(_policy_path(name))
        print(report.english_tree(policy))
        print()
        print(report.metrics_table(result))
        print()

    # Side-by-side only makes sense when comparing two or more policies.
    if len(results) > 1:
        print(report.comparison_table(results))


if __name__ == "__main__":
    main()
