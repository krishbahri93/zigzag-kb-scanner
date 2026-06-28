"""
none.py — rotation rule: never rotate.
======================================

WHAT IT DOES
  The "no rotation" policy: when the portfolio is full, free_capital() frees
  nothing, so a new signal is simply skipped until an existing position exits on its
  own (V2's TP/SL). This is the `baseline` policy's behavior — capital is committed
  first-come-first-served and never recycled early.

WHEN THE SIMULATOR CALLS IT
  engine.py calls free_capital() only when the portfolio is full (max_concurrent
  reached) and a new signal wants in. Returning [] tells the simulator "close
  nothing — skip the new signal."

HOW TO MAKE A VARIANT
  See nearest_to_target_band.py for a real rotation rule. Copy either file, change
  the @register name, and return the symbol(s) to close instead of [].
"""
from ..base import RotationRule
from ..registry import register


@register("rotation", "none")
class NoRotation(RotationRule):
    """Never sell an open position to fund a new entry; full means full."""

    description = "No rotation — never sell to fund a new entry."

    def __init__(self):
        # No tunables: this rule always frees nothing.
        pass

    def free_capital(self, portfolio, needed, prices, date):
        # Free nothing -> the simulator skips the new signal until a natural exit.
        return []
