"""
tv_zigzag.py — faithful Python port of the TradingView ZigZag library
=====================================================================

A line-for-line port of `tradingview_zigzag_v9.pine` (© TradingView, MPL-2.0).
Core detection mechanics are identical across library versions 7/8/9 (per the
official release notes); the KB Fib Dual Trade indicator pins v7 and runs with
**projection pivots OFF**, so this port implements only the CONFIRMED-pivot path
and deliberately omits the projection machinery (`findProjectionPivot`,
`updateProjectionPivot`, the `barstate.islast` projection block) — none of which
runs when `projectionPivots = false`.

This REPLACES the hand-rolled deviation-tracker in `pine_engine.py`, which used a
different algorithm and the wrong `depth` semantics.

Pine→Python mapping (source lines in tradingview_zigzag_v9.pine):
  findPivotPoint        P:85-100   -> _find_pivot_point
  calcDev               P:108-109  -> _calc_dev
  isMorePrice           P:246-248  -> inline in _new_pivot_point_found
  newPivotPointFound    P:302-319  -> _new_pivot_point_found
  tryFindPivot          P:339-343  -> inline in update loop
  update (confirmed)    P:471-539  -> detect_pivots loop

KEY SEMANTICS recovered from the real source (all were guessed wrong before):
  * effective depth = max(2, floor(settings.depth / 2))   (P:477) — HALVED
  * pivot = value `depth` bars back; >= all `depth` newer bars, > all `depth`
    older bars (asymmetric equality); confirmed `depth` bars later  (P:85-100)
  * a new opposite-direction pivot registers only if the % move from the last
    pivot >= devThreshold; same-direction more-extreme updates the last pivot
  * devThreshold is ALWAYS a percentage; "Absolute" mode only affects labels
"""
import math


def _calc_dev(start, end):
    """P:108 — calcDev: signed % change of `end` vs `start`."""
    if start == 0:
        return 0.0
    return 100.0 * (end - start) / abs(start)


def _find_pivot_point(source, k, depth, is_high):
    """P:85-100 — findPivotPoint, evaluated as if the current bar is index `k`.

    `source` is a full list; `source[k - off]` is the Pine `source[off]` (off bars
    back). The candidate sits `depth` bars back. Returns (pivot_index, price) or None.
    """
    if depth == 0:
        return (k, source[k])
    # Pine guard: `depth * 2 <= bar_index`
    if depth * 2 > k:
        return None
    cand = source[k - depth]
    # Right side — offsets 0..depth-1 (newer than candidate): high must be >= these
    for i in range(0, depth):
        v = source[k - i]
        if (is_high and v > cand) or (not is_high and v < cand):
            return None
    # Left side — offsets depth+1..2*depth (older than candidate): high must be > these
    for i in range(depth + 1, 2 * depth + 1):
        v = source[k - i]
        if (is_high and v >= cand) or (not is_high and v <= cand):
            return None
    return (k - depth, cand)


def detect_pivots(high, low, depth_setting, dev_threshold, allow_one_bar=True):
    """Replay the library's confirmed-pivot detection bar-by-bar over the series.

    Returns the ordered list of confirmed ZigZag pivots as
    `(bar_index, price, is_high)`, where `bar_index` is the true bar of the pivot
    (it is only *detected* `depth` bars later, with no lookahead).

    Mirrors `tryFindPivot(high, true)` then `tryFindPivot(low, false)` per bar,
    and `newPivotPointFound`'s update-vs-register logic.
    """
    n = len(high)
    depth = max(2, math.floor(depth_setting / 2))      # P:477 — the halving
    pivots = []   # list of [bar_index, price, is_high] for each pivot's END point

    def register(point, is_high):
        """P:302-319 — newPivotPointFound (update last vs push new)."""
        idx, price = point
        if pivots:
            last = pivots[-1]
            last_idx, last_price, last_is_high = last
            if last_is_high == is_high:
                # same direction: update last pivot if the new point is more extreme
                m = 1 if is_high else -1
                if price * m > last_price * m:          # isMorePrice (P:246-248)
                    last[0], last[1] = idx, price
            else:
                dev = _calc_dev(last_price, price)
                if (not last_is_high and dev >= dev_threshold) or \
                   (last_is_high and dev <= -dev_threshold):
                    pivots.append([idx, price, is_high])
        else:
            pivots.append([idx, price, is_high])

    for k in range(n):
        # tryFindPivot(high, isHigh=true, depth)  — P:484
        hp = _find_pivot_point(high, k, depth, True)
        new_high = hp is not None
        if new_high:
            register(hp, True)
        # tryFindPivot(low, isHigh=false, depth, registerPivot = allowOneBar or not newHigh)
        register_low = allow_one_bar or not new_high   # P:485
        lp = _find_pivot_point(low, k, depth, False)
        if lp is not None and register_low:
            register(lp, False)

    return [(idx, price, is_high) for idx, price, is_high in pivots]


# ============================================================================
# SELF-TEST — synthetic swing + sanity on the pivot rules
# ============================================================================
if __name__ == "__main__":
    # A clean down-then-up series; with depth_setting=4 (-> depth=2) we expect a
    # low pivot near the bottom and a high pivot near the top, given a big % move.
    seq = [100, 98, 96, 90, 80, 70, 60, 55, 60, 70, 82, 95, 110, 112, 111, 113]
    highs = [p * 1.005 for p in seq]
    lows = [p * 0.995 for p in seq]
    piv = detect_pivots(highs, lows, depth_setting=4, dev_threshold=15.0)
    print(f"pivots ({len(piv)}):")
    for idx, price, is_high in piv:
        print(f"  bar {idx:>2}  {'H' if is_high else 'L'}  {price:.2f}")
    # effective depth check
    print("effective depth for setting=10:", max(2, math.floor(10 / 2)))
