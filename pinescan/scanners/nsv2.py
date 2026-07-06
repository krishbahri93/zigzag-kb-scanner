"""
nsv2.py — register the V2 indicator (ZZ KB Nested Swings V2) as scanner "nsv2".
===============================================================================

Wraps the existing, parity-verified `nsv2_engine` + `nsv2_scanner` into the Scanner contract (see
registry.py). The heavy code stays in `pinescan/nsv2_engine.py` / `nsv2_scanner.py` — this module is
only the registry adapter, so nsv2 plugs into the live scan, the forward-test, and the UI exactly
like any future scanner will. Imported by `pinescan/scanners/__init__.py` so it self-registers.
"""
from .registry import Scanner, register
from .. import nsv2_engine, nsv2_scanner

register(Scanner(
    name="nsv2",
    display="Nested Daily Long (V2)",   # -> "V2.1" when the retire-missed + seed-pivot rules land via parity
    description="Nested ZigZag swings with fib entry/target/stop bands (faithful Pine port).",
    timeframe="1D",
    default_params=nsv2_engine.DEFAULTS,
    min_bars=nsv2_scanner.MIN_BARS,
    run=nsv2_engine.run,
    swing_levels=nsv2_engine.swing_levels,
    scan_symbol=nsv2_scanner.scan_symbol,
))
