"""
portfolio.py — the account the simulator drives: cash, open positions, equity curve.
====================================================================================

ROLE IN THE FLOW
  engine.py owns exactly ONE Portfolio per backtest run. As it walks the daily
  timeline it calls these methods and nothing else touches the account:
      can_afford() / open()   -> take a new V2 signal (the sizing rule chose notional)
      mark()                  -> end-of-day: record total equity onto the curve
      distance_to_target()    -> hand the rotation rule a 0..1 score per open position
      close()                 -> exit on V2 TP/SL, a rotation, or end-of-data
  The Portfolio holds NO rules and makes NO policy decisions — it only records what the
  simulator tells it to do, so cash and positions can never drift out of sync.

  Costs (brokerage / slippage / STT) are NOT applied here. costs.py adjusts the
  notional the simulator passes into open() and the pnl after close(); everything in
  this file is GROSS so the cash-in/cash-out math stays trivially auditable — see
  close().

CONSUMES   contracts.Trade (the fixed V2 signal) + contracts.Position (its own output)
EXPOSES    Portfolio with fields  cash, positions{symbol -> Position},
           equity_curve[(date, equity)], closed[ClosedTrade]
           -> metrics.py reads `closed` + `equity_curve` to score the run

HOW TO EXTEND
  * a new exit reason        -> pass a new `outcome` string to close(); the allowed
                                values live in the ClosedTrade contract, not here
  * size by live equity      -> the sizing rule reads portfolio.cash; this file just
                                records whatever notional it is handed
  * a different risk basis   -> close()'s `r` is the only risk math; change it there
                                and update the ClosedTrade.r note in contracts.py
"""
from .contracts import Position, ClosedTrade

# Floor for the R-multiple denominator so a degenerate trade where the stop sits at or
# above entry (entry-to-SL risk <= 0) can't divide by zero and kill a whole run. The
# engine shouldn't emit such a Trade, but we stay defensive rather than crash.
_TINY = 1e-9


class Portfolio:
    """A single backtest's brokerage account. Created once by engine.py with the
    policy's starting cash. Every rupee that moves goes through open() or close(), so
    `cash` always equals starting_cash minus capital locked in open positions plus
    realised proceeds — there is no leverage and no hidden state."""

    def __init__(self, starting_cash):
        """Start flat: all cash, no positions, empty history.

        starting_cash -- the policy's total capital (rupees). Becomes `cash`, the only
        money the portfolio can ever deploy.
        """
        self.cash = starting_cash
        self.positions = {}        # symbol -> open Position (at most one per symbol)
        self.equity_curve = []     # [(date, equity)] — one entry per marked day
        self.closed = []           # [ClosedTrade] — one per exit, in close order

    def can_afford(self, notional):
        """True if `notional` rupees are free in cash right now.

        The simulator checks this before open(); the portfolio never borrows, so an
        unaffordable signal is either skipped or sent to the rotation rule to free
        capital first.
        """
        return self.cash >= notional

    def open(self, trade, notional, price, date):
        """Take `trade`: lock `notional` rupees into a new Position and return it.

        Buys notional / price shares at `price` (the fill the simulator chose — normally
        trade.entry_price) and deducts the full notional from cash. The caller
        guarantees `trade.symbol` isn't already open, so positions[symbol] is set
        unconditionally. Returns the Position so the simulator and rules can track it.

        SHORTS use the same cash mechanics deliberately: the full notional is locked
        as margin (no leverage credit — conservative vs real F&O margins), and the
        mirrored P&L is settled at close(). One capital model for both sides keeps a
        combined long+short book's cash arithmetic trivially auditable.
        """
        qty = notional / price
        pos = Position(trade=trade, notional=notional, qty=qty, opened=date)
        self.cash -= notional
        self.positions[trade.symbol] = pos
        return pos

    def close(self, symbol, price, date, outcome):
        """Sell the open position in `symbol` at `price`, book a ClosedTrade, return it.

        Returns proceeds (qty * price) to cash and records the GROSS pnl
        (proceeds - notional). Costs are deliberately NOT subtracted here: the simulator
        applies them via costs.py, keeping this a pure cash identity that's easy to
        audit. `outcome` says WHY we exited ("tp" | "sl" | "rotated" | "open_at_end" —
        see the ClosedTrade contract).

        `r` is the R-multiple: pnl over the rupees risked from entry to the stop
        (notional - qty * sl). _TINY floors that denominator so a bad signal can't
        divide by zero. The Position is removed from `positions` and the ClosedTrade is
        appended to `closed`.
        """
        pos = self.positions[symbol]
        trade = pos.trade
        entry_fill = pos.notional / pos.qty                 # the actual fill at open
        if trade.side == "short":
            # Sold at entry_fill, bought back at `price`: margin comes home + the
            # mirrored gross P&L. Risk basis is the stop ABOVE the entry.
            pnl = (entry_fill - price) * pos.qty            # GROSS (costs added by sim)
            self.cash += pos.notional + pnl
            risk = max(pos.qty * (trade.sl - entry_fill), _TINY)
        else:
            proceeds = pos.qty * price
            self.cash += proceeds
            pnl = proceeds - pos.notional                   # GROSS (costs added by sim)
            risk = max(pos.notional - pos.qty * trade.sl, _TINY)
        closed = ClosedTrade(
            symbol=symbol,
            swing=trade.swing,
            # Book what the ACCOUNT did, not what the signal said: pos.opened is the day
            # the simulator filled, notional/qty is the actual fill price. Identical to
            # trade.entry_date/entry_price for close-fills (every legacy run); they
            # differ only under the lab's entry_fill="next_open" variant.
            entry_date=pos.opened,
            exit_date=date,
            entry_price=entry_fill,
            exit_price=price,
            notional=pos.notional,
            pnl=pnl,
            r=pnl / risk,
            outcome=outcome,
            side=trade.side,
        )
        self.closed.append(closed)
        del self.positions[symbol]
        return closed

    def mark(self, prices, date):
        """Snapshot total equity for `date` onto the equity curve; also return it.

        equity = cash + the marked value of every open position. `prices` is
        {symbol: today's close}; a symbol missing from it (e.g. no bar printed that day)
        falls back to its own entry_price, so a data gap leaves that holding flat
        instead of crashing the run. metrics.py turns the resulting curve into
        returns / drawdown.
        """
        holdings = 0.0
        for sym, pos in self.positions.items():
            px = prices.get(sym, pos.trade.entry_price)
            if pos.trade.side == "short":
                # margin locked at open + mark-to-market of the mirrored P&L
                holdings += pos.notional + (pos.notional / pos.qty - px) * pos.qty
            else:
                holdings += pos.qty * px
        equity = self.cash + holdings
        self.equity_curve.append((date, equity))
        return equity

    def distance_to_target(self, symbol, price):
        """How far `symbol` has travelled from entry toward its take-profit, in [0, 1].

        0.0 at (or below) entry, 1.0 at (or above) target, linear in between. The
        rotation rule uses this to prefer closing positions nearest their target when it
        must free capital. The result is clamped so a price outside the entry->target
        band can't report < 0 or > 1; a degenerate target not above entry reports 0.0
        rather than dividing by zero.
        """
        trade = self.positions[symbol].trade
        # Progress in TRADE DIRECTION: for shorts the target sits below entry, so both
        # span and progress flip sign and the same 0..1 scale falls out.
        if trade.side == "short":
            span = trade.entry_price - trade.target
            gain = trade.entry_price - price
        else:
            span = trade.target - trade.entry_price
            gain = price - trade.entry_price
        if span <= 0:                                       # degenerate: target not beyond entry
            return 0.0
        return min(1.0, max(0.0, gain / span))              # clamp to [0, 1]
