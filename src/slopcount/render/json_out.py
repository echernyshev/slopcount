from __future__ import annotations

import json
import math

from slopcount.evidence import Category, Report
from slopcount.verdicts import verdict_for


def render_json(report: Report) -> str:
    sc = None
    if report.slocomo is not None:
        sc = {
            "reading_hours": round(report.slocomo.reading_hours, 3),
            "person_months": round(report.slocomo.person_months, 3),
            "schedule_months": round(report.slocomo.schedule_months, 3),
            "therapists": round(report.slocomo.therapists, 3),
            "cost": round(report.slocomo.cost, 2),
            "context_windows_200k": round(report.slocomo.context_windows_200k, 4),
            "context_windows_1m": round(report.slocomo.context_windows_1m, 4),
            "gpu_hours": round(report.slocomo.gpu_hours, 4),
            "coffee_cups": report.slocomo.coffee_cups,
            "approximate": report.slocomo.approximate,
        }
    v = verdict_for(report.slop_ratio)
    ratio = round(report.slop_ratio, 2) if not math.isinf(report.slop_ratio) else None
    return json.dumps(
        {
            "sloc": report.sloc,
            "slop": report.slop,
            "slop_ratio": ratio,
            "skipped_files": report.skip_count,
            "infected_md_lines": report.infected_md_lines,
            "history_commits": report.history_commits,
            "categories": {
                c.value: {
                    "files": report.categories[c].files,
                    "slop_lines": report.categories[c].slop_lines,
                    "weight": report.categories[c].weight,
                    "cognitivity": report.categories[c].cognitivity,
                }
                for c in Category
            },
            "evidence_count": len(report.details),
            "slocomo": sc,
            "verdict": {"code": v.code, "ratio": ratio},
        },
        indent=2,
    )
