"""
scanner_default.py — exit rule: no extra exit beyond V2's own TP/SL.
====================================================================

WHAT IT DOES
  The default exit policy: it adds NO exit of its own. Every open position rides
  until V2's parity-verified target or stop is hit (the simulator applies those
  unconditionally). should_exit() therefore always returns False. Both shipped
  policies use this — the backtester layers capital management on V2's signals
  without second-guessing when a trade ends.

WHEN THE SIMULATOR CALLS IT
  engine.py calls should_exit() once per open position per day, AFTER checking V2's
  TP/SL, to let a policy force an extra early exit. This rule never does.

HOW TO MAKE A VARIANT
  Copy this file to rules/exit/<your_name>.py, change the @register name, and return
  True to force-close — e.g. a time stop (`date - position.opened > N days`) or a
  trailing exit computed off `price`. Then list "<your_name>" under "exit" in a policy.
"""
from ..base import ExitRule
from ..registry import register


@register("exit", "scanner_default")
class ScannerDefault(ExitRule):
    """No extra exit — positions leave only on V2's own target or stop."""

    description = "Exit on V2's own target or stop; no extra exit."

    def should_exit(self, position, price, date):
        # Never force an early exit; V2's TP/SL (applied by the simulator) govern.
        return False
