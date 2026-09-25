from __future__ import annotations

import re
from collections.abc import Callable

from slopcount.evidence import Category, Evidence
from slopcount.extractors import extract_comments
from slopcount.scanner import ScannedFile

_EMOJI = re.compile(r"[\U0001F300-\U0001FAFF☀-⟿⬀-⯿]")
_TRIVIAL_DOC = re.compile(
    r"^(Adds?|Returns?|Gets?|Sets?|Creates?|Initiali[sz]es?|Updates?|Checks?)\b", re.I)
_CATCH_ALL = re.compile(
    r"except\s+(Exception|BaseException)|catch\s*\(\s*(e|err|error|Exception)")


class CodeStyleDetector:
    category = Category.STYLE

    def detect(self, sf: ScannedFile, text: str) -> list[Evidence]:
        checks: list[Callable[[ScannedFile, str], list[Evidence]]] = [
            self._docstrings, self._catch_all, self._emoji_comments,
            self._docstring_perfection, self._monotone_comments]
        out: list[Evidence] = []
        for check in checks:
            out.extend(check(sf, text))
        return out

    def _docstrings(self, sf, text) -> list[Evidence]:
        evs = []
        blocks = [b for b in extract_comments(text, sf.language or "") if b.is_docstring]
        code_lines = len([l for l in text.split("\n") if l.strip()])
        for b in blocks:
            n = len(b.lines)
            first = b.lines[0] if b.lines else ""
            if n <= 2 and _TRIVIAL_DOC.match(first):
                evs.append(Evidence(sf.path, b.start_line, self.category, 2,
                                    "trivial docstring on obvious function"))
            if code_lines and n / max(code_lines, 1) > 0.5 and n >= 5:
                evs.append(Evidence(sf.path, b.start_line, self.category, 2,
                                    f"docstring longer than body ({n} lines)"))
        return evs

    def _catch_all(self, sf, text) -> list[Evidence]:
        evs = []
        total = 0
        for i, line in enumerate(text.split("\n"), 1):
            if _CATCH_ALL.search(line):
                total += 1
                evs.append(Evidence(sf.path, i, self.category, 1,
                                    "catch-all exception swallowing"))
        if total >= 5:
            evs.append(Evidence(sf.path, 0, self.category, 2,
                                f"defensive catch-all density ({total})"))
        return evs

    def _emoji_comments(self, sf, text) -> list[Evidence]:
        evs = []
        for b in extract_comments(text, sf.language or ""):
            for k, line in enumerate(b.lines):
                if _EMOJI.search(line):
                    evs.append(Evidence(sf.path, b.start_line + k, self.category, 2,
                                        "emoji in code comment"))
        return evs

    _GOOGLE = re.compile(r"\b(Args|Parameters|Returns|Raises)\s*:", re.I)
    _DEF_LINE = re.compile(r"^\s*(?:async\s+)?def\s+\w+")

    def _docstring_perfection(self, sf, text) -> list[Evidence]:
        lines = text.split("\n")
        defs = [i for i, l in enumerate(lines, 1) if self._DEF_LINE.match(l)]
        if len(defs) < 5:
            return []
        doc_starts = {b.start_line for b in extract_comments(text, sf.language or "")
                      if b.is_docstring}
        perfect = sum(
            1 for d in defs
            if any(ds == d + 1 for ds in doc_starts)
            and any(self._GOOGLE.search(l) for l in lines[d:d + 15]))
        if perfect / len(defs) >= 0.8:
            return [Evidence(sf.path, 0, self.category, 2,
                             f"textbook-perfect docstrings on {perfect}/{len(defs)} functions")]
        return []

    def _monotone_comments(self, sf, text) -> list[Evidence]:
        lens = [len(line) for b in extract_comments(text, sf.language or "")
                for line in b.lines if line]
        if len(lens) < 10:
            return []
        mean = sum(lens) / len(lens)
        var = sum((x - mean) ** 2 for x in lens) / len(lens)
        if var < 25:
            return [Evidence(sf.path, 0, self.category, 2,
                             f"monotone comment length (var={var:.1f}) — machine cadence")]
        return []
