"""
rules/sizing — capital-sizing rules (how many rupees a new trade gets).
======================================================================

The simulator (engine.py) calls the chosen sizing rule's position_size() once per
opened trade to learn the rupee notional to commit. This package's only job is to
IMPORT every sizing-rule module so each one runs its @register("sizing", ...) at
load time and becomes referenceable by name from a policy JSON.

ADD A SIZING RULE
  1. drop a new file in this folder (copy fixed_amount.py as a template)
  2. add one import line below so it self-registers on load
  3. name it under "sizing" in a policy JSON
"""
from . import fixed_amount        # noqa: F401  (imported only for its @register side effect)
from . import percent_of_capital  # noqa: F401
from . import percent_of_equity   # noqa: F401  (Automation Lab: true compounding)
