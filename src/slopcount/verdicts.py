from __future__ import annotations

from dataclasses import dataclass

from slopcount.i18n import fmt_float


@dataclass(frozen=True)
class Verdict:
    code: str
    text: str  # английский msgid; переводится через _() при рендере


_SCALE: list[tuple[float, Verdict]] = [
    (10.0, Verdict("HUMAN",
        "Almost human. Suspiciously clean. Where are you hiding the slop?")),
    (25.0, Verdict("NEURO_CLOUD",
        "A light neuro-haze: the slop has arrived, but so far it does the dishes")),
    (50.0, Verdict("ESTABLISHED_SLOP",
        "The slop has settled in for good. More documentation than meaning")),
    (75.0, Verdict("AGENT_SELF_SERVICE",
        "Repository on LLM self-service. Humans visit on weekends")),
    (float("inf"), Verdict("AGENT_OCCUPATION",
        "Agent occupation. Resistance is futile")),
]
_RECURSION = Verdict("RECURSION", "You ran slopcount inside slop. Recursion")


def verdict_for(slop_ratio_pct: float) -> Verdict:
    if slop_ratio_pct > 100.0:
        return _RECURSION
    for bound, v in _SCALE:
        if slop_ratio_pct < bound:
            return v
    return _SCALE[-1][1]


def progress_bar(pct: float, width: int = 20) -> str:
    filled = 0 if pct != pct or pct == float("inf") else round(pct / 100 * width)
    filled = max(0, min(width, filled))
    return "[" + "█" * filled + "░" * (width - filled) + f"] {fmt_float(pct, 1)}%"
