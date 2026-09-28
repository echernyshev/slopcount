from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # цикл: evidence → metrics.slocomo → app → evidence; scc — типы полей Report
    from slopcount.metrics.costs import CocomoSplit, LocomoBuckets
    from slopcount.metrics.slocomo import ComprehensionStats
    from slopcount.scc import Cocomo as SccCocomo
    from slopcount.scc import Locomo as SccLocomo


class Category(StrEnum):
    PROSE = "prose"
    DOCS = "docs"
    STYLE = "style"
    AGENCY = "agency"
    HISTORY = "history"


@dataclass(frozen=True)
class Evidence:
    file: str  # путь относительно корня скана или "git:<sha8>" для коммитов
    line: int  # 1-based; 0 = файл-уровень
    category: Category
    weight: int
    description: str


@dataclass(frozen=True)
class ScannedFile:
    # Родился в scanner.py (модуль удалён при делегировании scc); живёт здесь —
    # ядро модели данных, детекторы не зависят от источника манифеста.

    path: str  # posix-путь относительно корня
    language: str | None
    kind: str  # "code" | "markdown" | "prose" | "data"
    size: int


def read_text(path: Path) -> str | None:
    """None для бинарных/нечитаемых файлов (счётчик skip).

    Переехал из удалённого scanner.py; семантика не менялась: бинарность —
    NUL-байт в первых 1024 байтах, декодирование строгий UTF-8."""
    try:
        raw = path.read_bytes()
        if b"\0" in raw[:1024]:
            return None
        return raw.decode("utf-8")
    except (OSError, UnicodeDecodeError):
        return None


@dataclass
class CategoryTotals:
    files: int = 0
    slop_lines: int = 0
    weight: int = 0

    @property
    def cognitivity(self) -> str:
        if self.slop_lines == 0:
            return "low"
        density = self.weight / self.slop_lines
        if density >= 3:
            return "high"
        if density >= 1.5:
            return "medium"
        return "low"


@dataclass
class LanguageRow:
    language: str  # display-имя scc
    files: int
    sloc: int


@dataclass
class VolumeStats:
    """Секция 1 отчёта: объём проекта (спека 0.5.0 §3)."""

    sloc: int = 0  # Σ Code, kind=code
    comment_lines: int = 0  # Σ Comment, kind=code
    complexity: int = 0  # Σ Complexity, kind=code (факт; в формулах не участвует)
    cognitive_total: int = 0  # Σ Cognitive, kind=code — вход reading_hours
    files_total: int = 0  # весь манифест scc (включая data)
    languages: list[LanguageRow] = field(default_factory=list)  # только kind=code
    md_files: int = 0  # .md/.markdown (kind=markdown + фильтр расширения)
    md_lines: int = 0
    md_words: int = 0  # честный Σ слов kind=markdown+prose (для чтения)
    md_sloc_ratio: float = 0.0  # доля; inf при sloc=0 и md>0
    comment_sloc_ratio: float = 0.0


@dataclass
class SlopStats:
    """Секция 3 отчёта: детектированный слоп (спека 0.5.0 §3)."""

    total: int = 0  # SLOP: улики (prose/docs/style/history) + заражённые md
    ratio: float = 0.0  # total/sloc; inf при sloc=0 и total>0
    infected_md_lines: int = 0
    categories: dict[Category, CategoryTotals] = field(
        default_factory=lambda: {c: CategoryTotals() for c in Category}
    )
    top_files: list[tuple[str, int]] = field(default_factory=list)  # топ-5 по слоп-строкам
    agency: list[Evidence] = field(default_factory=list)  # AGENCY не входит в SLOP
    details: list[Evidence] = field(default_factory=list)


def safe_ratio(numerator: float, denominator: float) -> float:
    """Доля; denominator=0 → inf при числителе > 0, иначе 0.0."""
    if denominator == 0:
        return float("inf") if numerator > 0 else 0.0
    return numerator / denominator


def aggregate_slop(
    evidences: list[Evidence], *, sloc: int, infected: list[tuple[str, int]] = ()
) -> SlopStats:
    lines_per_cat: dict[Category, set[tuple[str, int]]] = defaultdict(set)
    files_per_cat: dict[Category, set[str]] = defaultdict(set)
    weight_per_cat: dict[Category, int] = defaultdict(int)
    for e in evidences:
        lines_per_cat[e.category].add((e.file, e.line))
        files_per_cat[e.category].add(e.file)
        weight_per_cat[e.category] += e.weight

    stats = SlopStats(
        agency=[e for e in evidences if e.category is Category.AGENCY],
        details=list(evidences),
    )
    stats.infected_md_lines = sum(round(n * 0.8) for _, n in infected)
    for cat in Category:
        totals = stats.categories[cat]
        totals.files = len(files_per_cat[cat])
        totals.slop_lines = len(lines_per_cat[cat])
        totals.weight = weight_per_cat[cat]

    # SLOP: уникальные строки с уликами (agency не входит) + заражённые md-строки
    slop_lines: set[tuple[str, int]] = set()
    for cat in (Category.PROSE, Category.DOCS, Category.STYLE, Category.HISTORY):
        slop_lines |= lines_per_cat[cat]
    per_file: dict[str, int] = defaultdict(int)
    for file, _line in slop_lines:
        per_file[file] += 1
    for file, n in infected:
        per_file[file] += round(n * 0.8)
    stats.top_files = sorted(per_file.items(), key=lambda kv: (-kv[1], kv[0]))[:5]
    stats.total = len(slop_lines) + stats.infected_md_lines
    stats.ratio = safe_ratio(stats.total, sloc)
    return stats


@dataclass
class Report:
    root: str
    skip_count: int = 0
    history_commits: int | None = None
    volume: VolumeStats = field(default_factory=VolumeStats)
    slop: SlopStats = field(default_factory=SlopStats)
    scc_version: str = ""
    cocomo: SccCocomo | None = None
    locomo: SccLocomo | None = None
    cocomo_breakdown: CocomoSplit | None = None
    locomo_breakdown: LocomoBuckets | None = None
    slocomo: ComprehensionStats | None = None  # модуль metrics.slocomo
