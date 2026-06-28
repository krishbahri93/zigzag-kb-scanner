"""
free_capital_first.py — selection rule: consider every fresh signal.
====================================================================

WHAT IT DOES
  The permissive default pre-filter: it says "yes, consider this signal" for every
  trade. It deliberately does NOT look at cash or the position cap — those are
  enforced downstream by the simulator (cash) and the rotation rule (the
  max_concurrent cap). Keeping selection dumb means the capital logic lives in
  exactly one place instead of being split across two rules.

WHEN THE SIMULATOR CALLS IT
  engine.py calls should_take() for each new V2 signal on the day it fires, BEFORE
  any sizing/rotation, to discard signals a policy never wants. This rule discards
  none — every signal moves on to the capital checks.

HOW TO MAKE A VARIANT
  Copy this file to rules/selection/<your_name>.py, change the @register name, and
  return False to skip signals — e.g. only take certain swings (`signal.swing in
  {...}`) or skip a symbol already held. Then list "<your_name>" under "selection".
"""
from ..base import SelectionRule
from ..registry import register


@register("selection", "free_capital_first")
class FreeCapitalFirst(SelectionRule):
    """Take every signal into consideration; let cash and the position cap gate it
    downstream rather than filtering anything here."""

    description = "Consider every fresh signal; cash and the position cap gate it downstream."

    def __init__(self):
        # No tunables: this rule holds no state and accepts everything.
        pass

    def should_take(self, portfolio, signal):
        # Always consider the signal; the simulator + rotation decide if it fits.
        return True
