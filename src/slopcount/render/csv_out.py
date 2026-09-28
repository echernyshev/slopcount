from __future__ import annotations

import csv
import io
from pathlib import Path

from slopcount.evidence import Report
from slopcount.render.text import _snippet


def render_csv(report: Report) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["file", "line", "category", "weight", "description", "source"])
    root = Path(report.root)
    for e in sorted(report.slop.details, key=lambda e: -e.weight):
        w.writerow(
            [
                e.file,
                e.line,
                e.category.value,
                e.weight,
                e.description,
                _snippet(root, e.file, e.line),
            ]
        )
    return buf.getvalue()
