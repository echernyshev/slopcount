from __future__ import annotations

import sys
from dataclasses import dataclass, field

from slopcount.i18n import _
from slopcount.scc import Cocomo, Locomo


@dataclass(frozen=True)
class CocomoBucket:
    lines: int
    person_months: float
    cost: float


# Единая структура корзин (спека §6): docs / source_code{total, code,
# comments} / data. Заполнение честное по возможностям метрики:
# comments=None у COCOMO/LOCOMO (scc их не учитывает), data=None у
# SLOCOMO (data-файлы не читаем).
CocomoBuckets = dict[str, CocomoBucket | dict[str, CocomoBucket | None]]


@dataclass(frozen=True)
class CocomoSplit:
    total_person_months: float
    buckets: CocomoBuckets = field(default_factory=dict)


@dataclass(frozen=True)
class LocomoBucket:
    lines: int
    hours: float
    cost: float


LocomoBuckets = dict[str, LocomoBucket | dict[str, LocomoBucket | None]]

SlocomoBuckets = dict[str, float | dict[str, float] | None]


def split_cocomo(
    cocomo: Cocomo,
    *,
    docs_lines: int,
    code_lines: int,
    data_lines: int,
    personcost: float,
    overhead: float,
) -> CocomoSplit:
    """Независимые оценки по корзинам: PM = 2.4·(K)^1.05 (репликация
    базового COCOMO organic из scc — проверено до доллара, спека §6.1).
    Неаддитивность принята; сверка total с scc — drift-guard.

    Единая структура корзин: вход scc — только Code-строки, поэтому
    source_code.total = source_code.code, comments = None."""
    total_lines = docs_lines + code_lines + data_lines
    pm_total = 2.4 * (total_lines / 1000) ** 1.05
    pm_implied = cocomo.cost / (personcost * overhead) if personcost and overhead else 0.0
    if pm_implied and abs(pm_total - pm_implied) / pm_implied > 0.01:
        print(
            _(
                "slopcount: scc COCOMO model drift detected: replica %.1f vs implied "
                "%.1f person-months; bucket split may differ"
            )
            % (pm_total, pm_implied),
            file=sys.stderr,
        )
    rate = personcost * overhead
    code_b = CocomoBucket(
        lines=code_lines,
        person_months=2.4 * (code_lines / 1000) ** 1.05,
        cost=2.4 * (code_lines / 1000) ** 1.05 * rate,
    )
    buckets = {
        "docs": CocomoBucket(
            lines=docs_lines,
            person_months=2.4 * (docs_lines / 1000) ** 1.05,
            cost=2.4 * (docs_lines / 1000) ** 1.05 * rate,
        ),
        # комментарии scc в COCOMO не считает → total = code, comments = None
        "source_code": {"total": code_b, "code": code_b, "comments": None},
        "data": CocomoBucket(
            lines=data_lines,
            person_months=2.4 * (data_lines / 1000) ** 1.05,
            cost=2.4 * (data_lines / 1000) ** 1.05 * rate,
        ),
    }
    return CocomoSplit(total_person_months=pm_total, buckets=buckets)


def attribute_locomo(
    locomo: Locomo, *, docs_lines: int, code_lines: int, data_lines: int
) -> LocomoBuckets:
    """Атрибуция фактических цифр LOCOMO по долям Code-строк корзин —
    аддитивно ровно к total; модель scc не реплицируем (спека §6.2).

    Единая структура корзин: вход scc — только Code-строки, поэтому
    source_code.total = source_code.code, comments = None."""
    total_lines = docs_lines + code_lines + data_lines
    total_hours = locomo.generation_seconds / 3600 + locomo.review_hours

    def _bucket(lines: int) -> LocomoBucket:
        share = lines / total_lines if total_lines else 0.0
        return LocomoBucket(lines=lines, hours=total_hours * share, cost=locomo.cost * share)

    code_b = _bucket(code_lines)
    # комментарии scc в LOCOMO не считает → total = code, comments = None
    return {
        "docs": _bucket(docs_lines),
        "source_code": {"total": code_b, "code": code_b, "comments": None},
        "data": _bucket(data_lines),
    }


def split_slocomo(
    reading_components: dict[str, float], *, slop_ratio: float, personcost: float, overhead: float
) -> SlocomoBuckets:
    """Точная аддитивная разбивка SLOCOMO-стоимости (линейная модель,
    спека §6.3) в единой структуре корзин: source_code = код +
    когнитивная обработка + комментарии (все подстроки живые),
    data = None — data-файлы не читаем; 152 = HOURS_PER_PERSON_MONTH
    (COCOMO II).

    Нулевые компоненты остаются нулями и при slop_ratio=inf (0·inf=nan
    нарушил бы аддитивность: сумма корзин обязана равняться total)."""
    factor = (1 + slop_ratio) * personcost * overhead / 152

    def _bucket(comp: float) -> float:
        return comp * factor if comp else 0.0

    code = _bucket(reading_components["code"] + reading_components["cognitive"])
    comments = _bucket(reading_components["comments"])
    return {
        "docs": _bucket(reading_components["docs"]),
        "source_code": {"total": code + comments, "code": code, "comments": comments},
        "data": None,  # data-файлы не читаем (спека §6)
    }
