"""
entry_filters — Krish's 3:20 PM signal-day judgment, systematized (Automation Lab).

Vetoes a V2 signal unless the SIGNAL BAR passes the configured checks, using the
evidence events.py froze onto the Trade (candle_pos, is_green, volumes, rr_remaining).
Every check is optional (None/False = off), so one rule sweeps the whole filter grid.

Missing evidence (None feature, e.g. a data gap) PASSES that check rather than
silently discarding the signal — filters must only act on evidence that exists.
"""
from ..base import SelectionRule
from ..registry import register


@register("selection", "entry_filters")
class EntryFilters(SelectionRule):
    description = ("Take a signal only if the signal bar passes: candle_pos >= "
                   "{min_candle_pos}, confirming-candle-only={green_only}, relative volume "
                   "{rel_vol}, remaining R:R >= {min_rr}.")

    def __init__(self, min_candle_pos=None, green_only=False, rel_vol=None, min_rr=None):
        self.min_candle_pos = min_candle_pos   # e.g. 0.6 -> close in the FAVOURABLE 40% of the
                                               # range (near the high for longs, near the low for
                                               # shorts — events.py normalises candle_pos per side)
        self.green_only = green_only           # confirming candle only: green longs, RED shorts
        self.rel_vol = rel_vol                 # None | "gt_prev" | "gt_1_2x20d"
        self.min_rr = min_rr                   # e.g. 1.0 -> skip if reward left < risk

    def should_take(self, portfolio, signal):
        t = signal
        if self.min_candle_pos is not None and t.candle_pos is not None:
            if t.candle_pos < self.min_candle_pos:
                return False
        if self.green_only and t.is_green is not None:
            # The CONFIRMING colour depends on the side: a short's conviction candle is
            # red. (The param keeps its historical name for policy-JSON stability.)
            confirming = t.is_green if t.side == "long" else (not t.is_green)
            if not confirming:
                return False
        if self.rel_vol == "gt_prev" and t.sig_volume is not None and t.vol_prev is not None:
            if t.sig_volume <= t.vol_prev:
                return False
        if self.rel_vol == "gt_1_2x20d" and t.sig_volume is not None and t.vol_avg20 is not None:
            if t.sig_volume <= 1.2 * t.vol_avg20:
                return False
        if self.min_rr is not None:
            # rr_remaining is None when risk <= 0 (close at/below stop) — treat as unpassable
            if t.rr_remaining is None or t.rr_remaining < self.min_rr:
                return False
        return True
