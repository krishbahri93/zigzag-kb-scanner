"""
Acceptance test for U0 — the backtester's contract keystone.

Every other backtest unit is built against contracts.py + rules/base.py + the registry,
so this guards the shared vocabulary: contracts construct, both shipped policies parse,
and the registry resolves a registered rule while rejecting unknown names.
"""
import pathlib

import pytest

from pinescan.backtest import contracts
from pinescan.backtest.rules import base, registry

POLICIES = pathlib.Path(__file__).resolve().parent.parent / "pinescan" / "backtest" / "policies"


def test_contracts_construct():
    t = contracts.Trade(symbol="X", swing="T1", entry_date=None, entry_price=100.0,
                        target=120.0, sl=95.0)
    assert t.natural_outcome == "open" and t.target == 120.0      # defaults + fields
    p = contracts.Position(trade=t, notional=200000, qty=2000, opened=None)
    assert p.trade is t and p.notional == 200000


def test_policies_parse():
    base_pol = registry.load_policy(POLICIES / "baseline.json")
    assert (base_pol.total_capital, base_pol.sizing_params["amount"], base_pol.max_concurrent) == (2000000, 200000, 10)
    assert base_pol.rotation == "none"
    rot = registry.load_policy(POLICIES / "rotation.json")
    assert rot.rotation == "nearest_to_target_band" and rot.rotation_params["start"] == 10


def test_registry_resolves_and_rejects():
    # a dummy rule self-registers, get_rule finds it, and an unknown name raises clearly
    @registry.register("sizing", "_dummy")
    class _Dummy(base.SizingRule):
        description = "test only"
        def __init__(self, amount=0): self.amount = amount
        def position_size(self, portfolio, signal): return self.amount

    assert registry.get_rule("sizing", "_dummy") is _Dummy
    with pytest.raises(KeyError):
        registry.get_rule("rotation", "does_not_exist")
