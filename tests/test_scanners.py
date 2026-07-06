"""
Acceptance for the scanner registry (T2.1 / T2.2 / T2.3).

nsv2 self-registers on import, exposes the existing engine unchanged, and unknown names raise a
clear error. Importing `pinescan.scanners` (here via `from pinescan.scanners import registry`) runs
the package __init__, which registers every scanner.
"""
import pytest

from pinescan import nsv2_engine
from pinescan.scanners import registry


def test_nsv2_self_registered_and_wraps_engine():
    assert "nsv2" in registry.list_scanners()
    sc = registry.get("nsv2")                       # default name is "nsv2"
    assert sc.run is nsv2_engine.run                # the registered run IS the engine (byte-identical)
    # the LIVE scanner runs the chart-verified V2.1 rules ON TOP of the engine defaults
    # (engine DEFAULTS keep them off so the legacy golden masters stay valid as regression)
    assert sc.default_params == dict(nsv2_engine.DEFAULTS,
                                     retireMissed=True, seedPivotFix=True)
    assert sc.swing_levels is nsv2_engine.swing_levels


def test_get_unknown_lists_available():
    with pytest.raises(KeyError) as e:
        registry.get("does_not_exist")
    assert "nsv2" in str(e.value)                   # the error names what IS available


def test_register_then_list_then_cleanup():
    dummy = registry.Scanner(name="dummy", display="D", description="", timeframe="1D",
                             default_params={}, min_bars=1, run=lambda df, p: {},
                             swing_levels=lambda a, b, p: {}, scan_symbol=lambda s, df, p: None)
    registry.register(dummy)
    assert "dummy" in registry.list_scanners() and registry.get("dummy") is dummy
    registry._SCANNERS.pop("dummy")                 # don't leak into other tests
