from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from slopcount.detectors.code_style import CodeStyleDetector
from slopcount.detectors.docs_bloat import DocsBloatDetector, repo_bloat_evidence
from slopcount.detectors.phrase import PhraseDetector
from slopcount.evidence import Evidence, Report, aggregate
from slopcount.metrics.sloc import count_sloc
from slopcount.rules import load_rules
from slopcount.scanner import ScannedFile, read_text, scan


@dataclass
class Options:
    paths: list[str] = field(default_factory=lambda: ["."])
    details: bool = False
    json_out: bool = False
    csv_out: bool = False
    history: int | None = None
    perplexity: bool = False
    rules: list[Path] = field(default_factory=list)
    lang: str | None = None
    personcost: float = 4690.50
    overhead: float = 2.4
    coffee_price: float = 4.0
    no_therapy: bool = False
    fail_above: float | None = None
    verdict_only: bool = False
    wide: bool = False


def flagged_words(text: str, evidences: list[Evidence]) -> int:
    lines = text.split("\n")
    uniq = {e.line for e in evidences if e.line > 0 and e.line <= len(lines)}
    return sum(len(lines[l - 1].split()) for l in uniq)


def run(opts: Options) -> Report:
    root = Path(opts.paths[0])
    files: list[ScannedFile] = scan(root)
    phrase = PhraseDetector(load_rules(opts.rules))
    docs_bloat = DocsBloatDetector()
    style_detector = CodeStyleDetector()
    evidences: list[Evidence] = []
    infected: list[tuple[str, int]] = []
    sloc = 0
    skip = 0
    for sf in files:
        if sf.kind not in ("code", "markdown", "prose"):
            continue
        text = read_text(root / sf.path)
        if text is None:
            skip += 1
            continue
        if sf.kind == "code":
            sloc += count_sloc(text, sf.language or "")
            evidences.extend(style_detector.detect(sf, text))
        if sf.kind == "markdown":
            bloat = docs_bloat.detect(sf, text)
            evidences.extend(bloat.evidences)
            infected.extend(bloat.infected)
        evidences.extend(phrase.detect(sf, text))
    rb = repo_bloat_evidence(files, sloc)
    if rb:
        evidences.append(rb)
    return aggregate(evidences, sloc=sloc, infected=infected,
                     skip_count=skip, root=str(root))
