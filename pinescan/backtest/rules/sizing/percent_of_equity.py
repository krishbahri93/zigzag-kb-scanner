"""
percent_of_equity.py — sizing rule: a fraction of the CURRENT book, so wins compound.
=====================================================================================

WHAT IT DOES
  Allocates pct% of the book's CURRENT value to each new trade. Unlike
  percent_of_capital (which fixes the rupee amount off the STARTING capital once,
  at construction), this re-reads the portfolio at every entry — as equity grows,
  positions grow with it. This is the true-compounding sizer the Automation Lab
  needed: a fixed Rs 2L slot is 10% of a Rs 20L account but only 5% once the
  account has doubled, silently de-risking the strategy over time.

BOOK VALUE, DELIBERATELY
  "Current value" here = cash + the notional locked in open positions (cost basis),
  NOT marked-to-market equity. Cost basis needs no price lookups, is identical for
  long and short margin locks, and can't feed today's unrealised P&L back into
  today's sizing — a small, conservative, deterministic choice.

WHEN THE SIMULATOR CALLS IT
  engine.py calls position_size() once per accepted signal; the engine still gates
  the result by available cash (no leverage), so a full book simply skips.
"""
from ..base import SizingRule
from ..registry import register


@register("sizing", "percent_of_equity")
class PercentOfEquity(SizingRule):
    """Allocate pct% of the current book value (cash + locked notional) per trade —
    positions scale up as the account compounds (and down after losses)."""

    description = "Allocate {pct}% of the CURRENT book value per trade (compounding)."

    def __init__(self, pct, total_capital=None):
        # `total_capital` is accepted (build_rules passes it to every sizing rule)
        # but unused: sizing must track the LIVE book, not the starting number.
        self.pct = pct

    def position_size(self, portfolio, signal):
        book = portfolio.cash + sum(p.notional for p in portfolio.positions.values())
        return book * self.pct / 100.0
