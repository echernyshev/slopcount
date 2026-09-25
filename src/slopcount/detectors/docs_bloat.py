from __future__ import annotations

import re
from dataclasses import dataclass

from slopcount.detectors import EMOJI_RE
from slopcount.evidence import Category, Evidence
from slopcount.i18n import _, ngettext
from slopcount.scanner import ScannedFile

_EMOJI_HEADER = re.compile(r"^#{1,6}\s.*" + EMOJI_RE.pattern)


@dataclass(frozen=True)
class DocsBloatResult:
    evidences: list[Evidence]
    infected: list[tuple[str, int]]   # (путь, всего строк файла)


class DocsBloatDetector:
    category = Category.DOCS

    def detect(self, sf: ScannedFile, text: str) -> DocsBloatResult:
        lines = text.split("\n")
        # физические строки: хвостовой "\n" даёт пустой последний элемент
        total = len(lines) - (1 if lines and lines[-1] == "" else 0)
        ev: list[Evidence] = []
        weight = 0
        if total > 500:
            ev.append(Evidence(sf.path, 0, self.category, 5,
                               ngettext("spec giant: %d line",
                                        "spec giant: %d lines", total) % total))
            weight += 5
        for i, line in enumerate(lines, 1):
            if _EMOJI_HEADER.match(line):
                ev.append(Evidence(sf.path, i, self.category, 2,
                                   _("emoji-decorated section header")))
                weight += 2
        infected: list[tuple[str, int]] = []
        if total > 0 and weight / total > 0.1:
            infected.append((sf.path, total))
        return DocsBloatResult(ev, infected)


def repo_bloat_evidence(files: list[ScannedFile], sloc: int) -> Evidence | None:
    """Spec-to-Code Ratio из спеки §4.2: >100 КБ markdown на KLOC — тревога."""
    docs_bytes = sum(f.size for f in files if f.kind == "markdown")
    if sloc == 0:
        # docs-only repo: ratio undefined, signal comes from infection instead
        return None
    kb_per_kloc = docs_bytes / 1024 / (sloc / 1000)
    if kb_per_kloc > 100:
        return Evidence("<repo>", 0, Category.DOCS, 4,
                        _("docs bloat: %.0f KB of markdown per KLOC") % kb_per_kloc)
    return None
