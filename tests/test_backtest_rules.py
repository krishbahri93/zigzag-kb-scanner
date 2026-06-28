"""
Acceptance test for U5 — the rules hierarchy (the tunable money-management layer).
=================================================================================

Guards the behavior the simulator depends on:
  * nearest_to_target_band picks the in-band position CLOSEST to target, and widens
    the band step-by-step up to `max` before giving up,
  * none frees nothing,
  * the `rotation` policy resolves to four live rule instances via build_rules().

The rotation rules only read two things off a portfolio — a `.positions` mapping and
distance_to_target() — so a tiny fake stands in for the real Portfolio (a separate
unit), letting us place positions at exact distances along the entry->target path.
"""
import pathlib

from pinescan.backtest.rules import registry
from pinescan.backtest.rules.base import (
    SizingRule, SelectionRule, RotationRule, ExitRule,
)
from pinescan.backtest.rules.rotation.nearest_to_target_band import NearestToTargetBand
from pinescan.backtest.rules.rotation.none import NoRotation

POLICIES = pathlib.Path(__file__).resolve().parent.parent / "pinescan" / "backtest" / "policies"


class FakePortfolio:
    """Minimal stand-in for the real Portfolio: just the two things a rotation rule
    reads. `distance_to_target` returns a preset progress per symbol (ignoring price,
    which the real portfolio would use), so each test can place positions at chosen
    distances: 0 = at entry, 1 = at target."""

    def __init__(self, distances):
        self._distances = dict(distances)                     # symbol -> distance (0..1)
        self.positions = {sym: object() for sym in distances}  # the rule only iterates keys

    def distance_to_target(self, sym, price):
        # Preset for the test; the real portfolio computes this from price vs target.
        return self._distances[sym]


def _prices(pf):
    """A price per open position (value is irrelevant — the fake ignores it)."""
    return {sym: 100.0 for sym in pf.positions}


def test_nearest_picks_closest_in_band():
    # Three positions at increasing distance-from-entry toward their targets.
    pf = FakePortfolio({"AAA": 0.95, "BBB": 0.85, "CCC": 0.5})
    rule = NearestToTargetBand(start=10, step=10, max=40)
    # band=10 -> threshold 0.90: only AAA (0.95) is in-band, and it's closest to target.
    assert rule.free_capital(pf, needed=200000, prices=_prices(pf), date=None) == ["AAA"]


def test_nearest_picks_max_distance_among_multiple_in_band():
    # With a wider start both AAA and BBB are in-band; it must pick the closer one.
    pf = FakePortfolio({"AAA": 0.95, "BBB": 0.85, "CCC": 0.5})
    rule = NearestToTargetBand(start=20, step=10, max=40)   # band=20 -> threshold 0.80
    assert rule.free_capital(pf, needed=200000, prices=_prices(pf), date=None) == ["AAA"]


def test_nearest_widens_band_until_target_reached():
    # A single position only halfway to target.
    pf = FakePortfolio({"CCC": 0.5})
    # Default ceiling 40% -> widest threshold is 0.60; 0.5 never qualifies -> [].
    narrow = NearestToTargetBand(start=10, step=10, max=40)
    assert narrow.free_capital(pf, needed=200000, prices=_prices(pf), date=None) == []
    # Raise the ceiling to 60%: at band=50 the threshold is 0.50, so 0.5 qualifies.
    wide = NearestToTargetBand(start=10, step=10, max=60)
    assert wide.free_capital(pf, needed=200000, prices=_prices(pf), date=None) == ["CCC"]


def test_none_frees_nothing():
    pf = FakePortfolio({"AAA": 0.95})
    assert NoRotation().free_capital(pf, needed=200000, prices=_prices(pf), date=None) == []


def test_rotation_policy_builds_four_rules():
    # The shipped rotation policy must resolve to one live instance per category.
    policy = registry.load_policy(POLICIES / "rotation.json")
    rules = registry.build_rules(policy)

    assert set(rules) == {"sizing", "selection", "rotation", "exit"}
    assert isinstance(rules["sizing"], SizingRule)
    assert isinstance(rules["selection"], SelectionRule)
    assert isinstance(rules["rotation"], RotationRule)
    assert isinstance(rules["exit"], ExitRule)

    # Params flowed from the JSON onto the instances.
    assert rules["sizing"].amount == policy.sizing_params["amount"]
    assert (rules["rotation"].start, rules["rotation"].step, rules["rotation"].max) == (10, 10, 40)
