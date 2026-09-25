from __future__ import annotations

import argparse
import sys
from pathlib import Path

from slopcount import __version__, i18n
from slopcount.app import Options, run
from slopcount.i18n import _
from slopcount.render.csv_out import render_csv
from slopcount.render.json_out import render_json
from slopcount.render.text import render_details, render_slocomo, render_text, render_verdict


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="slopcount",
        description="Count the AI slop in a project and the cost of comprehending it.")
    p.add_argument("--version", action="version", version=f"slopcount {__version__}")
    p.add_argument("paths", nargs="*", default=["."])
    p.add_argument("--details", action="store_true")
    p.add_argument("--json", dest="json_out", action="store_true")
    p.add_argument("--csv", dest="csv_out", action="store_true")
    p.add_argument("--history", nargs="?", const=500, type=int, default=None)
    p.add_argument("--perplexity", action="store_true")
    p.add_argument("--rules", action="append", type=Path, default=[])
    p.add_argument("--lang", choices=["en", "ru"], default=None)
    p.add_argument("--personcost", type=float, default=4690.50)
    p.add_argument("--overhead", type=float, default=2.4)
    p.add_argument("--coffee-price", type=float, default=4.0)
    p.add_argument("--no-therapy", action="store_true")
    p.add_argument("--fail-above", type=float, default=None)
    p.add_argument("--verdict-only", action="store_true")
    p.add_argument("--wide", action="store_true")
    return p


def main(argv=None) -> int:
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as e:  # argparse: --version (0) / usage error (2)
        return int(e.code or 0)
    i18n.setup(args.lang)
    opts = Options(
        paths=args.paths or ["."], details=args.details, json_out=args.json_out,
        csv_out=args.csv_out, history=args.history, perplexity=args.perplexity,
        rules=args.rules, lang=args.lang, personcost=args.personcost,
        overhead=args.overhead, coffee_price=args.coffee_price,
        no_therapy=args.no_therapy, fail_above=args.fail_above,
        verdict_only=args.verdict_only, wide=args.wide)
    root = Path(opts.paths[0])
    if not root.exists():
        print(_("slopcount: path not found: {path}").format(path=root),
              file=sys.stderr)
        return 2
    if root.is_file():
        print(_("slopcount: path is a file, directory expected: {path}")
              .format(path=root), file=sys.stderr)
        return 2
    try:
        report = run(opts)
    except RuntimeError as e:  # напр. --perplexity без extras: подсказка, exit 2
        print(e, file=sys.stderr)
        return 2
    if args.json_out:
        print(render_json(report))
    elif args.csv_out:
        print(render_csv(report), end="")
    elif args.verdict_only:
        print(render_verdict(report))
    else:
        print(render_text(report))
        print(render_slocomo(report))
        print(render_verdict(report))
        if args.details:
            print(render_details(report))
    if opts.fail_above is not None and report.slop_ratio > opts.fail_above:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
