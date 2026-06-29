"""
pinescan.scanners — the scanner registry + every registered scanner.

Importing this package registers all scanners (each module self-registers via `registry.register`),
so `from pinescan.scanners import registry; registry.get(name)` / `registry.list_scanners()` always
sees them. To add a scanner: drop a module here (see nsv2.py) and import it below.
"""
from . import registry          # noqa: F401  (the registry API: register/get/list_scanners/Scanner)
from . import nsv2              # noqa: F401  (self-registers "nsv2" on import)
