"""
nds.py — register the Daily Short mirror (Nested Daily Short V1.1) as scanner "nds".
====================================================================================

LAB-ONLY for now: this adapter exposes the chart-verified `nds_engine` to the
backtester (events.trades_for(scanner="nds")) so the Automation Lab can study the
short side. It is NOT part of the live scan — service.py fetches scanners by name
and only asks for "nsv2"; wiring shorts into the dashboard (scan_symbol, UI toggle,
alerts) is a separate parked phase, so `scan_symbol` here is a stub by design.
"""
from .registry import Scanner, register
from .. import nds_engine, nsv2_scanner


def _not_wired(sym, df, params):
    """Live scanning of shorts is a parked phase — the lab never calls this."""
    raise NotImplementedError("nds is lab-only: scan_symbol not wired into the app yet")


register(Scanner(
    name="nds",
    display="Nested Daily Short (V1.1)",
    description="Short-only mirror: nested troughs under a rally high, fib ladder measured down.",
    timeframe="1D",
    # V1.1 rules (retire-missed, seed fix) are built into nds_engine — no flags needed.
    default_params=dict(nds_engine.DEFAULTS),
    min_bars=nsv2_scanner.MIN_BARS,          # same 1D geometry/warmup as the long side
    run=nds_engine.run,
    swing_levels=nds_engine.swing_levels,
    scan_symbol=_not_wired,
    side="short",
))
