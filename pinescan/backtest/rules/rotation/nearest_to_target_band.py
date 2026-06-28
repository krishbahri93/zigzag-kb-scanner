"""
nearest_to_target_band.py — rotation rule: recycle capital out of the position
that is closest to cashing in.
==============================================================================

WHAT IT DOES
  When the portfolio is full and a new signal fires, this rule funds the new entry
  by selling ONE open position that is already near its take-profit — the idea being
  "bank the trade that's nearly done and redeploy into a fresher setup." It looks for
  positions inside a TARGET band and, among those, sells the single one closest to
  its target.

THE BAND — and how to read distance_to_target (READ THIS BEFORE TWEAKING)
  portfolio.distance_to_target(sym, price) is a 0..1 progress measure for a position:
  0 at the entry price, 1 once price reaches the target. A position is "IN-BAND at
  band%" when it has covered all but the last band% of the way to its target, i.e.

      portfolio.distance_to_target(sym, prices[sym]) >= 1 - band/100

  e.g. band=10  -> distance >= 0.90  (within the final 10% of the move to target)
       band=40  -> distance >= 0.60.

  We start at `start`% and, if nothing qualifies, WIDEN the band by `step`% at a time
  up to `max`%, admitting positions that are progressively further from target. Among
  whatever is in-band we sell the ONE CLOSEST to target (the largest
  distance_to_target). If nothing is in-band even at the widest band, we free nothing
  (return []) and the new signal is skipped.

  This rule sells EXACTLY ONE position per call and ignores `needed`/`date`: it frees
  "a" slot, not a precise rupee amount. All of these are deliberate, tunable choices —
  the in-band test, "closest" vs "furthest", one-vs-many — see HOW TO MAKE A VARIANT.

WHEN THE SIMULATOR CALLS IT
  engine.py calls free_capital() only when the portfolio is full and a new signal
  wants in. The returned symbol is closed (counted as a "rotated" exit) to make room.

HOW TO MAKE A VARIANT
  Copy this file, change the @register name and __init__ params, and rewrite
  free_capital(). To sell the position FURTHEST from target, key min() on
  distance_to_target; to free a precise amount, keep selling (accumulate notional)
  until freed >= `needed`; to bias by cash freed, key on the position's notional.
  Then name your rule under "rotation" in a policy JSON.
"""
from ..base import RotationRule
from ..registry import register


@register("rotation", "nearest_to_target_band")
class NearestToTargetBand(RotationRule):
    """Fund a new entry by selling the open position nearest its target, searching a
    band that starts at `start`% from target and widens by `step`% up to `max`%."""

    description = ("To fund a new entry, sell the open position closest to its target "
                   "within {start}%; widen the band by {step}% up to {max}%.")

    def __init__(self, start=10, step=10, max=40):
        # Band edges, in PERCENT-from-target. Defaults match the `rotation` policy.
        # `max` shadows the builtin on purpose: the name mirrors the policy JSON key so
        # build_rules(**rotation_params) maps straight onto these constructor params.
        self.start = start
        self.step = step
        self.max = max

    def free_capital(self, portfolio, needed, prices, date):
        """Return [symbol] of the in-band position closest to target, or [] if none
        qualifies even at the widest band. `needed` and `date` are unused by this
        rule (it frees one slot, not a precise amount)."""
        band = self.start
        while band <= self.max:
            # In-band = within the final band% of the way to target (see file header).
            threshold = 1 - band / 100
            in_band = [
                sym for sym in portfolio.positions
                if portfolio.distance_to_target(sym, prices[sym]) >= threshold
            ]
            if in_band:
                # Closest to target = the largest distance_to_target among them.
                nearest = max(
                    in_band,
                    key=lambda sym: portfolio.distance_to_target(sym, prices[sym]),
                )
                return [nearest]
            band += self.step  # nothing close enough yet — widen the band and retry
        return []  # nothing near enough to target, even at the widest band
