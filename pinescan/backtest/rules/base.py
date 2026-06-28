"""
base.py — the rule hook interfaces the simulator calls.
=======================================================

The simulator (engine.py) only ever sees these base types — it never knows which
CONCRETE rule is plugged in. That indirection is what lets you swap behaviors by
editing a policy JSON instead of touching the simulator.

To implement a rule: subclass the right hook, set `description`, override the one
method. See rules/__init__.py for the full add-a-rule recipe, and registry.py for how
a rule name in a policy becomes one of these instances.
"""


class Rule:
    """Base for every rule. `description` is plain English rendered into the report's
    rule tree; use {param} placeholders and report.py fills them from the policy params
    (so the English you read is generated from the code that ran — they can't drift)."""
    description = ""


class SizingRule(Rule):
    """Decides how much capital a new trade gets. Constructed with the policy's
    capital params (e.g. `amount` = per_trade)."""
    def position_size(self, portfolio, signal):
        """Return the rupee notional to allocate to `signal` (a Trade). Called only
        once the simulator has decided to open it. `portfolio` is available so size
        can depend on current equity if a rule wants."""
        raise NotImplementedError


class SelectionRule(Rule):
    """A cheap pre-filter: should we even consider this signal? (Capital limits are
    enforced separately by the simulator + rotation rule, not here.)"""
    def should_take(self, portfolio, signal):
        """Return True to consider opening `signal` (a Trade), else False to ignore it."""
        raise NotImplementedError


class RotationRule(Rule):
    """When the portfolio is full and a new signal fires, decide which open
    position(s) to close to free capital for it."""
    def free_capital(self, portfolio, needed, prices, date):
        """Return a list of symbols to CLOSE to free at least `needed` rupees.
        `prices` = {symbol: today's close} for marking positions. Return [] to free
        nothing (the new signal is then skipped). The simulator performs the actual
        closes and counts a rotation."""
        raise NotImplementedError


class ExitRule(Rule):
    """Optional EXTRA exit on top of V2's own TP/SL (which always apply). Default does
    nothing; override for e.g. a time-based or trailing exit."""
    def should_exit(self, position, price, date):
        """Return True to force-close `position` today at `price`. Default: never."""
        return False
