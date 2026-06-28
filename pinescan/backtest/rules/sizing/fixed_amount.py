"""
fixed_amount.py — sizing rule: put a constant rupee amount into every trade.
===========================================================================

WHAT IT DOES
  Allocates the SAME notional (rupees) to every position, regardless of price,
  conviction, or current equity. This is the simplest possible sizer and the one
  both shipped policies use: the policy JSON's capital.per_trade becomes `amount`.

WHEN THE SIMULATOR CALLS IT
  engine.py calls position_size() once, right after it has decided to open a
  signal, to learn how many rupees to commit (shares = notional / entry_price).

HOW TO MAKE A VARIANT
  Copy this file to rules/sizing/<your_name>.py, change the @register name, and
  return a different number from position_size — e.g. a fraction of current equity
  (`portfolio.equity * 0.05`) for percent-of-equity sizing, or scale by `signal`
  fields for conviction sizing. Then list "<your_name>" under "sizing" in a policy.
"""
from ..base import SizingRule
from ..registry import register


@register("sizing", "fixed_amount")
class FixedAmount(SizingRule):
    """Allocate a fixed cash amount to every trade (currency per the market). Built from the
    policy's capital.per_trade, which build_rules() passes in as `amount`."""

    description = "Allocate a fixed {currency}{amount} per trade."

    def __init__(self, amount, total_capital=None):
        # `amount` = rupees per trade from the policy's sizing.params. `total_capital`
        # is accepted (build_rules passes it to every sizing rule) but unused here.
        self.amount = amount

    def position_size(self, portfolio, signal):
        # Same notional for every trade — ignore portfolio equity and signal details.
        return self.amount
