"""
Acceptance test for U4 — the cost model (brokerage / slippage / STT).

Guards the rupee friction the simulator subtracts from P&L: entry charges
brokerage+slippage, exit adds India's sell-side STT, a zero-rate model is frictionless,
and from_policy() reads the same `costs` dict shape that policies/baseline.json uses.
"""
import pytest

from pinescan.backtest.costs import CostModel


def test_entry_exit_round_trip():
    # 0.03% brokerage + 0.05% slippage + 0.025% STT on a 2,00,000 notional
    cm = CostModel(brokerage_pct=0.03, slippage_pct=0.05, stt_pct=0.025)
    assert cm.entry_cost(200000) == pytest.approx(160.0)   # (0.03+0.05)% — buy, no STT
    assert cm.exit_cost(200000) == pytest.approx(210.0)    # +0.025% STT on the sell
    assert cm.round_trip(200000) == pytest.approx(370.0)   # entry + exit


def test_zero_rates_are_frictionless():
    cm = CostModel()                                       # all rates default to 0
    assert cm.entry_cost(200000) == 0.0
    assert cm.exit_cost(200000) == 0.0
    assert cm.round_trip(200000) == 0.0


def test_from_policy_matches_baseline_costs():
    # the exact dict shape registry.load_policy hands over (policies/baseline.json)
    cm = CostModel.from_policy({"brokerage_pct": 0.03, "slippage_pct": 0.05, "stt_pct": 0.025})
    assert cm.entry_cost(200000) == pytest.approx(160.0)
    assert cm.exit_cost(200000) == pytest.approx(210.0)
    assert cm.round_trip(200000) == pytest.approx(370.0)


def test_from_policy_defaults_missing_keys():
    # a policy may omit costs (load_policy passes {}) -> frictionless, no KeyError
    assert CostModel.from_policy({}).round_trip(200000) == 0.0
    # partial dicts fill only what's given: 0.10% of 1,00,000 = 100, no slippage/STT
    cm = CostModel.from_policy({"brokerage_pct": 0.10})
    assert cm.entry_cost(100000) == pytest.approx(100.0)
    assert cm.exit_cost(100000) == pytest.approx(100.0)    # still no STT term
