"""Shared bits for market data sources.

The data interface the scanner/backtester target is:

    get_universe() -> (symbols, {symbol: sector})   the tradeable list
    get_daily(symbol) -> DataFrame                   OHLCV, DatetimeIndex,
                                                     columns Open/High/Low/Close/Volume

`india` implements this directly (per-symbol fetch). `us` currently exposes its own
bulk-cache API instead — `select_liquid_universe()` + `load_cache()` — because Polygon's
grouped endpoint is fetched per-date, not per-symbol; it'll be wrapped to the same names
when the backtester needs US (Phase 2 is India-first). No formal ABC yet — convention
only, promoted when a third market makes it earn its keep. Adding an exchange to backtest
= a new module providing daily bars + one line in the script that selects it.
"""


def resample_weekly(d):
    """Aggregate daily bars into weekly (Friday close)."""
    if d is None or len(d) == 0:
        return None
    return d.resample("W-FRI").agg(
        {"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"}
    ).dropna()
