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


def render_slocomo(report: Report) -> str:
    r = report.slocomo
    if r is None:
        return ""
    mode = " (approximate)" if r.approximate else ""
    lines = [
        "-" * 79,
        f"{_('Cognitive Awareness Effort, Person-Years (Person-Months)'):<57}"
        f" = {fmt_float(r.person_years)} ({fmt_float(r.person_months)}){mode}",
        _("(SLOCOMO model, Person-Months = 2.4 * (KSLOP**1.05))"),
        f"{_('Schedule of Despair, Years (Months)'):<57}"
        f" = {fmt_float(r.schedule_months / 12)} ({fmt_float(r.schedule_months)})",
        _("(SLOCOMO model, Months = 2.5 * (person-months**0.38))"),
        f"{_('Estimated Average Number of Therapists (Effort/Schedule)'):<57}"
        f" = {fmt_float(r.therapists)}",
        f"{_('Total Estimated Cost to Comprehend'):<57} = $ {fmt_float(r.cost)}",
        f"{_('Context Windows Consumed'):<57}"
        f" = {fmt_float(r.context_windows_200k)} × 200K / {fmt_float(r.context_windows_1m)} × 1M",
        f"{_('GPU-hours of Regret'):<57} = {fmt_float(r.gpu_hours)}",
        f"{_('Coffee Required'):<57}"
        f" = {fmt_int(r.coffee_cups)} ($ {fmt_float(r.coffee_cost)})",
    ]
    if r.therapy_sessions:
        lines.append(
            f"{_('Therapy Recommended'):<57}"
            f" = {fmt_int(r.therapy_sessions)} ($ {fmt_float(r.therapy_cost)})")
    return "\n".join(lines)


def render_verdict(report: Report) -> str:
    v = verdict_for(report.slop_ratio)
    return f"{_('VERDICT:')} {progress_bar(report.slop_ratio)}  {_(v.text)}"
