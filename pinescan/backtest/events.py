"""
events.py — turn the V2 engine's per-bar signals into discrete Trade records.
============================================================================

ROLE IN THE FLOW (see backtest/__init__.py)
  This is the FIRST backtester unit. It is the only place that talks to the
  parity-verified signal engine; every downstream unit (portfolio, rules,
  engine, metrics) consumes the Trade list this module produces and never looks
  at the engine again. So this file is the seam between "what V2 signalled" and
  "what a portfolio does about it".

WHAT IT CONSUMES
  pinescan.nsv2_engine — READ ONLY. We call `run(df, params)` exactly once and
  reconstruct trades purely from its returned per-bar series. We never mutate the
  engine or re-run it; the engine's entry/TP/SL logic is parity-locked and this
  unit must not change a single signal.

  The engine returns lists, each bar-aligned to df.index:
    out["B"]                 common-low B price (na before a setup exists)
    out["A0".."A3"]          nested-peak prices for swings T1..T4 (na if absent)
    out["ST0".."ST3"]        per-swing state machine, recorded every bar:
                               0 = no setup yet (before the first B)
                               1 = wait  (armed, waiting for the 0.382 cross)
                               2 = IN    (entered; managing toward TP/SL)
                               3 = TP    (take-profit hit; terminal)
  The state machine only ever reaches 2 via a genuine entry fire, and 3 is
  terminal — facts this reconstruction relies on (see trades_for).

WHAT IT EXPOSES
  trades_for(symbol, df, params=None) -> list[Trade]
      One Trade per swing-entry that fired, levels snapshotted at the entry bar,
      tagged with V2's own (natural) TP/SL/open outcome. Sorted by entry_date.

HOW TO EXTEND
  * change what counts as a trade (e.g. also record the entry filter values,
    or split re-entries differently) -> here, in trades_for.
  * need a new level on the Trade (e.g. the 0.32 entry-band low) -> add the field
    in contracts.py, then populate it here from swing_levels(...).
  * the levels come from nsv2_engine.swing_levels(A, B, params); if the fib
    inputs change, they change there, not here.
"""
import math

from ..scanners import registry
from .contracts import Trade


# Per-swing state codes recorded in out["ST{i}"] (see module header / engine).
_WAIT = 1   # armed, waiting for the 0.382 cross
_IN = 2     # entered; position live, managing toward TP/SL
_TP = 3     # take-profit hit; terminal


def _natural_exit(st_series, entry_k, index):
    """V2's OWN outcome for the position entered at bar `entry_k`, ignoring any
    capital limits the simulator will later impose.

    While a swing is IN its state stays `_IN`; the first later bar that leaves
    `_IN` is the exit:
        -> _TP   (3)  the 0.618 target was reached            -> outcome "tp"
        -> _WAIT (1)  close fell below 0.236 and the swing     -> outcome "sl"
                      re-armed (a new common-low B also resets a
                      live swing to wait, so it surfaces here too)
    If the swing never leaves `_IN` before data ends, the trade is still open.

    Returns (exit_date | None, outcome) where outcome is "tp" | "sl" | "open".
    """
    for m in range(entry_k + 1, len(st_series)):
        s = st_series[m]
        if s == _TP:
            return index[m], "tp"
        if s == _WAIT:
            return index[m], "sl"
        # s == _IN -> still holding; keep scanning forward
    return None, "open"


def trades_for(symbol, df, scanner="nsv2", params=None):
    """Reconstruct every V2 swing-trade for one symbol from a single engine run.

    Runs the scanner's engine (default "nsv2") once (read-only) and replays the recorded
    per-swing state series to emit one Trade per entry that fired.

    For each swing i in 0..3 we walk its ST{i} series and look for a transition
    INTO state _IN (prev != _IN and cur == _IN) — that bar is an entry. We detect
    "into _IN" rather than strictly the 1->2 pair because the engine resets a
    freshly-confirmed swing to _WAIT and then runs the entry test within the SAME
    bar: when a setup's B-confirmation and its entry land on one bar, the recorded
    snapshot shows 0->2 (the intermediate _WAIT is invisible). "Into _IN" captures
    that bar too and can never false-positive, since the engine reaches state _IN
    only on a real entry fire.

    At the entry bar k the price levels are FIXED: we snapshot A = out["A{i}"][k]
    and B = out["B"][k] and derive target/sl from nsv2_engine.swing_levels. Swings
    whose A or B is na at the entry bar are skipped (no valid setup to price).

    Args:
        symbol: ticker label stamped onto each Trade.
        df:     OHLCV DataFrame (TitleCase or TradingView-lower columns), the same
                frame handed to the engine; its index supplies the trade dates.
        params: optional overrides for nsv2_engine.DEFAULTS. Merged onto the
                defaults so a partial dict is safe for both run() and swing_levels.

    Returns:
        list[Trade], sorted by entry_date. ALL per-swing entries are emitted (the
        same symbol may yield several, e.g. T1 plus a later re-entry after an SL);
        the "one open position per symbol" rule is enforced later by the simulator,
        not here.
    """
    # Resolve the scanner (default nsv2) via the registry, then merge once so swing_levels (which
    # would otherwise KeyError on a partial dict) and the engine see the identical, fully-populated
    # parameter set. Default nsv2 -> byte-identical to the pre-registry behaviour.
    sc = registry.get(scanner)
    p = dict(sc.default_params)
    if params:
        p.update(params)
    # Short scanners (side="short") mirror the geometry: target BELOW entry, stop ABOVE.
    short = getattr(sc, "side", "long") == "short"

    out = sc.run(df, p)

    # The engine accepts either Title-case or TradingView-lower OHLCV; mirror that
    # when reading the fill price so trades_for works on whatever the caller passed.
    def _series(*names):
        for nm in names:
            if nm in df.columns:
                return df[nm]
        return None

    closes = _series("Close", "close")
    opens = _series("Open", "open")
    highs = _series("High", "high")
    lows = _series("Low", "low")
    vols = _series("Volume", "volume")
    # 20-bar volume SMA for the relative-volume entry filter (display/filter feature
    # only — the engine's own volume filter stays inside the parity-locked engine)
    vol_sma20 = vols.rolling(20).mean() if vols is not None else None
    index = df.index

    trades = []
    for i in range(4):
        st_series = out[f"ST{i}"]
        a_series = out[f"A{i}"]
        b_series = out["B"]

        prev = 0.0  # engine's pre-first-bar state (no setup yet)
        for k in range(len(st_series)):
            cur = st_series[k]
            is_entry = (cur == _IN) and (prev != _IN)
            prev = cur
            if not is_entry:
                continue

            # Snapshot the levels frozen at this entry bar.
            a_price = a_series[k]
            b_price = b_series[k]
            if math.isnan(a_price) or math.isnan(b_price):
                continue  # no valid A/B to price this swing — skip

            lv = sc.swing_levels(a_price, b_price, p)
            exit_date, outcome = _natural_exit(st_series, k, index)

            # --- signal-bar evidence for the Automation Lab's entry filters ---
            bar_c = float(closes.iloc[k])

            def _f(series, kk=k):
                if series is None:
                    return None
                v = series.iloc[kk]
                return None if (v != v) else float(v)   # NaN-safe

            bar_o, bar_h, bar_l = _f(opens), _f(highs), _f(lows)
            rng = (bar_h - bar_l) if (bar_h is not None and bar_l is not None) else None
            candle_pos = ((bar_c - bar_l) / rng) if (rng is not None and rng > 0) else None
            # Side-aware geometry. The level dicts keep PRICE semantics (tL = lower
            # price), so the 0.618 first-touch target edge is tL for longs but tH for
            # shorts. candle_pos is normalised to "close near the FAVOURABLE extreme"
            # (the high for longs, the low for shorts) so one filter serves both sides.
            target = lv["tH"] if short else lv["tL"]
            if short and candle_pos is not None:
                candle_pos = 1.0 - candle_pos
            risk = (lv["sl"] - bar_c) if short else (bar_c - lv["sl"])
            reward = (bar_c - target) if short else (target - bar_c)
            rr_remaining = (reward / risk) if risk > 0 else None
            has_next = k + 1 < len(index)

            trades.append(Trade(
                symbol=symbol,
                swing=f"T{i + 1}",
                entry_date=index[k],
                entry_price=bar_c,
                target=target,            # 0.618 first-touch edge (below entry for shorts)
                sl=lv["sl"],              # 0.236 stop (above entry for shorts)
                side="short" if short else "long",
                natural_exit_date=exit_date,
                natural_outcome=outcome,
                sig_open=bar_o,
                sig_high=bar_h,
                sig_low=bar_l,
                sig_volume=_f(vols),
                vol_avg20=_f(vol_sma20),
                vol_prev=_f(vols, k - 1) if k > 0 else None,
                candle_pos=candle_pos,
                is_green=(bar_c > bar_o) if bar_o is not None else None,
                rr_remaining=rr_remaining,
                next_open=_f(opens, k + 1) if has_next else None,
                next_date=index[k + 1] if has_next else None,
            ))

    # Across-swing emission order is by swing index; the simulator wants a single
    # chronological stream, so sort by entry_date (stable: same-bar entries keep
    # T1..T4 order).
    trades.sort(key=lambda t: t.entry_date)
    return trades
