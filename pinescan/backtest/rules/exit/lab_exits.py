"""
lab_exits — the Automation Lab's dynamic exit toolbox (early target / breakeven / trail).

One composite rule with every leg optional, so a single rule name sweeps the whole
exit grid. Evaluated daily per open position by the simulator's dynamic-exit pass
(AFTER V2's natural TP/SL pass — V2's own exit always wins its own date).

Legs (all off by default = behaves exactly like scanner_default):
  early_pct   exit when the day's HIGH reaches entry + early_pct% of (target - entry)
              (Krish's "don't wait for the last volatile leg")
  be_arm_r    once the PEAK CLOSE has gained >= be_arm_r x initial risk, the stop
              rises to the entry price ("make the trade free")
  trail_pct   the stop follows the peak close down by trail_pct percent

Discipline against lookahead & optimism:
  * stop state (peak/breakeven/trail) updates AFTER the day's exit checks, so a stop
    can only act on information from PRIOR days;
  * the STOP check runs BEFORE the early-target check (pessimistic on double-touch days);
  * gap days fill at the day's OPEN when it opens beyond the level (worse for stops,
    better for targets — both realistic);
  * the dynamic stop only ever RISES, and never sits below V2's own 0.236 stop.
"""
from ..base import ExitRule
from ..registry import register


@register("exit", "lab_exits")
class LabExits(ExitRule):
    description = ("Dynamic exits: early target at {early_pct}% of the entry->target "
                   "distance; breakeven once profit >= {be_arm_r}R; trailing stop "
                   "{trail_pct}% below the peak close. V2's own TP/SL always apply.")
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
            position.peak_close = fill0
        risk0 = fill0 - t.sl

        # 1) STOP first (pessimistic when stop and target are both touched in one day).
        #    Only meaningful once the dynamic stop has risen above V2's own stop —
        #    below that, V2's close-based SL (the natural pass) is the authority.
        if (self.be_arm_r is not None or self.trail_pct is not None) \
                and position.stop_now > t.sl and bar_low is not None \
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
