"""
report.py — human output: the generated English rule-tree + the metrics tables.
===============================================================================

ROLE IN THE FLOW (see backtest/__init__.py for the whole picture)
  This is the LAST unit before a human reads the result. It turns the two things a
  finished run produces — a Policy (the rules that ran) and a Result (how they did) —
  into text the CLI (run.py) prints. It computes nothing about trading; it only renders
  what registry.build_rules() and metrics.summarize() already decided.

      Policy  (load_policy + build_rules)  -->  english_tree()      the rule tree
      Result  (run_backtest)               -->  metrics_table()     one policy's stats
                                           -->  comparison_table()  stats side-by-side

THE "ENGLISH <-> CODE NEVER DRIFT" FEATURE (the reason english_tree exists)
  Each rule class carries a plain-English `description` with {param} placeholders (see
  rules/base.py). english_tree() asks build_rules() for the SAME instances the simulator
  ran and fills each description with the SAME params the policy passed them. So the
  sentence a human reads is generated from the code that actually executed — change a
  rule's behavior and its English changes with it; they cannot fall out of sync.

EXPOSES
  english_tree(policy)        -> str   the policy as a plain-English hierarchy
  metrics_table(result)       -> str   one policy's headline stats, labelled block
  comparison_table(results)   -> str   one row per policy, stats side-by-side

HOW TO EXTEND
  * show a new metric        -> add a row in metrics_table() / a column in
                               comparison_table(); the key must already be produced by
                               metrics.summarize() (or be an engine counter merged into
                               Result.metrics) — report.py never computes trading stats.
  * change the tree shape    -> edit english_tree(); keep reading each line's text from
                               the rule INSTANCE's `.description` so the no-drift
                               guarantee holds.
  * a non-rupee currency     -> the ₹ glyph is hard-coded to match the policy JSONs
                               (rupee-denominated); thread a symbol through if a market
                               ever reports in another currency.
"""
import math

from .rules.registry import build_rules


# ======================================================================================
# Small value formatters — every number a table prints goes through one of these, so
# "undefined" (None) and "infinite" (a no-loss profit factor) read uniformly as text
# instead of crashing str.format or printing a bare "None"/"inf".
# ======================================================================================

def _fmt_pct(x, signed=False):
    """A percentage value (already in percent units, e.g. 12.3 -> '12.3%').

    None -> 'N/A' (metrics.summarize returns None where a stat is undefined on the data).
    `signed` prepends a '+' on non-negative values so gains/losses line up by sign.
    """
    if x is None:
        return "N/A"
    return f"{x:+.2f}%" if signed else f"{x:.2f}%"


def _fmt_ratio(x):
    """A bare ratio (avg R, profit factor): 2 decimals, with None -> 'N/A' and the
    no-losing-trades profit factor (math.inf) -> 'inf' rather than an overflowing
    number string."""
    if x is None:
        return "N/A"
    if isinstance(x, float) and math.isinf(x):
        return "inf"
    return f"{x:.2f}"


def _fmt_count(x):
    """An integer count (# trades, rotations, skips): None -> 'N/A', else a plain int."""
    return "N/A" if x is None else f"{int(x)}"


def _fmt_days(x):
    """A duration in days (avg holding): 1 decimal, None -> 'N/A'."""
    return "N/A" if x is None else f"{x:.1f}"


def _fmt_money(x):
    """A rupee amount with thousands separators (₹2,000,000). Whole-rupee precision —
    capital params are round numbers and decimals only add noise to the tree."""
    return f"₹{x:,.0f}"


# ======================================================================================
# Capital utilization — the one figure report.py derives itself, because the engine does
# not record per-day cash/holdings split, only total equity. It answers "on an average
# day, what fraction of my capital was committed to positions?" — the number that shows
# whether rotation actually kept more money working (vs. sitting idle in cash).
# ======================================================================================

def _capital_utilization_pct(result):
    """Time-weighted average committed capital, as a percent of starting capital.

    Reconstructed from the Result alone (report.py never sees the Policy here):
      * starting capital is recovered EXACTLY from the equity curve and the headline
        return — metrics defines total_return_pct = (final/start - 1) * 100, so
        start = final / (1 + total_return_pct/100).
      * committed capital on each marked day = the summed ENTRY notional of every
        position open that day, read off the closed-trade ledger (a trade is open on
        [entry_date, exit_date) — half-open so the exit day, when capital is freed
        before the mark, isn't double-counted).
    Returns a percent in roughly [0, 100], or None when it can't be defined (no curve,
    undefined return, non-positive recovered capital) so the table prints 'N/A'.
    """
    eq = result.equity_curve
    if not eq:
        return None  # no marked days -> nothing to average over

    final_equity = eq[-1][1]
    total_return_pct = result.metrics.get("total_return_pct")
    if total_return_pct is None:
        return None  # can't recover the starting-capital denominator

    growth = 1.0 + total_return_pct / 100.0
    if growth <= 0:
        return None  # a -100% (or worse) run -> no meaningful base
    start = final_equity / growth
    if start <= 0:
        return None

    closed = result.closed
    if not closed:
        return 0.0  # the account never took a position -> 0% utilized

    # Average the committed fraction across every marked day. O(days * trades), which is
    # fine for a one-shot report; positions per day are few, so this stays cheap.
    total_fraction = 0.0
    for day, _equity in eq:
        committed = sum(
            ct.notional for ct in closed
            if ct.entry_date <= day < ct.exit_date
        )
        total_fraction += committed / start
    return total_fraction / len(eq) * 100.0


# ======================================================================================
# english_tree — the generated, never-drifting plain-English view of a policy.
# ======================================================================================

def english_tree(policy) -> str:
    """Render `policy` as a plain-English hierarchy, generated from the rule descriptions.

    Builds the SAME rule instances the simulator runs (registry.build_rules) and fills
    each one's `.description` with the SAME params the policy hands it, so the English is
    a faithful read-out of the code that executed (see the module header's no-drift note).

    Shape (├──/└── children under the policy line):

        Policy: <name> — "<description>"
        ├── Capital: ₹<total> · max <n> positions   (per-trade amount shows in Sizing)
        ├── Sizing: <rule> — "<filled description>"
        ├── Selection: <rule> — "<description>"
        ├── Rotation: <rule> — "<filled description>"
        └── Exit: <rule> — "<description>"

    Returns the tree as a single multi-line string (no trailing newline).
    """
    rules = build_rules(policy)  # live instances -> their .description is what ran

    # Fill each description with exactly the params build_rules passed that rule:
    #   sizing got **sizing_params · rotation got **rotation_params · the others got
    #   nothing. .format() with no matching placeholders is a harmless no-op, so the two
    #   placeholder-free rules (selection/exit) pass through unchanged.
    sizing_desc = rules["sizing"].description.format(**policy.sizing_params)
    selection_desc = rules["selection"].description.format()
    rotation_desc = rules["rotation"].description.format(**policy.rotation_params)
    exit_desc = rules["exit"].description.format()

    capital_line = (
        f"{_fmt_money(policy.total_capital)} · "
        f"max {policy.max_concurrent} positions"
    )

    # (branch_label, value) in print order; the last child renders with └── (see below).
    children = [
        ("Capital", capital_line),
        ("Sizing", f'{policy.sizing} — "{sizing_desc}"'),
        ("Selection", f'{policy.selection} — "{selection_desc}"'),
        ("Rotation", f'{policy.rotation} — "{rotation_desc}"'),
        ("Exit", f'{policy.exit} — "{exit_desc}"'),
    ]

    lines = [f'Policy: {policy.name} — "{policy.description}"']
    for i, (label, value) in enumerate(children):
        connector = "└──" if i == len(children) - 1 else "├──"
        lines.append(f"{connector} {label}: {value}")
    return "\n".join(lines)


# ======================================================================================
# metrics_table — one policy's headline stats as a labelled block.
# ======================================================================================

def metrics_table(result) -> str:
    """Render one Result's metrics as a readable, label-aligned block.

    Pulls every figure from `result.metrics` (the metrics.summarize output, with the
    engine's rotation/skip counters already merged in) except capital utilization, which
    report.py derives here. Undefined stats print as 'N/A' via the formatters above.

    Returns a multi-line string headed by the policy name (no trailing newline).
    """
    m = result.metrics

    # (label, formatted value) in reading order. win_rate is a 0..1 fraction in the
    # metrics dict, so scale it to a percent for display.
    win_rate = m.get("win_rate")
    rows = [
        ("Total return", _fmt_pct(m.get("total_return_pct"), signed=True)),
        ("CAGR", _fmt_pct(m.get("cagr"), signed=True)),
        ("Max drawdown", _fmt_pct(m.get("max_drawdown_pct"))),
        ("Win rate", _fmt_pct(win_rate * 100.0 if win_rate is not None else None)),
        ("Avg R", _fmt_ratio(m.get("avg_r"))),
        ("Profit factor", _fmt_ratio(m.get("profit_factor"))),
        ("# trades", _fmt_count(m.get("num_trades"))),
        ("Rotations triggered", _fmt_count(m.get("rotations_triggered"))),
        ("Signals skipped (no cash)", _fmt_count(m.get("signals_skipped_no_cash"))),
        ("Capital utilization", _fmt_pct(_capital_utilization_pct(result))),
        ("Avg holding days", _fmt_days(m.get("avg_holding_days"))),
    ]

    # Align the values into a column: pad each label to the widest label + a colon.
    label_w = max(len(label) for label, _ in rows)
    lines = [f"Metrics: {result.policy_name}"]
    for label, value in rows:
        lines.append(f"  {label:<{label_w}} : {value}")
    return "\n".join(lines)


# ======================================================================================
# comparison_table — every policy's headline stats side-by-side, one row each.
# ======================================================================================

# (header, extractor) for each column. The extractor takes a Result and returns the
# already-formatted cell text, so adding a column is one line here. Rotations/Skipped sit
# next to the money columns on purpose: they're how you read WHETHER rotation helped.
_COLUMNS = [
    ("Policy", lambda r: r.policy_name),
    ("Return", lambda r: _fmt_pct(r.metrics.get("total_return_pct"), signed=True)),
    ("CAGR", lambda r: _fmt_pct(r.metrics.get("cagr"), signed=True)),
    ("MaxDD", lambda r: _fmt_pct(r.metrics.get("max_drawdown_pct"))),
    ("Win", lambda r: _fmt_pct(
        r.metrics["win_rate"] * 100.0 if r.metrics.get("win_rate") is not None else None)),
    ("AvgR", lambda r: _fmt_ratio(r.metrics.get("avg_r"))),
    ("PF", lambda r: _fmt_ratio(r.metrics.get("profit_factor"))),
    ("Trades", lambda r: _fmt_count(r.metrics.get("num_trades"))),
    ("Rotations", lambda r: _fmt_count(r.metrics.get("rotations_triggered"))),
    ("Skipped", lambda r: _fmt_count(r.metrics.get("signals_skipped_no_cash"))),
    ("Util", lambda r: _fmt_pct(_capital_utilization_pct(r))),
]


def comparison_table(results) -> str:
    """Render a list of Results as a fixed-width table, ONE ROW PER POLICY.

    Each column comes from _COLUMNS (header + a formatter reading one metric), so every
    policy's headline numbers — including rotations and skipped-signals — line up for a
    direct "which made more money, and did rotation help?" read. Column widths size to
    the widest cell so the columns stay aligned regardless of policy name length.

    Returns a header row, a rule line, then one line per Result (no trailing newline).
    An empty `results` list yields just the header + rule (nothing to compare).
    """
    headers = [h for h, _ in _COLUMNS]
    # Build every cell first so we can size each column to its widest entry.
    rows = [[extract(r) for _, extract in _COLUMNS] for r in results]

    widths = [
        max(len(headers[c]), *(len(row[c]) for row in rows)) if rows else len(headers[c])
        for c in range(len(_COLUMNS))
    ]

    def _render(cells):
        # Left-align the Policy name (column 0); right-align the numeric columns so
        # decimals and signs read down the page.
        out = []
        for c, cell in enumerate(cells):
            out.append(f"{cell:<{widths[c]}}" if c == 0 else f"{cell:>{widths[c]}}")
        return "  ".join(out)

    lines = [_render(headers)]
    lines.append("  ".join("-" * w for w in widths))   # rule line under the header
    for row in rows:
        lines.append(_render(row))                      # exactly one line per policy
    return "\n".join(lines)
