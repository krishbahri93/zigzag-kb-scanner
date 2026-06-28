"""
pinescan.backtest — the V2 portfolio backtester.
================================================

WHAT THIS PACKAGE DOES
  Replays the parity-verified V2 scanner's signals over years of daily bars and
  simulates a real portfolio under configurable money-management RULES, so you can
  compare investment "policies" (e.g. with vs without capital rotation) on the same
  history and see which makes more money at acceptable risk.

THE FLOW (how a backtest runs)
    market cache (daily bars)                      policy JSON (rules + params)
          |                                              |
          v                                              v
    events.trades_for(df) --> per-symbol Trades   registry.build_rules() --> rule instances
          |                                              |
          +----------------> engine.run_backtest() <-----+
                                  |  walks the daily timeline; each day marks open
                                  |  positions, closes V2 TP/SL, opens new signals
                                  |  subject to the rules (sizing/selection/rotation)
                                  v
                           Portfolio (cash, positions, equity curve)
                                  |
                                  v
                           metrics.summarize() --> report.py (table + English rule-tree)

UNIT MAP (one file per concern; see each file's header for details)
  contracts.py   the shared vocabulary: Trade, Position
  events.py      engine output -> [Trade]              (read-only on nsv2_engine)
  portfolio.py   cash / positions / equity curve
  rules/         the money-management rules + registry  (the part you tune)
  costs.py       brokerage / slippage / STT
  metrics.py     performance stats from the equity curve
  engine.py      the day-by-day simulator (ties it together)
  report.py      human output + the generated English rule-tree
  run.py         CLI: python -m pinescan.backtest.run --market india --policy baseline

HOW TO MAKE COMMON CHANGES
  * tune capital/sizing            -> edit a policy JSON in policies/
  * add a new rule behavior        -> add a file in rules/<category>/ (it self-registers)
                                      + reference its name in a policy JSON
  * change what counts as a trade  -> events.py
  * add a metric                   -> metrics.py

  V2's entry/TP/SL signals are FIXED (parity-verified) — the backtester only layers
  money/portfolio management on top; it never changes the signals.
"""
