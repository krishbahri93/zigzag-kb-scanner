"""CLI for the pinescan.core pipeline.

  python -m pinescan.core lint <file.pine> [--json]
      Pre-port analysis: library imports (copy-paste required!), semantic
      traps, builtin inventory, plotted-series inventory.

  python -m pinescan.core parity --csv <golden.csv> --port <module:function>
                             [--abs-tol X] [--rel-tol X] [--keep-last]
                             [--snapshot out.json] [--json]
      Golden-master diff. <module:function> is imported and called with the
      golden DataFrame; it must return {plot_title: [values...]} bar-aligned
      to the CSV. Exits non-zero on divergence. On pass, --snapshot saves a
      regression golden master.
"""
import argparse
import importlib
import json
import sys

from . import lint as _lint
from . import parity as _parity


def _cmd_lint(args):
    with open(args.file, "r", encoding="utf-8") as f:
        text = f.read()
    report = _lint.lint_pine(text)
    if args.json:
        print(json.dumps(report, indent=1))
    else:
        print(_lint.format_report(report, path=args.file))
    return 0


def _cmd_parity(args):
    golden = _parity.load_tv_csv(args.csv)
    mod_name, _, fn_name = args.port.partition(":")
    if not fn_name:
        print("error: --port must be <module>:<function>", file=sys.stderr)
        return 2
    sys.path.insert(0, ".")
    fn = getattr(importlib.import_module(mod_name), fn_name)
    outputs = fn(golden)
    report = _parity.compare(
        golden, outputs, drop_last=not args.keep_last,
        abs_tol=args.abs_tol, rel_tol=args.rel_tol,
    )
    if args.json:
        print(json.dumps(report, indent=1))
    else:
        print(_parity.format_report(report))
    if report["passed"] and args.snapshot:
        _parity.save_snapshot(args.snapshot, outputs)
        print(f"snapshot saved: {args.snapshot}")
    return 0 if report["passed"] else 1


def main(argv=None):
    p = argparse.ArgumentParser(prog="pinescan.core", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    pl = sub.add_parser("lint", help="static pre-port analysis of a .pine file")
    pl.add_argument("file")
    pl.add_argument("--json", action="store_true")
    pl.set_defaults(func=_cmd_lint)

    pp = sub.add_parser("parity", help="golden-master diff vs a TradingView CSV export")
    pp.add_argument("--csv", required=True)
    pp.add_argument("--port", required=True, help="<module>:<function>(df)->dict")
    pp.add_argument("--abs-tol", type=float, default=1e-8)
    pp.add_argument("--rel-tol", type=float, default=1e-5)
    pp.add_argument("--keep-last", action="store_true",
                    help="compare the last bar too (it repaints — off by default)")
    pp.add_argument("--snapshot", help="on pass, save outputs as a regression golden master")
    pp.add_argument("--json", action="store_true")
    pp.set_defaults(func=_cmd_parity)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
