"""
costs.py — turns a trade's rupee notional into the friction it really costs.
============================================================================

ROLE IN THE FLOW
  engine.py opens and closes Positions; every fill loses a little to brokerage,
  slippage, and (on sells) India's Securities Transaction Tax. This unit is the ONE
  place that knows those numbers, so the simulator can subtract realistic costs from
  P&L instead of trading frictionless. metrics.py then reports the net result.

CONSUMES   a policy's `costs` dict: {brokerage_pct, slippage_pct, stt_pct}
           (see rules/registry.py Policy.costs and policies/baseline.json).
EXPOSES    CostModel, with entry_cost / exit_cost / round_trip — all in rupees.

THE MODEL (kept boring and predictable on purpose)
  * Rates are PERCENT of notional: 0.03 means 0.03%, i.e. 0.03/100 of the rupee value
    traded. So one component costs `notional * pct / 100` rupees.
  * A BUY (entry) pays brokerage + slippage.
  * A SELL (exit) pays brokerage + slippage + STT. In India STT is levied on the SELL
    side only — that is exactly why entry carries no STT.
  * All-zero rates => zero cost => a frictionless backtest (a useful baseline run).

HOW TO EXTEND (e.g. add an exchange charge or GST)
  1. add a `<name>_pct` parameter to __init__ (and read it in from_policy),
  2. include it as one more `self._pct(notional, self._name_pct)` term in entry_cost
     and/or exit_cost, depending on which side of the trade it applies to.
  Each component is summed as its own rupee amount (we never add percentages together
  first), so a new term never disturbs the existing ones.
"""


class CostModel:
    """Computes the rupee friction on a trade from percent-of-notional rates.

    Build it directly (CostModel(brokerage_pct=0.03, ...)) or, the usual way, from a
    policy via CostModel.from_policy(policy.costs). Every rate defaults to 0, so an
    omitted cost simply contributes nothing.
    """

    def __init__(self, brokerage_pct=0.0, slippage_pct=0.0, stt_pct=0.0):
        """Store the rates. Each is a PERCENT of notional (0.05 == 0.05%), NOT a
        fraction — see the module header. Defaults of 0 give a frictionless model."""
        self.brokerage_pct = brokerage_pct
        self.slippage_pct = slippage_pct
        self.stt_pct = stt_pct

    @classmethod
    def from_policy(cls, costs):
        """Build a CostModel from a policy's `costs` dict (registry.Policy.costs).
        Missing keys default to 0.0, so a policy may list only the costs it cares about
        — or omit `costs` entirely (load_policy then hands us {}) for a frictionless run."""
        return cls(
            brokerage_pct=costs.get("brokerage_pct", 0.0),
            slippage_pct=costs.get("slippage_pct", 0.0),
            stt_pct=costs.get("stt_pct", 0.0),
        )

    @staticmethod
    def _pct(notional, pct):
        """One cost component in rupees: `pct` PERCENT of `notional`. The single place
        the /100 percent-to-rupees conversion lives, so every component reads the same."""
        return notional * pct / 100.0

    def entry_cost(self, notional):
        """Rupee cost to BUY `notional` worth of stock: brokerage + slippage. No STT —
        in India STT is charged on sells only (see exit_cost)."""
        return self._pct(notional, self.brokerage_pct) + self._pct(notional, self.slippage_pct)

    def exit_cost(self, notional):
        """Rupee cost to SELL `notional` worth: the same brokerage + slippage as a buy,
        PLUS India's sell-side STT. (Written as entry_cost + STT so the 'STT is the only
        extra on the sell' rule is visible in the code, not just the comment.)"""
        return self.entry_cost(notional) + self._pct(notional, self.stt_pct)

    def round_trip(self, notional):
        """Convenience: total rupee friction for the full buy-then-sell cycle on
        `notional` (entry_cost + exit_cost). Both legs use this same notional; when a
        position's exit value differs from entry, the simulator calls the two separately."""
        return self.entry_cost(notional) + self.exit_cost(notional)
