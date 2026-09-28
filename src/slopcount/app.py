from __future__ import annotations

import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from slopcount import scc
from slopcount.detectors.code_style import CodeStyleDetector
from slopcount.detectors.docs_bloat import DocsBloatDetector, repo_bloat_evidence
from slopcount.detectors.env_markers import EnvMarkerDetector
from slopcount.detectors.phrase import PhraseDetector
from slopcount.evidence import (
    Evidence,
    LanguageRow,
    Report,
    ScannedFile,
    VolumeStats,
    aggregate_slop,
    read_text,
    safe_ratio,
)
from slopcount.i18n import _
from slopcount.metrics.costs import attribute_locomo, split_cocomo
from slopcount.metrics.slocomo import compute as slocomo_compute
from slopcount.rules import load_languages, load_rules


@dataclass
class Options:
    paths: list[str] = field(default_factory=lambda: ["."])
    evidence: bool = False
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
    wide: bool = False
    scc_path: str | None = None


def run(opts: Options) -> Report:
    root = Path(opts.paths[0])
    if len(opts.paths) > 1:
        print(
            _("slopcount: multiple paths given, scanning only the first: %s") % opts.paths[0],
            file=sys.stderr,
        )
    langmap = load_languages(opts.rules)
    manifest = scc.collect(
        root, personcost=opts.personcost, overhead=opts.overhead, scc_path=opts.scc_path
    )
    # kind/language из каталога языков; неизвестный scc-язык → ("data", None)
    files: list[ScannedFile] = []
    for f in manifest.files:
        kind_lang = langmap.get(f.language_name, ("data", None))
        files.append(ScannedFile(f.path, kind_lang[1], kind_lang[0], f.size))

    # ── Фаза volume: объём проекта из манифеста (спека §4) ──────────────
    # SLOC/комментарии/когнитива — по манифесту целиком: нечитаемые (skip)
    # файлы входят в объём, как и в COCOMO/LOCOMO scc (спека §4);
    # детекторы такие файлы по-прежнему не видят.
    volume = VolumeStats(files_total=len(manifest.files))
    lang_files: Counter[str] = Counter()
    lang_sloc: Counter[str] = Counter()
    bucket_lines: Counter[str] = Counter()  # kind → Σ Code (корзины стоимостей)
    for f, sf in zip(manifest.files, files, strict=True):
        bucket_lines[sf.kind] += f.code
        if sf.kind != "code":
            continue
        volume.sloc += f.code
        volume.comment_lines += f.comment
        volume.complexity += f.complexity
        volume.cognitive_total += f.cognitive
        lang_files[f.language_name] += 1
        lang_sloc[f.language_name] += f.code
    volume.languages = [
        LanguageRow(lang, lang_files[lang], lang_sloc[lang])
        for lang in sorted(lang_sloc, key=lambda lg: (-lang_sloc[lg], lg))
    ]
    docs_bucket_lines = bucket_lines["markdown"] + bucket_lines["prose"]

    # ── Фаза detect: один проход по читаемым файлам ─────────────────────
    phrase = PhraseDetector(load_rules(opts.rules))
    docs_bloat = DocsBloatDetector()
    style_detector = CodeStyleDetector()
    pplx = None
    if opts.perplexity:
        from slopcount.detectors.perplexity import PerplexityDetector, available

        if not available():
            raise RuntimeError(
                _(
                    "slopcount: --perplexity requires extras; "
                    "pipx install 'slopcount[perplexity]' and "
                    "python -m slopcount.download_model"
                )
            )
        pplx = PerplexityDetector()
    by_path = {f.path: f for f in manifest.files}
    evidences: list[Evidence] = []
    infected: list[tuple[str, int]] = []
    md_files = 0
    md_lines = 0
    md_words = 0
    skip = 0
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
        if sf.kind == "code":
            evidences.extend(style_detector.detect(sf, text))
        else:  # markdown | prose — объём доков (спека §5.1)
            md_words += len(text.split())
            if sf.kind == "markdown":
                if sf.path.lower().endswith((".md", ".markdown")):
                    md_files += 1
                    md_lines += by_path[sf.path].lines
                bloat = docs_bloat.detect(sf, text)  # детекция — только markdown (спека §4)
                evidences.extend(bloat.evidences)
                infected.extend(bloat.infected)
        evidences.extend(phrase.detect(sf, text))
        if pplx is not None and sf.kind in ("markdown", "prose"):
            evidences.extend(pplx.detect(sf, text))
    if progressed:
        print(file=sys.stderr)  # завершаем строку прогресса
    rb = repo_bloat_evidence(files, volume.sloc)
    if rb:
        evidences.append(rb)
    evidences.extend(EnvMarkerDetector().detect(root, files, read_text))
    history_commits: int | None = None
    if opts.history:
        from slopcount.detectors.git_history import GitUnavailable
        from slopcount.detectors.git_history import detect as git_detect

        try:
            hist_evs, commits = git_detect(root, opts.history)
            evidences.extend(hist_evs)
            history_commits = commits
        except GitUnavailable:
            print(_("slopcount: git history unavailable; skipping archaeology"), file=sys.stderr)
    volume.md_files = md_files
    volume.md_lines = md_lines
    volume.md_words = md_words
    volume.md_sloc_ratio = safe_ratio(md_lines, volume.sloc)
    volume.comment_sloc_ratio = safe_ratio(volume.comment_lines, volume.sloc)

    # ── Фаза aggregate: SlopStats ───────────────────────────────────────
    slop = aggregate_slop(evidences, sloc=volume.sloc, infected=infected)

    # ── Фаза comprehension: SLOCOMO + разбивки стоимостей ───────────────
    # (slocomo_compute импортирован наверху: цикла больше нет — Options в
    # slocomo.py живёт только в TYPE_CHECKING)
    slocomo = slocomo_compute(
        md_words=md_words,
        comment_lines=volume.comment_lines,
        sloc=volume.sloc,
        cognitive_total=volume.cognitive_total,
        slop_ratio=slop.ratio,
        locomo=manifest.locomo,
        opts=opts,
    )
    report = Report(
        root=str(root),
        skip_count=skip,
        history_commits=history_commits,
        volume=volume,
        slop=slop,
        scc_version=manifest.scc_version,
        cocomo=manifest.cocomo,
        locomo=manifest.locomo,
        slocomo=slocomo,
    )
    if manifest.cocomo is not None:
        report.cocomo_breakdown = split_cocomo(
            manifest.cocomo,
            docs_lines=docs_bucket_lines,
            code_lines=bucket_lines["code"],
            data_lines=bucket_lines["data"],
            personcost=opts.personcost,
            overhead=opts.overhead,
        )
    if manifest.locomo is not None:
        report.locomo_breakdown = attribute_locomo(
            manifest.locomo,
            docs_lines=docs_bucket_lines,
            code_lines=bucket_lines["code"],
            data_lines=bucket_lines["data"],
        )
    return report
