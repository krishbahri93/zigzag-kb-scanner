# pine_port — Pine Script → Python conversion pipeline

A reusable pipeline for porting TradingView Pine Script to Python with
**zero behavioral differences**, proven by a bar-for-bar diff against data
exported from TradingView itself. Distilled from a real failure-then-fix
(see `../PINE_PORTING.md` for the methodology and case study).

> **⚠ Read this before you start — two things only YOU can provide**
>
> 1. **Library source.** If your script has `import author/Lib/N` lines, the
>    library source must be **copy-pasted by you** from TradingView (script
>    page → "Source code", including type definitions). It is not fetchable
>    by any tool. The pipeline stops until you paste it — a port written
>    from assumptions passes every test and still diverges.
> 2. **Golden CSV.** The equivalence proof needs a TradingView
>    **"Export chart data"** CSV (paid plan, ~10–20k bar cap) of the
>    instrumented script.

## Pipeline

```
.pine file
   │
   ▼
1. LINT (deterministic)            python -m pine_port lint my.pine
   imports → copy-paste warning, semantic traps, plotted-series inventory
   │
   ▼
2. OBTAIN LIBRARY SOURCE (you)     paste <lib>_vN.pine into the repo
   STOP GATE: no source → no port. Pinned older version? Check release notes.
   │
   ▼
3. AUTHOR THE PORT                 from pine_port import runtime
   bar-by-bar, Pine-exact ta.* (sma/ema/rma seeding, na rules, pivots)
   expose run(df) -> {plot_title: [values...]}
   │
   ▼
4. INSTRUMENT THE PINE (you+us)    plot() every series to verify —
   the CSV exports ONLY plotted series; library-internal values must be
   read back into the indicator and plotted
   │
   ▼
5. EXPORT GOLDEN CSV (you)         TradingView "Export chart data"
   record symbol, timeframe, timezone, bar range
   │
   ▼
6. PARITY (deterministic)          python -m pine_port parity \
                                     --csv golden.csv --port my_port:run
   bar-for-bar, last bar dropped (repaints), na-aware, explicit tolerance
   │
   ▼
7. SNAPSHOT (deterministic)        ... --snapshot golden.json
   regression golden master for all future changes
```

## Authoring a port

```python
# my_port.py
from pine_port import runtime as rt

def run(df):
    """df: the golden CSV DataFrame (time/open/high/low/close[/volume]).
    Returns {plot_title: [values...]} bar-aligned to df."""
    close = df["close"].tolist()
    ema21 = rt.ema(close, 21)                      # Pine seeding, not pandas ewm
    buy = [
        not rt.is_na(e) and c > e                   # na-aware, like Pine
        for c, e in zip(close, ema21)
    ]
    return {"EMA21": ema21, "Buy": [1.0 if b else rt.na for b in buy]}
```

Run the parity gate:

```
python -m pine_port parity --csv golden.csv --port my_port:run --snapshot golden.json
```

Exit code 0 = every plotted series matches every confirmed bar. Anything else
prints the first divergences with bar timestamps.

## Hard rules (each one is a documented real failure)

- **Never reconstruct an imported library** — the official ZigZag silently
  halves its `depth` input; no reconstruction survives that.
- **Never use pandas `ewm` / pandas-ta / TA-Lib for `ta.*`** — seeding and
  na rules differ from Pine (head-of-series divergence).
- **Never vectorize `var`/`varip`/pivot/trailing logic** — Pine is
  bar-by-bar; use `runtime.Series`.
- **Never compare the last bar** — it repaints. `parity` drops it by default.
- **Synthetic tests are not proof** — only the golden CSV is.

## Files

| File | Purpose |
|---|---|
| `lint.py` | static pre-port analyzer (`lint_pine`, `format_report`) |
| `runtime.py` | Pine-exact builtins (`Series`, `na/nz`, `ta.*`) |
| `parity.py` | golden-master diff + regression snapshots |
| `__main__.py` | CLI (`lint`, `parity`) |
| `../test_pine_port.py` | test suite (27 tests) |
| `../.claude/skills/pine-to-python/SKILL.md` | agent workflow skill |
| `../PINE_PORTING.md` | full methodology + ZigZag case study |

`runtime` docstrings flag any semantic detail TradingView does not publish as
**UNVERIFIED vs TV** (e.g. pivot equality rules) — make sure your golden CSV
exercises those paths.

## Reusing in another project

Copy the `pine_port/` package (stdlib + pandas only) and the
`.claude/skills/pine-to-python/` skill into the target repo. The skill keeps
agents on the rails; the package does the deterministic work.
