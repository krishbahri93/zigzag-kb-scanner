"""
contracts.py — the shared vocabulary every backtester unit speaks.
==================================================================

These two dataclasses are the ONLY types passed between units, so each unit can be
built and tested in isolation against them. If you change a field here, update the
producer/consumer noted below.

  Trade     produced by events.py (from the engine's signals); consumed by engine.py
  Position  produced by portfolio.py when a Trade is opened; consumed by the rules
"""
from dataclasses import dataclass
from typing import Optional

import pandas as pd


@dataclass
class Trade:
    """One swing's full trade lifecycle, exactly as the V2 engine computed it.

    events.py emits one Trade per (symbol, swing) whose V2 entry fired. The price
    levels are FIXED at entry (they never move), so the simulator can decide whether
    to actually take the trade and how to manage capital around it. `natural_*`
    describe V2's OWN outcome ignoring capital limits — the simulator may exit earlier
    (rotation) but never later.
    """
    symbol: str
    swing: str                       # which nested swing fired: "T1".."T4"
    entry_date: pd.Timestamp         # bar the V2 entry triggered (close crossed 0.382)
    entry_price: float               # fill price (signal-bar close; slippage added in costs.py)
    target: float                    # take-profit level (0.618 of the A-B range)
    sl: float                        # stop level (0.236 of the A-B range)
    natural_exit_date: Optional[pd.Timestamp] = None  # bar V2 hit TP/SL; None = open at data end
    natural_outcome: str = "open"    # "tp" | "sl" | "open"


@dataclass
class Position:
    """An OPEN trade the portfolio actually took — a Trade plus how much capital and
    how many shares. Created by portfolio.open(); the rules read it to decide sizing
    and rotation."""
    trade: Trade
    notional: float                  # rupees allocated to this position
    qty: float                       # notional / entry_price (shares)
    opened: pd.Timestamp             # date the simulator opened it (>= trade.entry_date)


@dataclass
class ClosedTrade:
    """A finished position — the record metrics.py consumes. Produced by
    portfolio.close(). This is the hand-off shape between portfolio.py and metrics.py,
    so keep both in sync if you change it.

    `outcome`: "tp"/"sl" = V2's natural exit hit; "rotated" = sold early to free
    capital for another entry; "open_at_end" = still open when the backtest ended
    (marked to the last available price).
    """
    symbol: str
    swing: str
    entry_date: pd.Timestamp
    exit_date: pd.Timestamp
    entry_price: float
    exit_price: float
    notional: float
    pnl: float                       # rupees, net of costs
    r: float                         # R-multiple = pnl / (entry-to-sl risk)
    outcome: str                     # "tp" | "sl" | "rotated" | "open_at_end"
