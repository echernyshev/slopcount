from __future__ import annotations

import math
from dataclasses import dataclass

from slopcount.app import Options

WPM = 238  # Brysbaert 2019
REREAD = 2.3  # коэффициент перечитывания от недоверия (шутка, помечена)
COG_MINUTES = 0.5  # 1 балл Cognitive Complexity ≈ полминуты
TOKENS_PER_WORD = 1.3
THERAPY_PRICE = 150.0


@dataclass(frozen=True)
class SlocomoResult:
    slop: int
    reading_hours: float
    person_months: float
    person_years: float
    schedule_months: float
    therapists: float
    cost: float
    context_windows_200k: float
    context_windows_1m: float
    gpu_hours: float
    coffee_cups: int
    coffee_cost: float
    therapy_sessions: int
    therapy_cost: float
    approximate: bool = True  # cognitive approximation mode


def compute(
    *,
    slop: int,
    prose_words: int,
    cognitive_points: int,
    halstead_secs: float,
    opts: Options,
    approximate: bool = True,
) -> SlocomoResult:
    reading = (
        prose_words / WPM / 60 * REREAD + cognitive_points * COG_MINUTES / 60 + halstead_secs / 3600
    )
    kslop = slop / 1000
    pm = 2.4 * kslop**1.05
    months = 2.5 * pm**0.38
    tokens = prose_words * TOKENS_PER_WORD
    coffee = math.ceil(reading / 4)
    sessions = 0 if opts.no_therapy else max(1, math.ceil(pm * 2))
    return SlocomoResult(
        slop=slop,
        reading_hours=reading,
        person_months=pm,
        person_years=pm / 12,
        schedule_months=months,
        therapists=(pm / months) if months else 0.0,
        cost=pm * opts.personcost * opts.overhead,
        context_windows_200k=tokens / 200_000,
        context_windows_1m=tokens / 1_000_000,
        gpu_hours=tokens / 100 / 3600,
        coffee_cups=coffee,
        coffee_cost=coffee * opts.coffee_price,
        therapy_sessions=sessions,
        therapy_cost=sessions * THERAPY_PRICE,
        approximate=approximate,
    )
