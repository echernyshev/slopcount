from __future__ import annotations

from slopcount.evidence import Category, Evidence
from slopcount.extractors import extract_comments
from slopcount.rules import PhraseRule
from slopcount.scanner import ScannedFile


class PhraseDetector:
    """Matches phrase rules against comment zones of code files and every
    line of prose/markdown files. For code, zones are the comment blocks
    (incl. docstrings) reported by the extractors; CommentBlock spans
    exactly len(lines) physical lines from start_line, so entry k of a
    block lives at physical line start_line + k."""

    category = Category.PROSE

    def __init__(self, rules: list[PhraseRule]):
        self.rules = rules

    def detect(self, sf: ScannedFile, text: str) -> list[Evidence]:
        if sf.kind == "code":
            zones = [
                (b.start_line + k, line)
                for b in extract_comments(text, sf.language or "")
                for k, line in enumerate(b.lines)
            ]
        else:  # markdown / prose
            zones = list(enumerate(text.split("\n"), 1))
        out: list[Evidence] = []
        for line_no, line in zones:
            for r in self.rules:
                if r.pattern.search(line):
                    out.append(Evidence(sf.path, line_no, self.category,
                                        r.weight, r.description))
        return out
