from __future__ import annotations

from slopcount.evidence import Category, Report
from slopcount.i18n import _, fmt_float, fmt_int
from slopcount.verdicts import progress_bar, verdict_for

_ROW_LABELS = {
    Category.DOCS: "Markdown specs",
    Category.PROSE: "Prose (comments/docstrings)",
    Category.STYLE: "Code style",
    Category.HISTORY: "Git history",
    Category.AGENCY: "Environment markers",
}


def render_text(report: Report) -> str:
    out = []
    out.append(_("Totals grouped by slop origin (dominant slop source first):"))
    out.append("-" * 79)
    out.append(f"{_('Origin'):<28}{'files':>10}{'slop lines':>14}"
               f"{'slop %':>10}  {'cognitivity':<10}")
    out.append("-" * 79)
    ordered = sorted(
        [c for c in Category if c is not Category.AGENCY],
        key=lambda c: report.categories[c].slop_lines, reverse=True)
    for cat in ordered:
        t = report.categories[cat]
        name = _(_ROW_LABELS[cat])
        if cat is Category.HISTORY and report.history_commits:
            name = name + f" ({report.history_commits})"
        pct = (t.slop_lines / report.slop * 100) if report.slop else 0.0
        out.append(f"{name:<28}{fmt_int(t.files):>10}{fmt_int(t.slop_lines):>14}"
                   f"{fmt_float(pct, 1):>10}  {t.cognitivity:<10}")
    agency = report.agency
    name = _(_ROW_LABELS[Category.AGENCY])
    out.append(f"{name:<28}{fmt_int(len({e.file for e in agency})):>10}{'—':>14}"
               f"{'—':>10}  {'—':<10}")
    out.append("-" * 79)
    out.append(f"{_('Total Physical Source Lines of Code (SLOC)'):<55} = {fmt_int(report.sloc)}")
    out.append(f"{_('Total Suspicious Lines Of Prose (SLOP)'):<55} = {fmt_int(report.slop)}")
    out.append(f"{_('Slop Ratio (SLOP/SLOC)'):<55} = {fmt_float(report.slop_ratio, 1)}%")
    return "\n".join(out)


def render_verdict(report: Report) -> str:
    v = verdict_for(report.slop_ratio)
    return f"{_('VERDICT:')} {progress_bar(report.slop_ratio)}  {_(v.text)}"
