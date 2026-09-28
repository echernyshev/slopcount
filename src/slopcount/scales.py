from __future__ import annotations

from dataclasses import dataclass

from slopcount.i18n import fmt_float


@dataclass(frozen=True)
class Grade:
    code: str
    text: str  # английский msgid; переводится через _() при рендере


# doc: якоря калибровки 2026-09-26 (спека 2026-09-26-md-sloc-ratio-design.md):
# HUMAN < 0.05 — классические эталоны (django 0.0005, flask 0.015);
# NEURO_CLOUD < 0.35 — потолок человеческого README (requests 0.34);
# RECURSION >= 1.0 — недетерминированного текста не меньше, чем кода
# (шутка самоскана, живёт вне списка границ).
_DOC: list[tuple[float, Grade]] = [
    (0.05, Grade("HUMAN", "Almost human. Suspiciously clean. Where are you hiding the slop?")),
    (
        0.35,
        Grade(
            "NEURO_CLOUD", "A light neuro-haze: the slop has arrived, but so far it does the dishes"
        ),
    ),
    (
        0.50,
        Grade(
            "ESTABLISHED_SLOP", "The slop has settled in for good. More documentation than meaning"
        ),
    ),
    (0.75, Grade("AGENT_SELF_SERVICE", "Repository on LLM self-service. Humans visit on weekends")),
    (1.00, Grade("AGENT_OCCUPATION", "Agent occupation. Resistance is futile")),
]
_RECURSION = Grade("RECURSION", "You ran slopcount inside slop. Recursion")

# comment: калибровка 2026-09-27 (спека 2026-09-27-comprehension-redesign-design.md
# §7.1/§14). Якоря: django 0.151 / redis 0.238 → DOCUMENTED; requests 0.320 /
# naumen-smp-mcp 0.331 / sqlite 0.343 / flask 0.415 → CHATTY; фикстура
# slop_project 1.5 → COMMENT_DRIVEN. Классы human/slop по comment/code не
# разделяются (naumen внутри гуманного кластера 0.32–0.41) — метрика
# информационная; единственный разрыв 0.41 → 1.5 черновым границам не
# противоречит, поэтому они оставлены.
_COMMENT: list[tuple[float, Grade]] = [
    (0.05, Grade("ASCETIC", "Not a single comment. The code speaks for itself, apparently")),
    (0.30, Grade("DOCUMENTED", "Healthy commentary. Docs and code in balance")),
    (0.60, Grade("CHATTY", "The code is chatty: comments grow thick")),
    (1.00, Grade("LECTURE_NOTES", "Lecture notes with occasional code samples")),
    (
        float("inf"),
        Grade("COMMENT_DRIVEN", "Comment-driven development. The code is an attachment"),
    ),
]
# slop: калибровка 2026-09-27 (спека 2026-09-27-comprehension-redesign-design.md
# §7.1/§14). Якоря: human-репо redis 0.0002 / sqlite 0.0005 / django 0.0015 /
# requests 0.0021 / flask 0.0025 → CLEAN; naumen-smp-mcp 0.0071 → TRACE;
# фикстура slop_project 2.0 → INFESTED. Единственный измеренный разрыв между
# классами 0.0025→0.0071 — граница CLEAN/TRACE в его середине (0.005, было
# 0.02: слоп-эталон naumen не должен получать «Detectors found nothing»).
# Точки между 0.0071 и 2.0 не измерялись — 0.10/0.30/1.00 остались круглыми.
_SLOP: list[tuple[float, Grade]] = [
    (0.005, Grade("CLEAN", "Slop at human noise level. Either clean or sneaky")),
    (0.10, Grade("TRACE", "Traces of slop. Nothing a mop cannot handle")),
    (0.30, Grade("NOTICEABLE", "Noticeable slop. The mop is wearing out")),
    (1.00, Grade("HEAVY", "Heavy slop contamination")),
    (float("inf"), Grade("INFESTED", "Full slop infestation. Call the exterminators")),
]

SCALES: dict[str, list[tuple[float, Grade]]] = {"doc": _DOC, "comment": _COMMENT, "slop": _SLOP}


def grade(metric: str, ratio: float) -> Grade:
    """Категория метрики по шкале; doc >= 1.0 — RECURSION (шутка самоскана)."""
    if metric == "doc" and ratio >= 1.0:
        return _RECURSION
    for bound, g in SCALES[metric]:
        if ratio < bound:
            return g
    return SCALES[metric][-1][1]


def progress_bar(pct: float, width: int = 20) -> str:
    filled = 0 if pct != pct or pct == float("inf") else round(pct / 100 * width)
    filled = max(0, min(width, filled))
    return "[" + "█" * filled + "░" * (width - filled) + f"] {fmt_float(pct, 1)}%"
