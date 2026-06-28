"""Pine-exact runtime building blocks for hand-authored ports.

Every function is CAUSAL and whole-series: `out[i]` depends only on inputs at
bars `<= i`, exactly mirroring Pine's bar-by-bar execution, so the same code
serves both backtests and live (append a bar, recompute or stream).

Semantics are taken from the published Pine v5/v6 reference equivalents
(e.g. `ema` / `rma` are documented as `na(prev) ? sma(src, len) : alpha * src
+ (1 - alpha) * prev`). Where TradingView does NOT publish exact semantics the
docstring says **UNVERIFIED vs TV** — those details MUST be covered by the
golden-master parity test (pinescan.core.parity); never assume them.

na is float('nan'); arithmetic with na yields na, as in Pine.
"""
import math as _math

# ---------------------------------------------------------------------------
# na / nz / Series
# ---------------------------------------------------------------------------

na = float("nan")


def is_na(x):
    """Pine `na(x)` — true for None or NaN."""
    return x is None or (isinstance(x, float) and _math.isnan(x))


def nz(x, replacement=0):
    """Pine `nz(x, replacement)`."""
    return replacement if is_na(x) else x


class Series:
    """Pine-style series with `[n]` history access (n bars back).

    Push one value per bar; out-of-range history is na, like Pine before the
    first bar. `set()` reassigns the current bar (Pine `s := value`).
    """

    __slots__ = ("_data",)

    def __init__(self, values=None):
        self._data = list(values) if values else []

    def push(self, value):
        self._data.append(value)

    def set(self, value):
        if not self._data:
            raise IndexError("Series.set() before first push()")
        self._data[-1] = value

    def __getitem__(self, bars_back):
        i = len(self._data) - 1 - bars_back
        if bars_back < 0 or i < 0:
            return na
        return self._data[i]

    def __len__(self):
        return len(self._data)

    def to_list(self):
        return list(self._data)


def _window(src, i, length):
    """Last `length` values ending at bar i, or None if the window isn't full."""
    if i + 1 < length:
        return None
    return src[i + 1 - length : i + 1]


# ---------------------------------------------------------------------------
# ta.* — moving averages and friends
# ---------------------------------------------------------------------------

def sma(src, length):
    """Pine `ta.sma` — na until the window holds `length` bars; any na in the
    window makes the output na (Pine na-propagation)."""
    out = []
    for i in range(len(src)):
        w = _window(src, i, length)
        if w is None or any(is_na(v) for v in w):
            out.append(na)
        else:
            out.append(sum(w) / length)
    return out


def _recursive_ma(src, length, alpha):
    """Pine's published recursion: na(prev) ? sma(src, length) : alpha*src + (1-alpha)*prev."""
    smas = sma(src, length)
    out, prev = [], na
    for i, x in enumerate(src):
        if is_na(prev):
            v = smas[i]
        else:
            v = na if is_na(x) else alpha * x + (1 - alpha) * prev
        out.append(v)
        prev = v
    return out


def ema(src, length):
    """Pine `ta.ema` — alpha = 2/(length+1), seeded with sma."""
    return _recursive_ma(src, length, 2.0 / (length + 1))


def rma(src, length):
    """Pine `ta.rma` — alpha = 1/length, seeded with sma (used by rsi/atr)."""
    return _recursive_ma(src, length, 1.0 / length)


def wma(src, length):
    """Pine `ta.wma` — linear weights, most recent bar heaviest."""
    denom = length * (length + 1) / 2.0
    out = []
    for i in range(len(src)):
        w = _window(src, i, length)
        if w is None or any(is_na(v) for v in w):
            out.append(na)
        else:
            out.append(sum(v * (k + 1) for k, v in enumerate(w)) / denom)
    return out


def vwma(src, volume, length):
    """Pine `ta.vwma` = sma(src*volume, length) / sma(volume, length)."""
    prod = [na if (is_na(s) or is_na(v)) else s * v for s, v in zip(src, volume)]
    num, den = sma(prod, length), sma(volume, length)
    return [na if (is_na(a) or is_na(b) or b == 0) else a / b for a, b in zip(num, den)]


# ---------------------------------------------------------------------------
# ta.* — change / extremes / crosses
# ---------------------------------------------------------------------------

def change(src, length=1):
    """Pine `ta.change` — src - src[length]."""
    out = []
    for i, x in enumerate(src):
        prev = src[i - length] if i >= length else na
        out.append(na if (is_na(x) or is_na(prev)) else x - prev)
    return out


def mom(src, length=1):
    """Pine `ta.mom` — identical to change."""
    return change(src, length)


def cum(src):
    """Pine `ta.cum` — running sum (a na input poisons the total from that
    bar on, faithful to `s := s + src`). UNVERIFIED vs TV for na inputs."""
    out, total = [], 0.0
    for x in src:
        total = na if (is_na(total) or is_na(x)) else total + x
        out.append(total)
    return out


def _extreme(src, length, pick):
    out = []
    for i in range(len(src)):
        w = _window(src, i, length)
        if w is None:
            out.append((na, na))
            continue
        vals = [(v, k) for k, v in enumerate(w) if not is_na(v)]
        if not vals:
            out.append((na, na))
            continue
        best = pick(vals, key=lambda t: (t[0], t[1]))
        out.append((best[0], float(best[1] - (length - 1))))  # offset: 0 current, negative back
    return out


def highest(src, length):
    """Pine `ta.highest` — na until window full; na values in a full window are
    ignored (UNVERIFIED vs TV for the na-in-window case)."""
    return [v for v, _ in _extreme(src, length, max)]


def lowest(src, length):
    """Pine `ta.lowest` — see highest()."""
    return [v for v, _ in _extreme(src, length, lambda vals, key: min(vals, key=lambda t: (t[0], -t[1])))]


def highestbars(src, length):
    """Pine `ta.highestbars` — offset to the highest bar (0 = current,
    negative = bars back). Ties resolve to the most recent bar
    (UNVERIFIED vs TV)."""
    return [o for _, o in _extreme(src, length, max)]


def lowestbars(src, length):
    """Pine `ta.lowestbars` — see highestbars()."""
    return [o for _, o in _extreme(src, length, lambda vals, key: min(vals, key=lambda t: (t[0], -t[1])))]


def crossover(a, b):
    """Pine `ta.crossover` — a crosses above b on this bar; na anywhere -> False."""
    out = []
    for i in range(len(a)):
        if i == 0 or any(is_na(v) for v in (a[i], b[i], a[i - 1], b[i - 1])):
            out.append(False)
        else:
            out.append(a[i] > b[i] and a[i - 1] <= b[i - 1])
    return out


def crossunder(a, b):
    """Pine `ta.crossunder`."""
    return crossover(b, a)


def cross(a, b):
    """Pine `ta.cross` — crossover or crossunder."""
    return [o or u for o, u in zip(crossover(a, b), crossunder(a, b))]


# ---------------------------------------------------------------------------
# ta.* — volatility / oscillators
# ---------------------------------------------------------------------------

def tr(high, low, close, handle_na=False):
    """Pine `ta.tr(handle_na)` — max(h-l, |h-c[1]|, |l-c[1]|); on the first bar
    (no prev close): h-l when handle_na, else na."""
    out = []
    for i in range(len(high)):
        c1 = close[i - 1] if i > 0 else na
        if is_na(c1):
            out.append(high[i] - low[i] if handle_na else na)
        else:
            out.append(max(high[i] - low[i], abs(high[i] - c1), abs(low[i] - c1)))
    return out


def atr(high, low, close, length):
    """Pine `ta.atr` — rma of tr(handle_na=true)."""
    return rma(tr(high, low, close, handle_na=True), length)


def rsi(src, length):
    """Pine `ta.rsi` — 100 - 100/(1+rs) with rma-smoothed gains/losses;
    avg loss 0 -> 100, avg gain 0 -> 0."""
    ch = change(src)
    gains = [na if is_na(c) else max(c, 0.0) for c in ch]
    losses = [na if is_na(c) else max(-c, 0.0) for c in ch]
    ag, al = rma(gains, length), rma(losses, length)
    out = []
    for g, l in zip(ag, al):
        if is_na(g) or is_na(l):
            out.append(na)
        elif l == 0:
            out.append(100.0)
        elif g == 0:
            out.append(0.0)
        else:
            out.append(100.0 - 100.0 / (1.0 + g / l))
    return out


def stdev(src, length, biased=True):
    """Pine `ta.stdev` — population (biased) by default, like Pine."""
    out = []
    for i in range(len(src)):
        w = _window(src, i, length)
        if w is None or any(is_na(v) for v in w):
            out.append(na)
            continue
        m = sum(w) / length
        ss = sum((v - m) ** 2 for v in w)
        n = length if biased else length - 1
        out.append(_math.sqrt(ss / n) if n > 0 else na)
    return out


# ---------------------------------------------------------------------------
# ta.* — event/state functions
# ---------------------------------------------------------------------------

def valuewhen(condition, src, occurrence=0):
    """Pine `ta.valuewhen` — src value on the Nth most recent bar (0 = latest,
    including the current bar) where condition was true; na until it exists."""
    hits, out = [], []
    for i, c in enumerate(condition):
        if c:
            hits.append(src[i])
        out.append(hits[-1 - occurrence] if len(hits) > occurrence else na)
    return out


def barssince(condition):
    """Pine `ta.barssince` — bars since condition was last true (0 = this bar);
    na before the first true."""
    out, last = [], None
    for i, c in enumerate(condition):
        if c:
            last = i
        out.append(na if last is None else float(i - last))
    return out


def pivothigh(src, leftbars, rightbars):
    """Pine `ta.pivothigh` — emits the pivot value on the CONFIRMATION bar
    (`rightbars` after the candidate), na elsewhere.

    Comparison is strict `>` on both sides, so equal neighbors disqualify.
    **UNVERIFIED vs TV** — TradingView does not publish the exact equality
    rule (the real ZigZag library uses asymmetric >= newer / > older; see
    tv_zigzag.py). Any port relying on pivots MUST cover them in the
    golden-master parity test.
    """
    return _pivot(src, leftbars, rightbars, is_high=True)


def pivotlow(src, leftbars, rightbars):
    """Pine `ta.pivotlow` — see pivothigh() (same UNVERIFIED equality caveat)."""
    return _pivot(src, leftbars, rightbars, is_high=False)


def _pivot(src, leftbars, rightbars, is_high):
    out = [na] * len(src)
    for i in range(leftbars + rightbars, len(src)):
        ci = i - rightbars
        cand = src[ci]
        if is_na(cand):
            continue
        neighbors = src[ci - leftbars : ci] + src[ci + 1 : i + 1]
        if any(is_na(v) for v in neighbors):
            continue
        if is_high and all(cand > v for v in neighbors):
            out[i] = cand
        elif not is_high and all(cand < v for v in neighbors):
            out[i] = cand
    return out


# Names exported for lint's supported-builtins check (pinescan.core.lint).
SUPPORTED_BUILTINS = {
    "ta.sma", "ta.ema", "ta.rma", "ta.wma", "ta.vwma", "ta.change", "ta.mom",
    "ta.cum", "ta.highest", "ta.lowest", "ta.highestbars", "ta.lowestbars",
    "ta.crossover", "ta.crossunder", "ta.cross", "ta.tr", "ta.atr", "ta.rsi",
    "ta.stdev", "ta.valuewhen", "ta.barssince", "ta.pivothigh", "ta.pivotlow",
    # trivially mapped math builtins
    "math.abs", "math.max", "math.min", "math.floor", "math.ceil", "math.round",
    "math.sign", "math.sqrt", "math.pow", "math.log", "math.exp", "math.avg",
    "math.sum",
}
