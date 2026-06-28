"""
percent_of_capital.py — sizing rule: put a FIXED PERCENT of capital into each trade.
====================================================================================

WHAT IT DOES
  Allocates `pct`% of the policy's total capital to every position. With a fixed ₹20L
  capital, "10%" = a constant ₹2,00,000 — the same money as fixed_amount(200000), but
  expressed as a fraction so you can reason in percentages. It sizes off the STARTING
  capital (not live equity), so it does not compound within a single run.

WHEN THE SIMULATOR CALLS IT
  engine.py calls position_size() once per opened trade to learn the rupee notional.

HOW TO MAKE A VARIANT
  For percent-of-LIVE-equity (compounding), read the equity off `portfolio` at call
  time inside position_size() instead of using the fixed starting amount.
"""
from ..base import SizingRule
from ..registry import register


@register("sizing", "percent_of_capital")
class PercentOfCapital(SizingRule):
    """Allocate a fixed percentage of total capital to every trade. build_rules() passes
    `pct` from the policy's sizing.params and `total_capital` from the policy."""

    description = "Allocate {pct}% of capital per trade."

    def __init__(self, pct, total_capital):
        # pct = percent (e.g. 10 means 10%); the rupee amount is fixed off the
        # starting capital, so every trade gets the same notional within a run.
        self.pct = pct
        self.amount = total_capital * pct / 100.0

    def position_size(self, portfolio, signal):
        # Constant notional (pct% of starting capital) — ignores live equity and signal.
        return self.amount
