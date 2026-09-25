from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # цикл: evidence → metrics.slocomo → app → evidence
    from slopcount.metrics.slocomo import SlocomoResult


class Category(StrEnum):
    PROSE = "prose"
    DOCS = "docs"
    STYLE = "style"
    AGENCY = "agency"
    HISTORY = "history"


@dataclass(frozen=True)
class Evidence:
    file: str          # путь относительно корня скана или "git:<sha8>" для коммитов
    line: int          # 1-based; 0 = файл-уровень
    category: Category
    weight: int
    description: str


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
class Report:
    root: str
    sloc: int = 0
    skip_count: int = 0
    categories: dict[Category, CategoryTotals] = field(
        default_factory=lambda: {c: CategoryTotals() for c in Category}
    )
    slop: int = 0
    slop_ratio: float = 0.0
    infected_md_lines: int = 0
    history_commits: int | None = None
    details: list[Evidence] = field(default_factory=list)
    agency: list[Evidence] = field(default_factory=list)
    slocomo: SlocomoResult | None = None  # модуль metrics.slocomo


def aggregate(
    evidences: list[Evidence],
    *,
    sloc: int,
    infected: list[tuple[str, int]] = (),
    history_commits: int | None = None,
    skip_count: int = 0,
    root: str = ".",
) -> Report:
    lines_per_cat: dict[Category, set[tuple[str, int]]] = defaultdict(set)
    files_per_cat: dict[Category, set[str]] = defaultdict(set)
    weight_per_cat: dict[Category, int] = defaultdict(int)
    for e in evidences:
        lines_per_cat[e.category].add((e.file, e.line))
        files_per_cat[e.category].add(e.file)
        weight_per_cat[e.category] += e.weight

    report = Report(root=root, sloc=sloc, history_commits=history_commits,
                    skip_count=skip_count, details=list(evidences),
                    agency=[e for e in evidences if e.category is Category.AGENCY])
    report.infected_md_lines = sum(round(n * 0.8) for _, n in infected)
    for cat in Category:
        totals = report.categories[cat]
        totals.files = len(files_per_cat[cat])
        totals.slop_lines = len(lines_per_cat[cat])
        totals.weight = weight_per_cat[cat]

    # SLOP: уникальные строки с уликами (agency не входит) + заражённые md-строки
    slop_lines = set()
    for cat in (Category.PROSE, Category.DOCS, Category.STYLE, Category.HISTORY):
        slop_lines |= lines_per_cat[cat]
    report.slop = len(slop_lines) + report.infected_md_lines
    if sloc == 0:
        report.slop_ratio = float("inf") if report.slop > 0 else 0.0
    else:
        report.slop_ratio = report.slop / sloc * 100
    return report
