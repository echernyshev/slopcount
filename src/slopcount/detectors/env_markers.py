from __future__ import annotations

import fnmatch
import re
from collections.abc import Callable
from dataclasses import dataclass
from importlib import resources
from pathlib import Path

from slopcount.evidence import Category, Evidence
from slopcount.i18n import _
from slopcount.scanner import ScannedFile


@dataclass(frozen=True)
class _Header:
    pattern: re.Pattern
    weight: int
    description: str


def _load():
    """Внутренний каталог; битый TOML падает сразу (fail fast, ассет в пакете)."""
    import tomllib
    base = resources.files("slopcount").joinpath("rules/env_markers.toml")
    data = tomllib.loads(Path(str(base)).read_text(encoding="utf-8"))
    paths = [(m["path"], m["weight"], _(m["description"]))
             for m in data.get("marker", [])]
    headers = [_Header(re.compile(h["pattern"]), h["weight"], _(h["description"]))
               for h in data.get("header", [])]
    return paths, headers


class EnvMarkerDetector:
    category = Category.AGENCY

    def __init__(self):
        self.paths, self.headers = _load()

    def detect(self, root: Path, scanned: list[ScannedFile],
               reader: Callable[[Path], str | None]) -> list[Evidence]:
        evs: list[Evidence] = []
        names = [sf.path for sf in scanned] + _all_entries(root)
        for pat, weight, desc in self.paths:
            for name in names:
                if fnmatch.fnmatch(name, pat) or fnmatch.fnmatch(Path(name).name, pat):
                    evs.append(Evidence(name, 0, self.category, weight, desc))
                    break
        for sf in scanned:
            if sf.kind == "other":
                continue
            text = reader(root / sf.path)
            if not text:
                continue
            for line in text.split("\n")[:5]:
                for h in self.headers:
                    if h.pattern.search(line):
                        evs.append(Evidence(sf.path, 1, self.category,
                                            h.weight, h.description))
        return evs


def _all_entries(root: Path) -> list[str]:
    out = []
    for p in root.iterdir():
        out.append(p.name)
    return out
