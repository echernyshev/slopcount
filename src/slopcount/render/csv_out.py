from __future__ import annotations

import csv
import io

from slopcount.evidence import Report


def render_csv(report: Report) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["file", "line", "category", "weight", "description"])
    for e in sorted(report.details, key=lambda e: -e.weight):
        w.writerow([e.file, e.line, e.category.value, e.weight, e.description])
    return buf.getvalue()
