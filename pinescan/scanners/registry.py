"""
registry.py — the scanner registry: how a ported Pine indicator plugs into the whole app.
=========================================================================================

ROLE IN THE FLOW
  A "scanner" is one ported Pine indicator (e.g. nsv2 = ZZ KB Nested Swings V2). Each is described
  by a `Scanner` record and self-registers here on import. Everything that consumes signals — the
  live scan (`service.scan_market`), the backtest/forward engine (`events.trades_for`), and the web
  UI (scanner selector) — looks scanners up here, so ADDING a scanner needs NO edits to those
  callers. Mirrors `backtest/rules/registry.py` (rules self-register the same way).

THE CONTRACT a scanner must satisfy (so the generic engine/scan code works unchanged):
  run(df, params) -> dict          per-bar series B / A0..A3 / ST0..ST3 / ENTRY / TP / SL (+ plots)
  swing_levels(a, b, params) -> dict   derive a swing's price levels from its A (peak) + B (base);
                                       MUST include "tL" (take-profit) and "sl" (stop)
  scan_symbol(sym, df, params) -> dict|None   last-bar actionable Setup row for the live scanner
  default_params: dict             the indicator's DEFAULTS (merged under any caller overrides)
  min_bars: int                    minimum history before a setup can confirm

TO ADD A SCANNER
  1. Port the Pine to Python with the golden-CSV parity gate (PINE_PORTING.md / `python -m
     pinescan.core lint|parity`).
  2. Add `pinescan/scanners/<name>.py` that builds a `Scanner(...)` and calls `register(...)`.
  3. Import it from `pinescan/scanners/__init__.py` so it self-registers.
  It then appears in the live scan, the forward-test, and the UI selector automatically.
"""
from dataclasses import dataclass


@dataclass
class Scanner:
    """One ported Pine indicator. See the module header for the contract each callable satisfies."""
    name: str                      # registry key, e.g. "nsv2"
    display: str                   # human label, e.g. "ZZ KB Nested Swings V2"
    description: str
    timeframe: str                 # e.g. "1D"
    default_params: dict
    min_bars: int
    run: object                    # run(df, params) -> dict (the per-bar series)
    swing_levels: object           # swing_levels(a, b, params) -> {tL, sl, ...}
    scan_symbol: object            # scan_symbol(sym, df, params) -> dict | None
    side: str = "long"             # trade direction: "long" | "short" (the backtester
                                   # mirrors targets/stops/features for short scanners)


_SCANNERS = {}


def register(scanner):
    """Register a Scanner under its `name` (idempotent — re-registering replaces, so module reloads
    stay safe)."""
    _SCANNERS[scanner.name] = scanner


def get(name="nsv2"):
    """Return the registered Scanner, or raise with the list of what IS available."""
    try:
        return _SCANNERS[name]
    except KeyError:
        avail = ", ".join(sorted(_SCANNERS)) or "(none)"
        raise KeyError(f"no scanner '{name}'. Registered: {avail}")


def list_scanners():
    """Registered scanner names, sorted (the UI selector + service iterate this)."""
    return sorted(_SCANNERS)
