from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

from slopcount.metrics.costs import SlocomoBuckets, split_slocomo

if TYPE_CHECKING:  # цикл: app → slocomo → app; типы только для аннотаций
    from slopcount.app import Options
    from slopcount.scc import Locomo

WPM = 238.0
REREAD = 2.3
COMMENT_WORDS_PER_LINE = 6.0
SLOC_PER_HOUR = 200.0
COG_MINUTES = 0.5
HOURS_PER_PERSON_MONTH = 152.0  # стандарт COCOMO II (19 дней × 8 ч)
# ВНИМАНИЕ: metrics/costs.py::split_slocomo зеркалит литерал 152 — менять только в обоих местах.
TEAM_SIZES = (1, 2, 3, 5, 8, 13, 21)  # Фибоначчи: шкала команды (спека §5.2)
THERAPY_PRICE = 150.0


@dataclass(frozen=True)
class ComprehensionStats:
    """SLOCOMO на новой концепции: стоимость понимания ПРОЕКТА (спека §5).
    Все величины — в расчёте на одного человека (per person)."""

    reading_hours: float
    reading_components: dict[str, float]  # docs/code/comments/cognitive, часы
    person_months: float
    person_years: float
    schedule_months: float
    therapists: float
    cost: float  # НА ОДНОГО человека
    cost_breakdown: SlocomoBuckets  # docs/source_code{total,code,comments}/data → $
    team_costs: list[tuple[int, float, float]]  # (человек, person-months, $)
    comprehension_tokens: float | None  # LOCOMO in+out; None → рендер «—»
    context_windows_200k: float | None
    context_windows_1m: float | None
    gpu_hours: float | None
    coffee_cups: int
    coffee_cost: float
    therapy_sessions: int | None  # None = ∞ (slop_ratio=inf); 0 при --no-therapy
    therapy_cost: float


def compute(
    *,
    md_words: int,
    comment_lines: int,
    sloc: int,
    cognitive_total: int,
    slop_ratio: float,
    locomo: Locomo | None,
    opts: Options,
) -> ComprehensionStats:
    """reading_hours отражает реальный объём проекта (спека §5.1):
    доки (238 wpm × 2.3 перечитывания) + комментарии (строки × 6 слов)
    + код (200 SLOC/ч) + когнитива (0.5 мин/балл, весь проект)."""
    components = {
        "docs": md_words / WPM / 60 * REREAD,
        "comments": comment_lines * COMMENT_WORDS_PER_LINE / WPM / 60,
        "code": sloc / SLOC_PER_HOUR,
        "cognitive": cognitive_total * COG_MINUTES / 60,
    }
    reading = sum(components.values())
    person_months = reading / HOURS_PER_PERSON_MONTH * (1 + slop_ratio)
    schedule = 2.5 * person_months**0.38
    if math.isinf(person_months):
        therapists = float("inf")
    else:
        therapists = person_months / schedule if schedule else 0.0
    cost = person_months * opts.personcost * opts.overhead
    tokens = None
    if locomo is not None:
        tokens = locomo.input_tokens + locomo.output_tokens
    coffee = math.ceil(reading / 4) if reading > 0 else 0
    if opts.no_therapy:
        sessions: int | None = 0
    elif math.isinf(person_months):
        sessions = None
    else:
        sessions = max(1, math.ceil(person_months * 2))
    return ComprehensionStats(
        reading_hours=reading,
        reading_components=components,
        person_months=person_months,
        person_years=person_months / 12,
        schedule_months=schedule,
        therapists=therapists,
        cost=cost,
        cost_breakdown=split_slocomo(
            components, slop_ratio=slop_ratio, personcost=opts.personcost, overhead=opts.overhead
        ),
        team_costs=[(n, person_months * n, cost * n) for n in TEAM_SIZES],
        comprehension_tokens=tokens,
        context_windows_200k=tokens / 200_000 if tokens is not None else None,
        context_windows_1m=tokens / 1_000_000 if tokens is not None else None,
        gpu_hours=tokens / 100 / 3600 if tokens is not None else None,
        coffee_cups=coffee,
        coffee_cost=coffee * opts.coffee_price,
        therapy_sessions=sessions,
        # sessions=None (∞) → cost 0.0: строка скрывается рендером
        # (if therapy_sessions) — осознанный выбор
        therapy_cost=sessions * THERAPY_PRICE if sessions else 0.0,
    )
