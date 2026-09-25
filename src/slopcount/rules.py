from __future__ import annotations

import re
from dataclasses import dataclass
from importlib import resources
from pathlib import Path

from slopcount.i18n import _


@dataclass(frozen=True)
class PhraseRule:
    pattern: re.Pattern
    weight: int
    description: str


def load_rules(extra_paths: list[Path] | None = None) -> list[PhraseRule]:
    """Load built-in phrase catalogs (en, ru) plus any user-supplied TOML files.

    Each catalog is a sequence of ``[[rule]]`` tables with ``pattern``
    (a regex, compiled case-insensitively), ``weight`` (int, default 1)
    and ``description`` (str, default ""). Missing files warn on stderr
    and are skipped; a malformed regex raises :class:`re.error` from compile.
    """
    import os
    import sys
    import tomllib

    rules: list[PhraseRule] = []
    names = ["phrases_en.toml", "phrases_ru.toml"]
    base = resources.files("slopcount").joinpath("rules")
    paths = [Path(os.fspath(base / n)) for n in names] + list(extra_paths or [])
    for p in paths:
        if not p.is_file():
            print(_("slopcount: rules file not found, skipped: {p}").format(p=p),
                  file=sys.stderr)
            continue
        data = tomllib.loads(p.read_text(encoding="utf-8"))
        for r in data.get("rule", []):
            rules.append(PhraseRule(
                pattern=re.compile(r["pattern"], re.IGNORECASE),
                weight=int(r.get("weight", 1)),
                description=r.get("description", ""),
            ))
    return rules
