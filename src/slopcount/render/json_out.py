from __future__ import annotations

import json
import math

from slopcount.evidence import Report
from slopcount.metrics.costs import (
    CocomoBucket,
    CocomoBuckets,
    LocomoBucket,
    LocomoBuckets,
    SlocomoBuckets,
)
from slopcount.scales import grade


def _rf(x: float | None, nd: int) -> float | None:
    """Округление; inf/nan → None (JSON не любит Infinity)."""
    if x is None or not math.isfinite(x):
        return None
    return round(x, nd)


def _cocomo_bucket_json(b: CocomoBucket) -> dict[str, int | float | None]:
    return {"lines": b.lines, "person_months": _rf(b.person_months, 2), "cost": _rf(b.cost, 2)}


def _cocomo_breakdown_json(b: CocomoBuckets) -> dict[str, object]:
    """Единая форма корзин → JSON: comments = null (scc их не учитывает)."""
    return {
        "docs": _cocomo_bucket_json(b["docs"]),
        "source_code": {
            name: None if x is None else _cocomo_bucket_json(x)
            for name, x in b["source_code"].items()
        },
        "data": _cocomo_bucket_json(b["data"]),
    }


def _locomo_bucket_json(b: LocomoBucket) -> dict[str, int | float | None]:
    return {"lines": b.lines, "hours": _rf(b.hours, 2), "cost": _rf(b.cost, 2)}


def _locomo_breakdown_json(b: LocomoBuckets) -> dict[str, object]:
    """Единая форма корзин → JSON: comments = null (scc их не учитывает)."""
    return {
        "docs": _locomo_bucket_json(b["docs"]),
        "source_code": {
            name: None if x is None else _locomo_bucket_json(x)
            for name, x in b["source_code"].items()
        },
        "data": _locomo_bucket_json(b["data"]),
    }


def _cost_breakdown_json(b: SlocomoBuckets) -> dict[str, float | dict[str, float | None] | None]:
    """SLOCOMO cost_breakdown в единой форме корзин: source_code с
    подстроками total/code/comments, data = null (не читаем)."""
    sc = b["source_code"]
    return {
        "docs": _rf(b["docs"], 2),
        "source_code": {name: _rf(x, 2) for name, x in sc.items()},
        "data": _rf(b["data"], 2),
    }


def render_json(report: Report) -> str:
    v = report.volume
    s = report.slop
    comp = None
    if report.slocomo is not None:
        r = report.slocomo
        comp = {
            "reading_hours": _rf(r.reading_hours, 3),
            "reading_components": {k: _rf(x, 3) for k, x in r.reading_components.items()},
            "person_months": _rf(r.person_months, 3),
            "person_years": _rf(r.person_years, 4),
            "schedule_months": _rf(r.schedule_months, 3),
            "therapists": _rf(r.therapists, 3),
            "cost_per_person": _rf(r.cost, 2),
            "cost_breakdown": _cost_breakdown_json(r.cost_breakdown),
            "team_costs": [
                {"people": n, "person_months": _rf(pm, 3), "cost": _rf(c, 2)}
                for n, pm, c in r.team_costs
            ],
            "comprehension_tokens": _rf(r.comprehension_tokens, 1),
            "context_windows_200k": _rf(r.context_windows_200k, 4),
            "context_windows_1m": _rf(r.context_windows_1m, 4),
            "gpu_hours": _rf(r.gpu_hours, 4),
            "coffee_cups": r.coffee_cups,
            "coffee_cost": _rf(r.coffee_cost, 2),
            "therapy_sessions": r.therapy_sessions,
            "therapy_cost": _rf(r.therapy_cost, 2),
        }
    cocomo = locomo = None
    if report.cocomo is not None and report.cocomo_breakdown is not None:
        cb = report.cocomo_breakdown
        cocomo = {
            "cost": _rf(report.cocomo.cost, 2),
            "person_months": _rf(cb.total_person_months, 2),
            "schedule_months": _rf(report.cocomo.schedule_months, 2),
            "people": _rf(report.cocomo.people, 3),
            "breakdown": _cocomo_breakdown_json(cb.buckets),
        }
    if report.locomo is not None:
        lb = report.locomo_breakdown
        locomo = {
            "cost": _rf(report.locomo.cost, 2),
            "input_tokens": _rf(report.locomo.input_tokens, 1),
            "output_tokens": _rf(report.locomo.output_tokens, 1),
            "generation_seconds": _rf(report.locomo.generation_seconds, 1),
            "review_hours": _rf(report.locomo.review_hours, 2),
            "cycles": _rf(report.locomo.cycles, 2),
            "preset": report.locomo.preset,
            # синтетический Report без разбивки → пустой breakdown
            "breakdown": _locomo_breakdown_json(lb) if lb else {},
        }
    return json.dumps(
        {
            "scan": {
                "tool": f"scc {report.scc_version}",
                "files": v.files_total,
                "skipped": report.skip_count,
                "history_commits": report.history_commits,
            },
            "volume": {
                "sloc": v.sloc,
                "comment_lines": v.comment_lines,
                "complexity": v.complexity,
                "cognitive": v.cognitive_total,
                "md_files": v.md_files,
                "md_lines": v.md_lines,
                "md_words": v.md_words,
                "md_sloc_ratio": _rf(v.md_sloc_ratio, 4),
                "comment_sloc_ratio": _rf(v.comment_sloc_ratio, 4),
                "languages": [
                    {"language": row.language, "files": row.files, "sloc": row.sloc}
                    for row in v.languages
                ],
                "grades": {
                    "doc": grade("doc", v.md_sloc_ratio).code,
                    "comment": grade("comment", v.comment_sloc_ratio).code,
                    "slop": grade("slop", s.ratio).code,
                },
            },
            "slop": {
                "total": s.total,
                "ratio": _rf(s.ratio, 4),
                "infected_md_lines": s.infected_md_lines,
                "categories": {
                    c.value: {
                        "files": s.categories[c].files,
                        "slop_lines": s.categories[c].slop_lines,
                        "weight": s.categories[c].weight,
                        "cognitivity": s.categories[c].cognitivity,
                    }
                    for c in s.categories
                },
                "top_files": [{"file": p, "lines": n} for p, n in s.top_files],
            },
            "comprehension": comp,
            "costs": {"cocomo": cocomo, "locomo": locomo},
            "evidence_count": len(s.details),
        },
        indent=2,
    )
