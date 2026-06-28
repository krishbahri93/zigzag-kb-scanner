"""
rules/rotation — capital-rotation rules (when full, what to sell to fund a new entry?).
======================================================================================

The simulator (engine.py) calls the chosen rotation rule's free_capital() ONLY when
the portfolio is full (max_concurrent reached) and a fresh signal wants in; the rule
returns the symbols to close to make room (or [] to skip the new signal). This
package IMPORTS every rotation-rule module so each runs its @register("rotation", ...)
at load time and can be named from a policy JSON.

ADD A ROTATION RULE
  1. drop a new file in this folder (copy nearest_to_target_band.py as a template)
  2. add one import line below so it self-registers on load
  3. name it under "rotation" in a policy JSON
"""
from . import none                     # noqa: F401  (imported only for @register side effect)
from . import nearest_to_target_band   # noqa: F401  (imported only for @register side effect)
