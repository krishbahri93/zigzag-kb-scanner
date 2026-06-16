# ZZ KB Nested Swings V2 — Python port

Faithful port of `zigzag_kb_Indicator_nested_v2_pinescript.txt` (Pine v6),
built with the `pine_port` pipeline. Engine: `nsv2_engine.py`. Tests:
`test_nsv2_engine.py` (22, all passing).

## Status

| Stage | State |
|---|---|
| Library source (`TradingView/ZigZag/7`) | ✅ Reuses verified `tv_zigzag.py` — no new paste needed |
| Builtins | ✅ All supported (`ta.ema`, `ta.sma`, `array.*` → Python lists) |
| Port (bar-by-bar, no lookahead) | ✅ `nsv2_engine.py`, 22 unit/integration tests green |
| Instrumented Pine for export | ✅ `zigzag_kb_Indicator_nested_v2_instrumented.pine` |
| **Golden-master parity** | ⏳ **needs your TradingView CSV export** (see below) |

The unit tests prove the new/novel logic (two-instance ZigZag streaming that
matches `tv_zigzag.detect_pivots` bar-for-bar, B detection, the nested-peak
walk, the per-swing state machine). They are **not** the equivalence proof —
only the golden CSV is.

## What the port reproduces

- **Two ZigZag instances**: `zzB` at devThreshold = Min Decline % (default 35)
  sets the common low **B**; `zzP` at Peak Sensitivity % (default 25) finds the
  nested peaks. Both depth 10 → internally halved to 5 (the library's
  `floor(depth/2)`).
- **B** = end of the most recent down-leg (latest confirmed low).
- **Nested peaks A0..A3** via the nearest-first walk back from B: B*gapMul
  floor, "keep the higher of two close peaks", new-nested vs keep-higher,
  stop-at-any-low-below-B, maxSwings cap.
- **Per-swing state machine** (independent T1..T4): entry on a confirmed close
  crossing 0.382 from below + EMA9/21 + 1.2× volume; TP when high reaches
  0.618; SL when close < 0.236 (re-arms); TP terminal.

No-lookahead: pivots are streamed bar-by-bar (`_Pivots`), so B/peaks/levels are
exactly what the chart had on each bar — a pivot at bar *i* is known only
`eff_depth` bars later.

## The `run(df)` contract

`nsv2_engine.run(df)` returns `{title: [values...]}` bar-aligned to `df`, with
titles matching the instrumented Pine's plots **exactly**:

```
EMA 9, EMA 21,  B,  A0, A1, A2, A3,  ST0, ST1, ST2, ST3,  ENTRY, TP, SL
```

- `B`, `A0..A3` — prices (na when absent)
- `ST0..ST3` — per-swing state each bar (0 pre-B, then 1 wait / 2 in / 3 TP)
- `ENTRY/TP/SL` — `1.0` on a bar where any swing fires that event, else na

`df` accepts TradingView-CSV columns (`open/high/low/close/volume`) or
Title-case OHLCV.

## Verify it (the one step that needs you)

1. Load **`zigzag_kb_Indicator_nested_v2_instrumented.pine`** in TradingView.
   It is the original indicator plus a parity block that plots B, A0–A3,
   ST0–ST3, and ENTRY/TP/SL into the **data window** (the strategy values
   otherwise live in labels/tables and never export). Behavior is unchanged.
2. Pick a symbol + timeframe. **Export chart data → CSV** (paid plan).
   Record symbol, timeframe, timezone, bar range.
3. Run the diff:
   ```
   python -m pine_port parity --csv your_export.csv --port nsv2_engine:run --snapshot nsv2_golden.json
   ```
   - PASS (exit 0) → snapshot saved as the regression golden master.
   - FAIL → prints the first diverging bars with timestamps, per series. The
     state series (`ST0..ST3`) localize exactly where the machine drifts.
4. Use defaults matching the Pine inputs. If you changed any input on the chart
   (Min Decline %, Peak Sensitivity %, depth, maxSwings, min gap, fib levels),
   pass them through — `run(df, params=...)` accepts the same keys (see
   `nsv2_engine.DEFAULTS`).

**No paid plan?** Transcribe 30–50 bars around a setup (the B bar, each peak,
and the entry/TP/SL bars) into the same CSV format and diff that. It catches
wrong-algorithm divergence; it is not the full bar-for-bar proof.

## Known UNVERIFIED-until-CSV points

- The exact bar a pivot **confirms** (depends on the library's `>=`/`>`
  equality rule, which TradingView doesn't publish). `tv_zigzag` is
  chart-verified on the dual-trade indicator, but the two-instance, finer
  (dev=25) `zzP` here exercises more/closer pivots — the CSV must confirm A0–A3
  land on the same bars.
- The nested-peak `time` chosen by the keep-higher rule (price is unambiguous;
  the bar index it carries should be checked).
