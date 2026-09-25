from __future__ import annotations

import argparse
from pathlib import Path

from slopcount import __version__, i18n
from slopcount.app import Options, run
from slopcount.render.text import render_slocomo, render_text, render_verdict


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
    report = run(opts)
    print(render_text(report))
    slocomo = render_slocomo(report)
    if slocomo:
        print(slocomo)
    print(render_verdict(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
