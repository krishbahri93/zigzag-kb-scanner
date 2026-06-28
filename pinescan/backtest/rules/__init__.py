"""
pinescan.backtest.rules — the money-management rules (the tunable part).
=======================================================================

A "policy" (a JSON file in ../policies/) picks one rule per category; the simulator
calls that rule at the matching decision point. Categories and when each fires:

  sizing      how much capital to put in a new trade        (SizingRule.position_size)
  selection   should we take this signal at all?            (SelectionRule.should_take)
  rotation    full up? free capital by closing a position   (RotationRule.free_capital)
  exit        extra exit beyond V2's TP/SL (default: none)  (ExitRule.should_exit)

HOW TO ADD A RULE (e.g. a new rotation strategy)
  1. create rules/<category>/<your_name>.py
  2. subclass the matching hook from base.py, set a plain-English `description`,
     implement the method, and decorate the class:
        @register("<category>", "<your_name>")
  3. import it from rules/<category>/__init__.py so it self-registers on load
  4. reference "<your_name>" in a policy JSON under that category

  base.py    = the hook interfaces (what each rule must implement)
  registry.py = name<->class wiring + policy loading (load_policy / build_rules)
"""
