"""
automation_lab.py — the backtest research lab for automating Krish's Daily Long judgment.
==========================================================================================

PURPOSE
  Before any capital is automated, Krish's 7-8 years of discretionary judgment must be
  made explicit and tested. This script sweeps systematic versions of that judgment —
  entry filters (candle strength, relative volume, green-only, remaining R:R), entry
  timing (3:20 close vs next-day open), dynamic exits (early target, breakeven,
  trailing stop) and sizing/rotation — over the SAME V2.1 signals, and scores every
  combination on a walk-forward split:

      TRAIN    = history -> 2024-12-31       (pick what works)
      VALIDATE = 2025-01-01 -> latest bar    (prove it still works on unseen days)

  A combination only "passes" if it keeps max drawdown <= 15% AND stays profitable in
  BOTH windows; passers are ranked by validation CAGR. Unconstrained bests are also
  reported. Two fixed baselines anchor everything:
      s1_equal_weight     — raw V2.1, no judgment (the do-nothing bot)
      lab_krish_manual    — Krish's current rules, encoded (the "human benchmark")

STAGED SWEEP (keeps it to ~1.1k simulations instead of a blind 10k grid)
  A. entry-filter grid x entry timing, natural V2 exits        (~192 combos)
  B. dynamic-exit grid on the top stage-A survivors            (~345 combos)
  C. sizing/rotation variants on the top combos so far         (~30 combos)
  Every stage reuses the ONE up-front signal detection (signals don't depend on policy).

USAGE (on the server, where the data cache lives)
    venv/bin/python scripts/automation_lab.py            # full staged sweep
    venv/bin/python scripts/automation_lab.py --quick    # coarse smoke grid (~40 sims)

OUTPUT -> reports/automation_lab/
    all_combos.csv   every simulation, one row, train_* and val_* metrics
    TOP20.md         ranked leaderboard (passers first) + baselines for scale
    ANSWERS.md       plain-English answers to each of Krish's questions, with the
                     marginal numbers that justify them
"""
import os
import sys
import time
import argparse
import itertools

import pandas as pd

# Windows consoles default to cp1252; force UTF-8 so the Rs glyphs print.
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

from pinescan.backtest.rules.registry import Policy, load_policy
from pinescan.backtest import engine, events
from pinescan.study import MIN_BARS, MARKETS

OUT_DIR = "reports/automation_lab"
DD_CAP = 15.0                                   # Krish's hard constraint, in %
COSTS = {"brokerage_pct": 0.03, "slippage_pct": 0.05, "stt_pct": 0.025}

# The metrics carried into the CSV/tables for each window (name -> metrics key).
_KEEP = ["total_return_pct", "cagr", "max_drawdown_pct", "win_rate", "profit_factor",
         "num_trades", "avg_holding_days", "n_target_hit", "n_stop_hit"]


# ---------------------------------------------------------------------------
# policy construction + one train/validate evaluation
# ---------------------------------------------------------------------------
def make_policy(name, selection_params=None, exit_params=None,
                sizing=("fixed_amount", {"amount": 200_000}),
                rotation=("none", {}), max_concurrent=10, total=2_000_000):
    """A Policy built in code (the sweep would otherwise need hundreds of JSONs)."""
    sel = ("entry_filters", selection_params) if selection_params else \
          ("free_capital_first", {})
    exi = ("lab_exits", exit_params) if exit_params else ("scanner_default", {})
    return Policy(name=name, description="", total_capital=total,
                  max_concurrent=max_concurrent,
                  sizing=sizing[0], sizing_params=sizing[1],
                  selection=sel[0], selection_params=sel[1],
                  rotation=rotation[0], rotation_params=rotation[1],
                  exit=exi[0], exit_params=exi[1], costs=COSTS)


def evaluate(cache, trades, policy, entry_fill, train_end):
    """Run one policy on both walk-forward windows -> (train_metrics, val_metrics)."""
    tm = engine.run_backtest(cache, policy, trades=trades, window_end=train_end,
                             entry_fill=entry_fill).metrics
    vm = engine.run_backtest(cache, policy, trades=trades,
                             window_start=train_end + pd.Timedelta(days=1),
                             entry_fill=entry_fill).metrics
    return tm, vm


def passes(tm, vm):
    """Krish's gate: DD <= 15% and profitable, in BOTH windows."""
    def ok(m):
        return (m["max_drawdown_pct"] is not None and m["max_drawdown_pct"] <= DD_CAP
                and (m["total_return_pct"] or 0) > 0)
    return ok(tm) and ok(vm)


def _row(rid, stage, parent, entry_fill, sel, exi, sizing_lbl, rot_lbl, tm, vm):
    """Flatten one evaluated combo into a CSV/ranking record."""
    r = {"id": rid, "stage": stage, "parent": parent, "entry_fill": entry_fill,
         "min_candle_pos": (sel or {}).get("min_candle_pos"),
         "green_only": (sel or {}).get("green_only", False),
         "rel_vol": (sel or {}).get("rel_vol"),
         "min_rr": (sel or {}).get("min_rr"),
         "early_pct": (exi or {}).get("early_pct"),
         "be_arm_r": (exi or {}).get("be_arm_r"),
         "trail_pct": (exi or {}).get("trail_pct"),
         "sizing": sizing_lbl, "rotation": rot_lbl,
         "passes": passes(tm, vm)}
    for k in _KEEP:
        r[f"train_{k}"] = tm.get(k)
        r[f"val_{k}"] = vm.get(k)
    return r


def _score(r):
    """Ranking key: passers first, then validation CAGR (None ranks last)."""
    v = r["val_cagr"]
    return (r["passes"], -1e18 if v is None else v)


# ---------------------------------------------------------------------------
# the grids
# ---------------------------------------------------------------------------
def grid_filters(quick):
    """Stage A: every entry-filter combination x entry timing (E1-E5)."""
    cps = [None, 0.6] if quick else [None, 0.5, 0.6, 0.7]
    greens = [False, True]
    vols = [None, "gt_prev"] if quick else [None, "gt_prev", "gt_1_2x20d"]
    rrs = [None, 1.0] if quick else [None, 0.75, 1.0, 1.5]
    fills = ["close"] if quick else ["close", "next_open"]
    for cp, g, v, rr, fill in itertools.product(cps, greens, vols, rrs, fills):
        sel = {}
        if cp is not None:
            sel["min_candle_pos"] = cp
        if g:
            sel["green_only"] = True
        if v is not None:
            sel["rel_vol"] = v
        if rr is not None:
            sel["min_rr"] = rr
        yield sel, fill


def grid_exits(quick):
    """Stage B: every dynamic-exit combination (X1-X3); all-off is skipped (== stage A)."""
    earlys = [None, 70] if quick else [None, 60, 70, 80]
    bes = [None, 1.0]
    trails = [None, 10] if quick else [None, 8, 12]
    for e, b, tr in itertools.product(earlys, bes, trails):
        if e is None and b is None and tr is None:
            continue
        exi = {}
        if e is not None:
            exi["early_pct"] = e
        if b is not None:
            exi["be_arm_r"] = b
        if tr is not None:
            exi["trail_pct"] = tr
        yield exi


# stage C variants: (label_sizing, sizing_tuple, label_rotation, rotation_tuple)
_BAND = ("nearest_to_target_band", {"start": 10, "step": 10, "max": 40})
VARIANTS_C = [
    ("pct10", ("percent_of_capital", {"pct": 10}), "none", ("none", {})),
    ("fixed2L", ("fixed_amount", {"amount": 200_000}), "band", _BAND),
    ("pct10", ("percent_of_capital", {"pct": 10}), "band", _BAND),
]


# ---------------------------------------------------------------------------
# report rendering
# ---------------------------------------------------------------------------
def _fmt(v, nd=1):
    if v is None:
        return "N/A"
    if v != v:                                   # NaN
        return "N/A"
    if v == float("inf"):
        return "inf"
    return f"{v:.{nd}f}"


def _combo_words(r):
    """One combo's spec in compact English, for tables."""
    f = []
    if r["min_candle_pos"] is not None:
        f.append(f"close in top {round((1 - r['min_candle_pos']) * 100)}% of range")
    if r["green_only"]:
        f.append("green candle only")
    if r["rel_vol"] == "gt_prev":
        f.append("volume > previous day")
    if r["rel_vol"] == "gt_1_2x20d":
        f.append("volume > 1.2x 20-day avg")
    if r["min_rr"] is not None:
        f.append(f"remaining R:R >= {r['min_rr']}")
    x = []
    if r["early_pct"] is not None:
        x.append(f"early target at {r['early_pct']}% of run")
    if r["be_arm_r"] is not None:
        x.append(f"breakeven after {r['be_arm_r']}R")
    if r["trail_pct"] is not None:
        x.append(f"{r['trail_pct']}% trailing stop")
    bits = ["; ".join(f) if f else "no entry filter",
            "; ".join(x) if x else "V2 natural exits",
            "next-day open entry" if r["entry_fill"] == "next_open" else "3:20 close entry"]
    if r["sizing"] != "fixed2L":
        bits.append("size 10% of equity")
    if r["rotation"] == "band":
        bits.append("rotation on")
    return " · ".join(bits)


def _table(rows, title):
    L = [f"## {title}", "",
         "| # | id | combo | val CAGR% | val DD% | val PF | val trades | train CAGR% | train DD% | pass |",
         "|---|----|-------|-----------|---------|--------|------------|-------------|-----------|------|"]
    for i, r in enumerate(rows, 1):
        L.append("| " + " | ".join([
            str(i), r["id"], _combo_words(r),
            _fmt(r["val_cagr"]), _fmt(r["val_max_drawdown_pct"]),
            _fmt(r["val_profit_factor"], 2), str(r["val_num_trades"]),
            _fmt(r["train_cagr"]), _fmt(r["train_max_drawdown_pct"]),
            "YES" if r["passes"] else "no"]) + " |")
    L.append("")
    return L


def _marginal(rows, col, val_key="val_cagr"):
    """Mean of `val_key` grouped by each distinct value of `col` — the honest 'does
    this dial pay?' view (each group averages over every other dial's settings)."""
    out = {}
    for r in rows:
        out.setdefault(r[col], []).append(r[val_key])
    return {k: (sum(x for x in v if x is not None) / max(1, len([x for x in v if x is not None])),
                len(v))
            for k, v in sorted(out.items(), key=lambda kv: str(kv[0]))}


def _marginal_lines(rows, col, label):
    L = [f"**{label}**", "", "| setting | avg val CAGR% | combos |", "|---|---|---|"]
    for k, (mean, n) in _marginal(rows, col).items():
        L.append(f"| {'off' if k in (None, False) else k} | {_fmt(mean)} | {n} |")
    L.append("")
    return L


def _delta_lines(rows, by_id, col, label):
    """Stage-B/C rows carry a parent id: mean (row - parent) val CAGR per setting —
    the marginal effect of ADDING that leg to an already-good combo."""
    L = [f"**{label}**", "", "| setting | avg val CAGR change vs parent | combos |", "|---|---|---|"]
    groups = {}
    for r in rows:
        p = by_id.get(r["parent"])
        if p is None or r["val_cagr"] is None or p["val_cagr"] is None:
            continue
        groups.setdefault(r[col], []).append(r["val_cagr"] - p["val_cagr"])
    for k, v in sorted(groups.items(), key=lambda kv: str(kv[0])):
        L.append(f"| {'off' if k in (None, False) else k} | {_fmt(sum(v) / len(v))} | {len(v)} |")
    L.append("")
    return L


def write_reports(rows, base_raw, base_krish, last_bar, train_end, elapsed, quick):
    os.makedirs(OUT_DIR, exist_ok=True)
    pd.DataFrame(rows).to_csv(f"{OUT_DIR}/all_combos.csv", index=False)

    ranked = sorted(rows, key=_score, reverse=True)
    sweep = [r for r in ranked if r["stage"] in ("A", "B", "C")]
    passers = [r for r in sweep if r["passes"]]
    by_id = {r["id"]: r for r in rows}

    # ------------------------------ TOP20.md ---------------------------------
    L = ["# Automation Lab — leaderboard", "",
         f"_Data through {last_bar.date()} · train = history->{train_end.date()} · "
         f"validate = {(train_end + pd.Timedelta(days=1)).date()}->{last_bar.date()} · "
         f"capital Rs 20L · gate: DD <= {DD_CAP:.0f}% and profitable in BOTH windows · "
         f"{len(sweep)} combos in {elapsed / 60:.1f} min"
         + (" · QUICK GRID (smoke only)" if quick else "") + "_", ""]
    L += _table([base_raw, base_krish], "Baselines (the bot with no judgment, and Krish encoded)")
    L += _table(sweep[:20], f"Top 20 of the sweep ({len(passers)} of {len(sweep)} passed the gate)")
    unc = sorted(sweep, key=lambda r: -1e18 if r["val_cagr"] is None else r["val_cagr"],
                 reverse=True)[:5]
    L += _table(unc, "Top 5 ignoring the drawdown gate (for reference only)")
    open(f"{OUT_DIR}/TOP20.md", "w", encoding="utf-8").write("\n".join(L))

    # ------------------------------ ANSWERS.md -------------------------------
    A_rows = [r for r in rows if r["stage"] == "A"]
    B_rows = [r for r in rows if r["stage"] == "B"]
    C_rows = [r for r in rows if r["stage"] == "C"]
    win = passers[0] if passers else (sweep[0] if sweep else None)

    L = ["# Automation Lab — answers to Krish's questions", "",
         "Every number below is the average validation-window CAGR across all sweep",
         "combinations sharing that setting — i.e. 'holding everything else mixed, does",
         "turning this dial pay?'. The leaderboard (TOP20.md) has the exact winners.", ""]

    L += ["## E1-E4 · Which entry filters actually pay?", ""]
    L += _marginal_lines(A_rows, "min_candle_pos", "E1 — candle must close near the day's high (min position in range)")
    L += _marginal_lines(A_rows, "green_only", "E3 — skip red confirming candles")
    L += _marginal_lines(A_rows, "rel_vol", "E2 — volume stronger than recent days")
    L += _marginal_lines(A_rows, "min_rr", "E4 — skip when remaining reward:risk is poor")

    L += ["## E5 · Enter at the 3:20 close, or the next day's open?", ""]
    L += _marginal_lines(A_rows, "entry_fill", "entry timing")

    L += ["## X1-X3 · Exits (measured as the CHANGE vs the same combo without that exit)", ""]
    L += _delta_lines(B_rows, by_id, "early_pct", "X1 — early target at % of the run")
    L += _delta_lines(B_rows, by_id, "be_arm_r", "X3 — move stop to breakeven after 1R")
    L += _delta_lines(B_rows, by_id, "trail_pct", "X2 — trailing stop % below peak close")

    L += ["## S1 · Equal Rs 2L per trade, or a % of equity? Rotation?", ""]
    L += _delta_lines(C_rows, by_id, "sizing", "sizing (vs the parent's fixed Rs 2L)")
    L += _delta_lines(C_rows, by_id, "rotation", "rotation (vs the parent's none)")

    L += ["## The verdict", ""]
    for r, tag in [(base_raw, "Raw V2.1, no judgment"), (base_krish, "Krish encoded (manual rules)")]:
        L.append(f"- **{tag}** -> validate CAGR {_fmt(r['val_cagr'])}% at "
                 f"{_fmt(r['val_max_drawdown_pct'])}% DD ({'passes' if r['passes'] else 'FAILS'} the gate)")
    if win:
        L.append(f"- **Best gated combo ({win['id']})** -> validate CAGR {_fmt(win['val_cagr'])}% at "
                 f"{_fmt(win['val_max_drawdown_pct'])}% DD · train CAGR {_fmt(win['train_cagr'])}% at "
                 f"{_fmt(win['train_max_drawdown_pct'])}% DD")
        L.append(f"  - spec: {_combo_words(win)}")
        L.append("")
        L.append("If the verdict holds up to scrutiny, this spec becomes the **NDL-Auto v1** policy")
        L.append("(a committed JSON) and goes to paper-trading in the forward test before any capital.")
    open(f"{OUT_DIR}/ANSWERS.md", "w", encoding="utf-8").write("\n".join(L))
    return win


# ---------------------------------------------------------------------------
# the staged sweep
# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="Automation Lab: staged walk-forward sweep "
                                             "of entry filters / exits / sizing (India).")
    ap.add_argument("--quick", action="store_true", help="coarse smoke grid (~40 sims)")
    ap.add_argument("--train-end", default="2024-12-31",
                    help="last TRAIN date; validation starts the next day")
    args = ap.parse_args()
    train_end = pd.Timestamp(args.train_end)
    t0 = time.time()

    mkt = MARKETS["india"]()
    print("Loading india cache ...")
    cache = mkt.load_cache()
    cache = {s: df for s, df in cache.items() if df is not None and len(df) >= MIN_BARS}
    last_bar = max(df.index.max() for df in cache.values())
    print(f"  {len(cache)} symbols with >= {MIN_BARS} bars, data through {last_bar.date()}")
    if last_bar <= train_end:
        sys.exit(f"ERROR: no validation window — data ends {last_bar.date()} <= "
                 f"train end {train_end.date()}")

    print("Detecting V2 setups once (reused across every simulation) ...")
    trades = []
    for sym, df in cache.items():
        trades += events.trades_for(sym, df)
    print(f"  {len(trades)} entry signals")

    def run(rid, stage, parent, sel, exi, fill, sizing=None, rotation=None,
            sizing_lbl="fixed2L", rot_lbl="none"):
        kw = {}
        if sizing is not None:
            kw["sizing"] = sizing
        if rotation is not None:
            kw["rotation"] = rotation
        pol = make_policy(rid, selection_params=sel or None, exit_params=exi or None, **kw)
        tm, vm = evaluate(cache, trades, pol, fill, train_end)
        return _row(rid, stage, parent, fill, sel, exi, sizing_lbl, rot_lbl, tm, vm)

    rows = []

    # ---- baselines -----------------------------------------------------------
    print("Baselines ...")
    s1 = load_policy(f"{mkt.policy_dir}/s1_equal_weight.json")
    tm, vm = evaluate(cache, trades, s1, "close", train_end)
    base_raw = _row("BASE_raw_v21", "baseline", None, "close", {}, {}, "fixed2L", "none", tm, vm)
    km = load_policy(f"{mkt.policy_dir}/lab_krish_manual.json")
    tm, vm = evaluate(cache, trades, km, "close", train_end)
    base_krish = _row("BASE_krish_manual", "baseline", None, "close",
                      km.selection_params, km.exit_params, "fixed2L", "none", tm, vm)
    rows += [base_raw, base_krish]
    for b in (base_raw, base_krish):
        print(f"  {b['id']:18s} val CAGR {_fmt(b['val_cagr']):>6s}%  "
              f"DD {_fmt(b['val_max_drawdown_pct'])}%  {'PASS' if b['passes'] else 'fail'}")

    # ---- sanity: raw baseline over the trailing 5y (compare with the old study) ----
    m5 = engine.run_backtest(cache, s1, trades=trades,
                             window_start=last_bar - pd.DateOffset(years=5)).metrics
    print(f"  sanity (s1 over trailing 5y, must match the strategy-matrix study): "
          f"return {_fmt(m5['total_return_pct'])}%  {m5['num_trades']} trades")

    # ---- stage A: entry filters x entry timing -------------------------------
    combos = list(grid_filters(args.quick))
    print(f"Stage A — {len(combos)} filter/timing combos, natural exits ...")
    for i, (sel, fill) in enumerate(combos):
        rows.append(run(f"A{i:03d}", "A", None, sel, {}, fill))
        if (i + 1) % 25 == 0:
            print(f"  {i + 1}/{len(combos)}  ({time.time() - t0:.0f}s)")
    A_rows = [r for r in rows if r["stage"] == "A"]
    keep_a = 4 if args.quick else 15
    survivors = sorted(A_rows, key=_score, reverse=True)[:keep_a]
    if not any(r["passes"] for r in survivors):
        print("  WARNING: no stage-A combo passed the DD<=15% gate; carrying best anyway")
    print(f"  kept {len(survivors)} survivors "
          f"({sum(1 for r in survivors if r['passes'])} pass the gate)")

    # ---- stage B: dynamic exits on the survivors ------------------------------
    exits = list(grid_exits(args.quick))
    print(f"Stage B — {len(exits)} exit combos x {len(survivors)} survivors ...")
    n = 0
    for s in survivors:
        sel = {k: s[k] for k in ("min_candle_pos", "green_only", "rel_vol", "min_rr")
               if s[k] not in (None, False)}
        for exi in exits:
            rows.append(run(f"B{n:03d}", "B", s["id"], sel, exi, s["entry_fill"]))
            n += 1
            if n % 50 == 0:
                print(f"  {n}/{len(exits) * len(survivors)}  ({time.time() - t0:.0f}s)")

    # ---- stage C: sizing / rotation on the best combos so far -----------------
    pool = sorted([r for r in rows if r["stage"] in ("A", "B")], key=_score, reverse=True)
    keep_c = 3 if args.quick else 10
    top = pool[:keep_c]
    print(f"Stage C — {len(VARIANTS_C)} sizing/rotation variants x {len(top)} top combos ...")
    n = 0
    for s in top:
        sel = {k: s[k] for k in ("min_candle_pos", "green_only", "rel_vol", "min_rr")
               if s[k] not in (None, False)}
        exi = {k: s[k] for k in ("early_pct", "be_arm_r", "trail_pct") if s[k] is not None}
        for sz_lbl, sz, rot_lbl, rot in VARIANTS_C:
            rows.append(run(f"C{n:03d}", "C", s["id"], sel, exi, s["entry_fill"],
                            sizing=sz, rotation=rot, sizing_lbl=sz_lbl, rot_lbl=rot_lbl))
            n += 1

    # ---- reports ---------------------------------------------------------------
    elapsed = time.time() - t0
    win = write_reports(rows, base_raw, base_krish, last_bar, train_end, elapsed, args.quick)
    print(f"\n{len(rows)} simulations in {elapsed / 60:.1f} min -> {OUT_DIR}/")
    print("  all_combos.csv · TOP20.md · ANSWERS.md")
    if win:
        print(f"  best gated combo: {win['id']} — {_combo_words(win)}")
        print(f"    validate CAGR {_fmt(win['val_cagr'])}% at DD {_fmt(win['val_max_drawdown_pct'])}%")


if __name__ == "__main__":
    main()
