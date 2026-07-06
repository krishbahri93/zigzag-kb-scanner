"""
rules/exit — extra-exit rules (force-close beyond V2's own TP/SL).
=================================================================

The simulator (engine.py) calls the chosen exit rule's should_exit() once per open
position per day, AFTER applying V2's own target/stop, to let a policy force an extra
early exit (e.g. a time stop). This package IMPORTS every exit-rule module so each
runs its @register("exit", ...) at load time and can be named from a policy JSON.

ADD AN EXIT RULE
  1. drop a new file in this folder (copy scanner_default.py as a template)
  2. add one import line below so it self-registers on load
  3. name it under "exit" in a policy JSON
"""
from . import scanner_default  # noqa: F401  (imported only for its @register side effect)
from . import lab_exits        # noqa: F401  (Automation Lab: early target / breakeven / trail)
