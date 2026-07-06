"""
rules/selection — signal pre-filter rules (should we take this signal at all?).
==============================================================================

The simulator (engine.py) calls the chosen selection rule's should_take() for each
fresh V2 signal, before sizing/rotation, to drop signals a policy never wants. This
package IMPORTS every selection-rule module so each runs its
@register("selection", ...) at load time and can be named from a policy JSON.

ADD A SELECTION RULE
  1. drop a new file in this folder (copy free_capital_first.py as a template)
  2. add one import line below so it self-registers on load
  3. name it under "selection" in a policy JSON
"""
from . import free_capital_first  # noqa: F401  (imported only for its @register side effect)
from . import entry_filters       # noqa: F401  (Automation Lab: Krish's signal-day judgment)
