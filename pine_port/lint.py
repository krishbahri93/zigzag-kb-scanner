"""Static pre-port analysis of a .pine source file.

Run this FIRST, before writing any Python. It answers, deterministically:

  * Which libraries does the script import? These are NOT auto-fetchable —
    the user must open each library on TradingView ("Source code" button)
    and copy-paste the FULL Pine source (including type definitions) into
    the repo. The report says so upfront, per import.
  * Which Pine constructs are semantic traps (varip, request.security,
    lookahead, var state, pivot confirmation lag, realtime-only barstate)?
  * Which ta./math. builtins are used, and which have no Pine-exact
    implementation in pine_port.runtime yet?
  * Which series are plot()-ed — TradingView's CSV export emits ONLY plotted
    series, so anything you want to verify must appear here.

Output is a plain dict (JSON-serializable); `format_report` renders it for
humans. CLI: python -m pine_port lint <file.pine> [--json]
"""
import re

from .runtime import SUPPORTED_BUILTINS

_IMPORT_RE = re.compile(
    r"^\s*import\s+([A-Za-z0-9_\-]+)/([A-Za-z0-9_\-]+)/(\d+)(?:\s+as\s+(\w+))?",
    re.MULTILINE,
)
_BUILTIN_RE = re.compile(
    r"\b(ta|math|request|array|matrix|map|str|syminfo|timeframe|barstate|strategy|ticker)\.(\w+)"
)
_PLOT_RE = re.compile(r"\bplot(?:char|shape|arrow|candle|bar)?\s*\(([^\n]*)")
_TITLE_KW_RE = re.compile(r"title\s*=\s*\"([^\"]*)\"")
_FIRST_STR_RE = re.compile(r"\"([^\"]*)\"")


def _strip_comments(text):
    """Remove // comments, respecting double-quoted strings."""
    out_lines = []
    for line in text.splitlines():
        in_str = False
        cut = len(line)
        i = 0
        while i < len(line):
            ch = line[i]
            if ch == '"' and (i == 0 or line[i - 1] != "\\"):
                in_str = not in_str
            elif not in_str and ch == "/" and i + 1 < len(line) and line[i + 1] == "/":
                cut = i
                break
            i += 1
        out_lines.append(line[:cut])
    return "\n".join(out_lines)


def _warn(code, message):
    return {"code": code, "message": message}


def lint_pine(text):
    """Analyze Pine source text; returns the report dict."""
    src = _strip_comments(text)
    warnings = []

    # --- dependencies (the upfront copy-paste warning) -----------------------
    dependencies = [
        {"author": m[0], "library": m[1], "version": int(m[2]), "alias": m[3] or m[1]}
        for m in _IMPORT_RE.findall(src)
    ]
    if dependencies:
        libs = ", ".join(f'{d["author"]}/{d["library"]}/{d["version"]}' for d in dependencies)
        warnings.append(_warn(
            "LIBRARY_SOURCE_REQUIRED",
            f"This script imports {len(dependencies)} Pine librar"
            f"{'y' if len(dependencies) == 1 else 'ies'} ({libs}). Library source "
            "is NOT auto-fetchable — you must open each library page on "
            "TradingView, click 'Source code', and copy-paste the FULL Pine "
            "source (including its type definitions, needed to decode "
            "positional Settings.new(...) args) into the repo as "
            "<lib>_v<N>.pine. If the pinned version is older than the visible "
            "one, read the release notes to confirm the algorithm is unchanged. "
            "DO NOT reconstruct a library from assumptions — that is the "
            "documented failure mode this pipeline exists to prevent.",
        ))

    # --- semantic-trap flags --------------------------------------------------
    if re.search(r"\bvarip\b", src):
        warnings.append(_warn(
            "VARIP",
            "varip persists within a realtime bar (tick-level state). It has no "
            "equivalent on bar-close data; the port must either run on ticks or "
            "document the divergence on realtime bars.",
        ))
    if "request.security" in src or "request_security" in src:
        warnings.append(_warn(
            "REQUEST_SECURITY",
            "request.security() fetches another symbol/timeframe. Its repaint/"
            "offset behavior must be replicated deliberately; barstate.isconfirmed "
            "is unreliable inside it.",
        ))
    if "lookahead_on" in src:
        warnings.append(_warn(
            "LOOKAHEAD_ON",
            "barmerge.lookahead_on leaks FUTURE data on historical bars unless "
            "offset with [1]. A naive port on completed bars will NOT reproduce "
            "it — replicate the lookahead explicitly.",
        ))
    if re.search(r"\bvar\s+\w", src):
        warnings.append(_warn(
            "VAR_STATE",
            "var declarations carry state across bars -> the logic is path-"
            "dependent. Port bar-by-bar (pine_port.runtime.Series); never "
            "vectorize.",
        ))
    if re.search(r"\bta\.pivot(high|low)\b", src):
        warnings.append(_warn(
            "PIVOT_CONFIRMATION_LAG",
            "ta.pivothigh/pivotlow confirm a pivot only `rightbars` later: the "
            "value appears on the confirmation bar, not the pivot bar. Also, "
            "TradingView does not publish the exact equality rule — pivots MUST "
            "be covered by the golden-master parity test.",
        ))
    if re.search(r"\bbarstate\.is(last|realtime|new)\b", src):
        warnings.append(_warn(
            "REALTIME_BARSTATE",
            "barstate.islast/isrealtime/isnew branches behave differently on "
            "historical vs realtime bars (repaint surface). Decide explicitly "
            "what the port does for these blocks; gate comparisons on confirmed "
            "bars only.",
        ))
    if re.search(r"\btimenow\b", src):
        warnings.append(_warn(
            "TIMENOW",
            "timenow is wall-clock time -> non-deterministic on historical "
            "replay. The port must not depend on it for signal logic.",
        ))

    # --- builtin inventory -----------------------------------------------------
    builtins_used = sorted({f"{ns}.{fn}" for ns, fn in _BUILTIN_RE.findall(src)})
    unsupported = sorted(
        b for b in builtins_used
        if b.split(".")[0] in ("ta", "math") and b not in SUPPORTED_BUILTINS
    )
    if unsupported:
        warnings.append(_warn(
            "UNSUPPORTED_BUILTINS",
            "No Pine-exact implementation in pine_port.runtime yet for: "
            + ", ".join(unsupported)
            + ". Implement them with Pine's published semantics (seeding, na "
            "rules) and verify via the parity test — do NOT substitute "
            "pandas-ta/TA-Lib defaults.",
        ))

    # --- plot inventory ----------------------------------------------------------
    plots = []
    for argtext in _PLOT_RE.findall(src):
        m = _TITLE_KW_RE.search(argtext) or _FIRST_STR_RE.search(argtext)
        if m:
            plots.append(m.group(1))
    if not plots:
        warnings.append(_warn(
            "NO_PLOTS",
            "No plot() calls found. TradingView's CSV export emits ONLY plotted "
            "series — instrument the Pine script with a plot() for every value "
            "you intend to verify (including library-internal values, read back "
            "and plotted) BEFORE exporting the golden CSV.",
        ))

    return {
        "dependencies": dependencies,
        "warnings": warnings,
        "builtins_used": builtins_used,
        "unsupported": unsupported,
        "plots": plots,
    }


def format_report(report, path="<source>"):
    """Human-readable rendering of a lint_pine() report."""
    lines = [f"pine_port lint — {path}", "=" * 60]
    deps = report["dependencies"]
    lines.append(f"\nLibrary imports: {len(deps)}")
    for d in deps:
        lines.append(f'  - {d["author"]}/{d["library"]}/{d["version"]} (as {d["alias"]})')
    lines.append(f"\nPlotted series ({len(report['plots'])} — only these export to CSV):")
    for p in report["plots"]:
        lines.append(f"  - {p}")
    lines.append(f"\nBuiltins used: {', '.join(report['builtins_used']) or '(none)'}")
    if report["unsupported"]:
        lines.append(f"Unsupported by runtime: {', '.join(report['unsupported'])}")
    lines.append(f"\nWarnings ({len(report['warnings'])}):")
    for w in report["warnings"]:
        lines.append(f"\n  [{w['code']}]")
        lines.append(f"  {w['message']}")
    return "\n".join(lines)
