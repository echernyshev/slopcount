from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

from slopcount.detectors.code_style import CodeStyleDetector
from slopcount.detectors.docs_bloat import DocsBloatDetector, repo_bloat_evidence
from slopcount.detectors.env_markers import EnvMarkerDetector
from slopcount.detectors.phrase import PhraseDetector
from slopcount.evidence import Evidence, Report, aggregate
from slopcount.i18n import _
from slopcount.metrics.cognitive import (approx_cognitive_complexity,
                                         cognitive_complexity_tspython,
                                         exact_available, halstead_seconds)
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
    if len(opts.paths) > 1:
        print(_("slopcount: multiple paths given, scanning only the first: {path}")
              .format(path=opts.paths[0]), file=sys.stderr)
    phrase = PhraseDetector(load_rules(opts.rules))
    docs_bloat = DocsBloatDetector()
    style_detector = CodeStyleDetector()
    pplx = None
    if opts.perplexity:
        from slopcount.detectors.perplexity import PerplexityDetector, available
        if not available():
            raise RuntimeError(
                _("slopcount: --perplexity requires extras; "
                  "pipx install 'slopcount[perplexity]' and "
                  "python -m slopcount.download_model"))
        pplx = PerplexityDetector()
    evidences: list[Evidence] = []
    infected: list[tuple[str, int]] = []
    sloc = 0
    skip = 0
    prose_words = 0
    cog_points = 0
    hal_secs = 0.0
    used_approx = False     # был ли хоть один файл посчитан приближённо
    n = 0
    progressed = False
    is_stderr_tty = sys.stderr.isatty()
    total = sum(1 for f in files if f.kind in ("code", "markdown", "prose"))
    for sf in files:
        if sf.kind not in ("code", "markdown", "prose"):
            continue
        text = read_text(root / sf.path)
        if text is None:
            skip += 1
            continue
        n += 1
        if is_stderr_tty and n % 200 == 0:
            print(f"\rscanned {n}/{total} files...", end="", file=sys.stderr)
            progressed = True
        file_evidences: list[Evidence] = []
        if sf.kind == "code":
            sloc += count_sloc(text, sf.language or "")
            style_evs = style_detector.detect(sf, text)
            evidences.extend(style_evs)
            file_evidences.extend(style_evs)
            if style_evs:   # SLOCOMO: вес слоп-кода
                # Точный режим: python + [treesitter] extras; остальное —
                # приближение. Смешанный режим считается приближённым.
                if sf.language == "python" and exact_available():
                    cog_points += cognitive_complexity_tspython(text)
                else:
                    cog_points += approx_cognitive_complexity(
                        text, sf.language or "")
                    used_approx = True
                hal_secs += halstead_seconds(text)
        if sf.kind == "markdown":
            bloat = docs_bloat.detect(sf, text)
            evidences.extend(bloat.evidences)
            file_evidences.extend(bloat.evidences)
            infected.extend(bloat.infected)
            if bloat.infected:
                prose_words += int(len(text.split()) * 0.8)
        phrase_evs = phrase.detect(sf, text)
        evidences.extend(phrase_evs)
        file_evidences.extend(phrase_evs)
        if pplx is not None and sf.kind in ("markdown", "prose"):
            evidences.extend(pplx.detect(sf, text))
        prose_words += flagged_words(text, file_evidences)
    if progressed:
        print(file=sys.stderr)          # завершаем строку прогресса
    rb = repo_bloat_evidence(files, sloc)
    if rb:
        evidences.append(rb)
    evidences.extend(EnvMarkerDetector().detect(root, files, read_text))
    history_commits: int | None = None
    if opts.history:
        from slopcount.detectors.git_history import GitUnavailable, detect as git_detect
        try:
            hist_evs, commits = git_detect(root, opts.history)
            evidences.extend(hist_evs)
            history_commits = commits
        except GitUnavailable:
            print(_("slopcount: git history unavailable; skipping archaeology"),
                  file=sys.stderr)
    report = aggregate(evidences, sloc=sloc, infected=infected,
                       skip_count=skip, root=str(root),
                       history_commits=history_commits)
    # Ленивый импорт: модуль slocomo импортирует Options из этого модуля
    from slopcount.metrics.slocomo import compute as slocomo_compute
    report.slocomo = slocomo_compute(
        slop=report.slop, prose_words=prose_words, cognitive_points=cog_points,
        halstead_secs=hal_secs, opts=opts, approximate=used_approx)
    return report
