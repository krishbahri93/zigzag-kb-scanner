"""
lab_exits — the Automation Lab's dynamic exit toolbox (early target / breakeven / trail).

One composite rule with every leg optional, so a single rule name sweeps the whole
exit grid. Evaluated daily per open position by the simulator's dynamic-exit pass
(AFTER V2's natural TP/SL pass — V2's own exit always wins its own date).

Legs (all off by default = behaves exactly like scanner_default):
  early_pct   exit when the day touches entry + early_pct% of the entry->target run
              (Krish's "don't wait for the last volatile leg")
  be_arm_r    once the BEST CLOSE has gained >= be_arm_r x initial risk, the stop
              moves to the entry price ("make the trade free")
  trail_pct   the stop follows the best close, trail_pct percent behind it

SIDES: fully mirrored. For a SHORT the run points DOWN — the early target sits below
entry (touched by the day's LOW), the stop sits ABOVE entry and only ever FALLS as
the trade works, and the trail hangs trail_pct% ABOVE the lowest close.

Discipline against lookahead & optimism (both sides):
  * stop state (best-close/breakeven/trail) updates AFTER the day's exit checks, so a
    stop can only act on information from PRIOR days;
  * the STOP check runs BEFORE the early-target check (pessimistic on double-touch days);
  * gap days fill at the day's OPEN when it opens beyond the level (worse for stops,
    better for targets — both realistic);
  * the dynamic stop only ever TIGHTENS, and never sits outside V2's own 0.236 stop.
"""
from ..base import ExitRule
from ..registry import register


@register("exit", "lab_exits")
class LabExits(ExitRule):
    description = ("Dynamic exits: early target at {early_pct}% of the entry->target "
                   "distance; breakeven once profit >= {be_arm_r}R; trailing stop "
                   "{trail_pct}% behind the best close. V2's own TP/SL always apply.")
    is_dynamic = True

    def __init__(self, early_pct=None, be_arm_r=None, trail_pct=None):
        self.early_pct = early_pct
        self.be_arm_r = be_arm_r
        self.trail_pct = trail_pct

    def check(self, position, bar_open, bar_high, bar_low, bar_close, date):
        t = position.trade
        fill0 = position.fill_price or t.entry_price
        if position.stop_now == 0.0:
            position.stop_now = t.sl
        if position.peak_close == 0.0:
            position.peak_close = fill0          # "best close" in trade direction
        stops_on = self.be_arm_r is not None or self.trail_pct is not None

        if t.side == "short":
            risk0 = t.sl - fill0                 # stop ABOVE the sell price

            # 1) STOP first (pessimistic). Ours only once tightened BELOW V2's stop.
            if stops_on and position.stop_now < t.sl and bar_high is not None \
                    and bar_high >= position.stop_now:
                fill = bar_open if (bar_open is not None and bar_open > position.stop_now) \
                    else position.stop_now       # gap up = worse buy-back
                reason = "breakeven" if abs(position.stop_now - fill0) < 1e-9 else "trail_stop"
                return fill, reason

            # 2) EARLY TARGET — bank the win before the volatile last leg (down-run).
            if self.early_pct is not None and bar_low is not None:
                level = fill0 - (self.early_pct / 100.0) * (fill0 - t.target)
                if level > t.target and bar_low <= level:
                    fill = bar_open if (bar_open is not None and bar_open < level) else level
                    return fill, "early_tp"      # gap down through it = better fill

            # 3) Update runtime state for TOMORROW (never with today's exit hindsight).
            if bar_close is not None and bar_close < position.peak_close:
                position.peak_close = bar_close
            if self.be_arm_r is not None and risk0 > 0:
                if fill0 - position.peak_close >= self.be_arm_r * risk0:
                    position.stop_now = min(position.stop_now, fill0)
            if self.trail_pct is not None:
                trail = position.peak_close * (1.0 + self.trail_pct / 100.0)
                position.stop_now = min(position.stop_now, trail)
            return None

        # ----------------------------- LONG (the original) -----------------------------
        risk0 = fill0 - t.sl

        # 1) STOP first (pessimistic when stop and target are both touched in one day).
        #    Only meaningful once the dynamic stop has risen above V2's own stop —
        #    below that, V2's close-based SL (the natural pass) is the authority.
        if stops_on and position.stop_now > t.sl and bar_low is not None \
                and bar_low <= position.stop_now:
            fill = bar_open if (bar_open is not None and bar_open < position.stop_now) \
                else position.stop_now
            reason = "breakeven" if abs(position.stop_now - fill0) < 1e-9 else "trail_stop"
            return fill, reason

        # 2) EARLY TARGET — bank the win before the volatile last leg.
        if self.early_pct is not None and bar_high is not None:
            level = fill0 + (self.early_pct / 100.0) * (t.target - fill0)
            if level < t.target and bar_high >= level:
                fill = bar_open if (bar_open is not None and bar_open > level) else level
                return fill, "early_tp"

        # 3) Update runtime state for TOMORROW (never with today's exit hindsight).
        if bar_close is not None and bar_close > position.peak_close:
            position.peak_close = bar_close
        if self.be_arm_r is not None and risk0 > 0:
            if position.peak_close - fill0 >= self.be_arm_r * risk0:
                position.stop_now = max(position.stop_now, fill0)
        if self.trail_pct is not None:
            trail = position.peak_close * (1.0 - self.trail_pct / 100.0)
            position.stop_now = max(position.stop_now, trail)
        return None
