from __future__ import annotations

import sys
from pathlib import Path
from typing import Literal

import typer

from slopcount import __version__, i18n
from slopcount.app import Options, run
from slopcount.i18n import _
from slopcount.render import ansi
from slopcount.render.csv_out import render_csv
from slopcount.render.json_out import render_json
from slopcount.render.text import (
    render_comprehension,
    render_evidence,
    render_slop,
    render_volume,
)

app = typer.Typer()


def _version(value: bool) -> None:
    if value:
        typer.echo(f"slopcount {__version__}")
        raise typer.Exit()


@app.command(context_settings={"help_option_names": ["-h", "--help"]})
def scan(
    paths: list[str] | None = typer.Argument(  # noqa: B008 — идиоматика typer
        None, help="Directory to scan (default: .)"
    ),
    evidence: bool = typer.Option(
        False, "--evidence", help="List every finding with its source line"
    ),
    json_out: bool = typer.Option(False, "--json", help="Print JSON report"),
    csv_out: bool = typer.Option(False, "--csv", help="Print CSV report"),
    history: int | None = typer.Option(None, "--history", help="Git history depth to scan"),
    perplexity: bool = typer.Option(False, "--perplexity", help="Perplexity detector (extras)"),
    rules: list[Path] | None = typer.Option(  # noqa: B008 — идиоматика typer
        None, "--rules", help="Extra rules TOML (repeatable)"
    ),
    scc_path: str | None = typer.Option(
        None, "--scc-path", help="Path to the scc binary (else PATH/env/download)"
    ),
    lang: Literal["en", "ru"] | None = typer.Option(None, "--lang", help="Interface language"),
    personcost: float = typer.Option(4690.50, "--personcost", help="Monthly person cost, USD"),
    overhead: float = typer.Option(
        2.4, "--overhead", help="Cost overhead multiplier (COCOMO and SLOCOMO)"
    ),
    coffee_price: float = typer.Option(4.0, "--coffee-price", help="Coffee cup price, USD"),
    no_therapy: bool = typer.Option(False, "--no-therapy", help="Skip the therapy estimate"),
    color: bool | None = typer.Option(
        None, "--color/--no-color", help="ANSI colors in the text report (default: auto)"
    ),
    wide: bool = typer.Option(False, "--wide", help="Wide table layout"),
    version: bool | None = typer.Option(
        None, "--version", callback=_version, is_eager=True, help="Show version and exit"
    ),
) -> None:
    """Count the AI slop in a project and the cost of comprehending it."""
    i18n.setup(lang)
    opts = Options(
        paths=paths or ["."],
        evidence=evidence,
        json_out=json_out,
        csv_out=csv_out,
        history=history,
        perplexity=perplexity,
        rules=rules or [],
        scc_path=scc_path,
        lang=lang,
        personcost=personcost,
        overhead=overhead,
        coffee_price=coffee_price,
        no_therapy=no_therapy,
        wide=wide,
    )
    root = Path(opts.paths[0])
    if not root.exists():
        print(_("slopcount: path not found: {path}").format(path=root), file=sys.stderr)
        raise typer.Exit(code=2)
    if root.is_file():
        print(
            _("slopcount: path is a file, directory expected: {path}").format(path=root),
            file=sys.stderr,
        )
        raise typer.Exit(code=2)
    try:
        report = run(opts)
    except RuntimeError as e:  # напр. --perplexity без extras: подсказка, exit 2
        print(e, file=sys.stderr)
        raise typer.Exit(code=2) from e
    if json_out:
        print(render_json(report))
    elif csv_out:
        print(render_csv(report), end="")
    else:
        # Явный флаг бьёт авто-детект (NO_COLOR/isatty) — как --color=always.
        ansi.set_enabled(color if color is not None else ansi.autodetect())
        print(render_volume(report))
        print(render_comprehension(report))
        print(render_slop(report))
        if evidence:
            print(render_evidence(report))


def main(argv: list[str] | None = None) -> int:
    try:
        app(argv)
    except SystemExit as e:  # typer/click: --version (0) / usage error (2) / Exit(N)
        return int(e.code or 0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
