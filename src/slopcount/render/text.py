from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from slopcount.evidence import Category, Report
from slopcount.i18n import _, fmt_float, fmt_int, ngettext
from slopcount.metrics import slocomo as sc
from slopcount.scales import grade, progress_bar

# _ROW_LABELS — подписи категорий детекции (английские msgid).
_ROW_LABELS: dict[Category, str] = {
    Category.PROSE: "Prose (comments/docstrings)",
    Category.DOCS: "Markdown specs",
    Category.STYLE: "Code style",
    Category.AGENCY: "Environment markers",
    Category.HISTORY: "Git history",
}


def _fmt_ratio(x: float) -> str:
    return "∞" if x == float("inf") else fmt_float(x, 3)


def _fmt_pm(x: float) -> str:
    """Человеко-месяцы — 1 знак: в ru-локали «122,653» читается как тысячи."""
    return "∞" if x == float("inf") else fmt_float(x, 1)


def _fmt_money(x: float) -> str:
    return "∞" if x == float("inf") else fmt_float(x, 0)


@lru_cache(maxsize=128)
def _read_lines(root: Path, file: str) -> tuple[str, ...] | None:
    """Строки файла для сниппетов; кеш — --evidence/CSV дёргают на каждую улику."""
    try:
        text = (root / file).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()  # хвостовой "" после завершающего \n — не строка файла
    return tuple(lines)


def _snippet(root: Path, file: str, line: int) -> str:
    """Текст исходной строки улики; лениво, для рендера (в Evidence не хранится)."""
    if line <= 0 or file.startswith("git:"):
        return "—"
    lines = _read_lines(root, file)
    if lines is None or line > len(lines):
        return "—"
    return lines[line - 1].strip()[:120]


# ── Секция 1: PROJECT VOLUME ───────────────────────────────────────────


def _ratio_line(label: str, ratio: float, metric: str) -> str:
    g = grade(metric, ratio)
    head = f"{label:<55} = {_fmt_ratio(ratio)} {progress_bar(ratio * 100)} {g.code}"
    return head + f"\n{' ' * 57}{_(g.text)}"


def render_volume(report: Report) -> str:
    v = report.volume
    out = [_("PROJECT VOLUME"), "-" * 79]
    if v.languages:
        out.append(f"{_('Code by language:'):<44}{_('files'):>10}{_('SLOC'):>15}")
        for row in v.languages[:10]:
            out.append(f"{row.language:<44}{fmt_int(row.files):>10}{fmt_int(row.sloc):>15}")
        rest = v.languages[10:]
        if rest:
            more = ngettext("… %d more language", "… %d more languages", len(rest)) % len(rest)
            out.append(
                f"{more:<44}{fmt_int(sum(r.files for r in rest)):>10}"
                f"{fmt_int(sum(r.sloc for r in rest)):>15}"
            )
        out.append("-" * 79)
    out.append(f"{_('Total SLOC'):<55} = {fmt_int(v.sloc)}")
    out.append(f"{_('Files in scan'):<55} = {fmt_int(v.files_total)}")
    md = ngettext("%d line", "%d lines", v.md_lines) % v.md_lines
    out.append(
        f"{_('Documentation'):<55} = {md}"
        f" ({ngettext('%d file', '%d files', v.md_files) % v.md_files})"
    )
    out.append(_ratio_line(_("Documentation-to-Code Ratio (MD/SLOC)"), v.md_sloc_ratio, "doc"))
    cl = ngettext("%d line", "%d lines", v.comment_lines) % v.comment_lines
    out.append(f"{_('Comments'):<55} = {cl}")
    out.append(
        _ratio_line(_("Comments-to-Code Ratio (comment/SLOC)"), v.comment_sloc_ratio, "comment")
    )
    sl = ngettext("%d line", "%d lines", report.slop.total) % report.slop.total
    out.append(f"{_('Detected SLOP'):<55} = {sl}")
    out.append(_ratio_line(_("Slop-to-Code Ratio (SLOP/SLOC)"), report.slop.ratio, "slop"))
    return "\n".join(out)


# ── Секция 2: COMPREHENSION EFFORT & COST ──────────────────────────────


def _cocomo_rows(report: Report) -> list[str]:
    cb = report.cocomo_breakdown
    if cb is None:
        return []
    b = cb.buckets
    rows = [
        f"{'':>11}{_('docs'):<16}{_fmt_pm(b['docs'].person_months):>10}"
        f" {_('person-months')} · $ {_fmt_money(b['docs'].cost)}",
        f"{'':>11}{_('source code'):<16}{_fmt_pm(b['source_code']['total'].person_months):>10}"
        f" {_('person-months')} · $ {_fmt_money(b['source_code']['total'].cost)}",
        f"{'':>13}{_('code'):<14}{_fmt_pm(b['source_code']['code'].person_months):>10}"
        f" {_('person-months')} · $ {_fmt_money(b['source_code']['code'].cost)}",
        f"{'':>13}{_('comments'):<14}{'—':>10}  {_('(scc does not count comments)')}",
        f"{'':>11}{_('data'):<16}{_fmt_pm(b['data'].person_months):>10}"
        f" {_('person-months')} · $ {_fmt_money(b['data'].cost)}",
    ]
    return rows


def _locomo_rows(report: Report) -> list[str]:
    lb = report.locomo_breakdown
    if lb is None:
        return []
    rows = [
        f"{'':>11}{_('docs'):<16}{fmt_float(lb['docs'].hours, 1):>10}"
        f" h · $ {fmt_float(lb['docs'].cost, 2)}",
        f"{'':>11}{_('source code'):<16}{fmt_float(lb['source_code']['total'].hours, 1):>10}"
        f" h · $ {fmt_float(lb['source_code']['total'].cost, 2)}",
        f"{'':>13}{_('code'):<14}{fmt_float(lb['source_code']['code'].hours, 1):>10}"
        f" h · $ {fmt_float(lb['source_code']['code'].cost, 2)}",
        f"{'':>13}{_('comments'):<14}{'—':>10}  {_('(scc does not count comments)')}",
        f"{'':>11}{_('data'):<16}{fmt_float(lb['data'].hours, 1):>10}"
        f" h · $ {fmt_float(lb['data'].cost, 2)}",
    ]
    return rows


def _slocomo_rows(report: Report) -> list[str]:
    r = report.slocomo
    if r is None:
        return []
    b = r.cost_breakdown
    hours = r.reading_components
    code_h = hours["code"] + hours["cognitive"]
    rows = [
        f"{'':>11}{_('docs'):<16}{fmt_float(hours['docs'], 1):>10} h · $ {_fmt_money(b['docs'])}",
        f"{'':>11}{_('source code'):<16}{fmt_float(code_h + hours['comments'], 1):>10}"
        f" h · $ {_fmt_money(b['source_code']['total'])}",
        f"{'':>13}{_('code'):<14}{fmt_float(code_h, 1):>10}"
        f" h · $ {_fmt_money(b['source_code']['code'])}"
        f"  ({_('incl. cognitive %s h') % fmt_float(hours['cognitive'], 1)})",
        f"{'':>13}{_('comments'):<14}{fmt_float(hours['comments'], 1):>10}"
        f" h · $ {_fmt_money(b['source_code']['comments'])}",
        f"{'':>11}{_('data'):<16}{'—':>10}  {_('(not read)')}",
    ]
    return rows


def _cost_ladder(report: Report) -> list[str]:
    out = ["-" * 79, _("Cost Ladder (write / regenerate / comprehend)"), "-" * 79]
    if report.cocomo is not None and report.cocomo_breakdown is not None:
        cb = report.cocomo_breakdown
        out.append(
            f"{_('COCOMO  write the whole tree (docs count as code)'):<48}"
            f" = $ {_fmt_money(report.cocomo.cost)}"
            f" ({_fmt_pm(cb.total_person_months)} {_('person-months')}"
            f" · {fmt_float(report.cocomo.schedule_months, 1)} {_('mo')}"
            f" · {fmt_float(report.cocomo.people, 1)} {_('people')})"
        )
        out.extend(_cocomo_rows(report))
    if report.locomo is not None:
        gen_h = report.locomo.generation_seconds / 3600
        out.append(
            f"{_('LOCOMO  regenerate it with an LLM'):<48}"
            f" = $ {fmt_float(report.locomo.cost, 2)}"
            f" ({fmt_float(gen_h, 1)} {_('h')} + {fmt_float(report.locomo.review_hours, 1)}"
            f" {_('h')} {_('review')})"
        )
        out.extend(_locomo_rows(report))
    r = report.slocomo
    if r is not None:
        out.append(
            f"{_('SLOCOMO comprehend the project'):<48}"
            f" = $ {_fmt_money(r.cost)} ({fmt_float(r.reading_hours, 1)} {_('h')} {_('reading')}"
            f" · {_fmt_pm(r.person_months)} {_('person-months')}) — {_('per person')}"
        )
        out.append(f"{'':>11}{_('(a team multiplies by headcount — see the scale below)')}")
        out.extend(_slocomo_rows(report))
    return out


def render_comprehension(report: Report) -> str:
    v = report.volume
    r = report.slocomo
    out = [_("COMPREHENSION EFFORT & COST"), "-" * 79]
    if r is not None:
        words = ngettext("%d word", "%d words", v.md_words) % v.md_words
        out.append(
            f"{_('Reading documentation'):<55} = {fmt_float(r.reading_components['docs'], 1)} h"
            f"  ({words} / {fmt_int(sc.WPM)} wpm × {fmt_float(sc.REREAD, 1)})"
        )
        out.append(
            f"{_('Reading code'):<55} = {fmt_float(r.reading_components['code'], 1)} h"
            f"  ({fmt_int(v.sloc)} SLOC / {fmt_int(sc.SLOC_PER_HOUR)} {_('per hour')})"
        )
        comment_words = int(v.comment_lines * sc.COMMENT_WORDS_PER_LINE)
        cw = ngettext("%d word", "%d words", comment_words) % comment_words
        out.append(
            f"{_('Reading comments'):<55} = {fmt_float(r.reading_components['comments'], 1)} h"
            f"  ({cw}, {_('lines × %d estimate') % int(sc.COMMENT_WORDS_PER_LINE)})"
        )
        pts = ngettext("%d point", "%d points", v.cognitive_total) % v.cognitive_total
        out.append(
            f"{_('Cognitive processing'):<55} = {fmt_float(r.reading_components['cognitive'], 1)} h"
            f"  ({pts} × {fmt_float(sc.COG_MINUTES, 1)} min)"
        )
        out.append(f"{_('Total reading time'):<55} = {fmt_float(r.reading_hours, 1)} h")
    out.append("")
    out.extend(_cost_ladder(report))
    if r is not None:
        out.append("")
        out.append(_("Team Comprehension Cost (headcount × per person)"))
        for people, person_months, cost in r.team_costs:
            unit = ngettext("%d person", "%d people", people) % people
            out.append(
                f"{unit:>12} = {_fmt_pm(person_months)} {_('person-months')} · $ {_fmt_money(cost)}"
            )
        if r.comprehension_tokens is not None:
            out.append("")
            out.append(
                f"{_('Comprehension Tokens (LOCOMO round-trip: in + out)'):<55}"
                f" = {fmt_float(r.comprehension_tokens, 0)}"
            )
            out.append(
                f"{_('Context Windows Consumed'):<55}"
                f" = {fmt_float(r.context_windows_200k, 4)} × 200K"
                f" / {fmt_float(r.context_windows_1m, 4)} × 1M"
            )
            out.append(f"{_('GPU-hours of Regret'):<55} = {fmt_float(r.gpu_hours, 4)}")
        out.append("")
        coffee = ngettext("%d cup", "%d cups", r.coffee_cups) % r.coffee_cups
        out.append(f"{_('Coffee Required'):<55} = {coffee} ($ {fmt_float(r.coffee_cost)})")
        if r.therapy_sessions:
            sessions = (
                ngettext("%d session", "%d sessions", r.therapy_sessions) % r.therapy_sessions
            )
            out.append(
                f"{_('Therapy Recommended'):<55} = {sessions} ($ {fmt_float(r.therapy_cost)})"
            )
    return "\n".join(out)


# ── Секция 3: DETECTED SLOP ────────────────────────────────────────────


def render_slop(report: Report) -> str:
    s = report.slop
    labels = {cat: _(_ROW_LABELS[cat]) for cat in Category}
    label_w = max(len(_("Origin")), *(len(n) for n in labels.values())) + 1
    out = [
        _("DETECTED SLOP"),
        "-" * 79,
        _("Totals grouped by slop origin (dominant slop source first):"),
        "-" * 79,
        f"{_('Origin'):<{label_w}}{_('files'):>10}{_('slop lines'):>14}"
        f"{_('slop %'):>10}  {_('cognitivity'):<10}",
        "-" * 79,
    ]
    ordered = sorted(
        [c for c in Category if c is not Category.AGENCY],
        key=lambda c: s.categories[c].slop_lines,
        reverse=True,
    )
    for cat in ordered:
        t = s.categories[cat]
        name = labels[cat]
        if cat is Category.HISTORY and report.history_commits:
            name = name + f" ({report.history_commits})"
        pct = (t.slop_lines / s.total * 100) if s.total else 0.0
        out.append(
            f"{name:<{label_w}}{fmt_int(t.files):>10}{fmt_int(t.slop_lines):>14}"
            f"{fmt_float(pct, 1):>10}  {_(t.cognitivity):<10}"
        )
    agency = s.agency
    name = labels[Category.AGENCY]
    out.append(
        f"{name:<{label_w}}{fmt_int(len({e.file for e in agency})):>10}{'—':>14}"
        f"{'—':>10}  {'—':<10}"
    )
    out.append("-" * 79)
    if s.top_files:
        parts = [f"{p} {ngettext('%d line', '%d lines', n) % n}" for p, n in s.top_files]
        out.append(f"{_('Top slop files:')}  " + " · ".join(parts))
    if agency:
        names = ", ".join(sorted({e.file for e in agency}))
        out.append(f"{_('Agents detected (not counted as slop):')} {names}")
    out.append(_("Run with --evidence to see every finding with its source line."))
    return "\n".join(out)


def render_evidence(report: Report) -> str:
    out = [_("EVIDENCE (every finding, most severe first, with source lines)")]
    root = Path(report.root)
    for e in sorted(report.slop.details, key=lambda e: -e.weight):
        out.append(
            f"{e.file}:{e.line}  [{e.category.value}]  {e.description} → +{e.weight}"
            f"  | {_snippet(root, e.file, e.line)}"
        )
    return "\n".join(out)
