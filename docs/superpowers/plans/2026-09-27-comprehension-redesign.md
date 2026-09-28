# Comprehension Redesign 0.5.0 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Перестроить slopcount по спеке `docs/superpowers/specs/2026-09-27-comprehension-redesign-design.md`: три секции отчёта (объём / понимание / детекция), SLOCOMO от объёма проекта, разбивки стоимостей по корзинам, три шкалы вместо вердикта, `--evidence`.

**Architecture:** Снизу вверх аддитивными шагами: новые модули (`scales.py`, `metrics/costs.py`, блоки `VolumeStats`/`SlopStats`, новый `compute()`) — затем интеграция конвейера с переходными зеркалами старой модели, переключение рендеров+CLI+i18n, JSON/CSV и чистка легаси, калибровка, документация.

**Tech Stack:** Python 3.11, typer, scc 4.1.0 (subprocess), gettext (en msgid / ru каталог), pytest.

**Спека — источник истины; цитаты §N по ней.** Все тесты: `.venv/bin/python -m pytest … -q`; линтер: `.venv/bin/ruff check .` и `.venv/bin/ruff format --check .`.

---

### Task 1: `scales.py` — три шкалы вместо вердикта

**Files:**
- Create: `src/slopcount/scales.py`
- Create: `tests/test_scales.py`
- (`verdicts.py` удаляется в Task 7; пока не трогаем)

- [ ] **Step 1: Write the failing test**

`tests/test_scales.py`:

```python
from slopcount.i18n import setup
from slopcount.scales import SCALES, grade, progress_bar


def test_doc_scale_boundaries():
    assert grade("doc", 0).code == "HUMAN"
    assert grade("doc", 0.049).code == "HUMAN"
    assert grade("doc", 0.05).code == "NEURO_CLOUD"
    assert grade("doc", 0.349).code == "NEURO_CLOUD"
    assert grade("doc", 0.35).code == "ESTABLISHED_SLOP"
    assert grade("doc", 0.50).code == "AGENT_SELF_SERVICE"
    assert grade("doc", 0.75).code == "AGENT_OCCUPATION"
    assert grade("doc", 0.999).code == "AGENT_OCCUPATION"
    assert grade("doc", 1.0).code == "RECURSION"
    assert grade("doc", float("inf")).code == "RECURSION"


def test_comment_and_slop_scale_structure():
    """5 категорий, коды уникальны, границы возрастают (значения границ
    может уточнить калибровка — тест проверяет структуру, не константы)."""
    for metric in ("comment", "slop"):
        entries = SCALES[metric]
        codes = [g.code for _b, g in entries]
        assert len(codes) == len(set(codes)) == 5
        bounds = [b for b, _g in entries]
        assert bounds == sorted(bounds)
        # последняя границы inf → grade всегда находит категорию
        assert bounds[-1] == float("inf")
        assert grade(metric, 1e9).code == codes[-1]


def test_grade_texts_are_english_msgids():
    for entries in SCALES.values():
        for _b, g in entries:
            assert g.text and g.code.isupper()


def test_progress_bar():
    setup("en")  # в прогресс-баре локализованный процент — фиксируем en
    assert progress_bar(50.0, width=4) == "[██░░] 50.0%"
    assert progress_bar(float("inf")) == "[░░░░░░░░░░░░░░░░░░░░] inf%"
    assert progress_bar(150.0, width=4) == "[████] 150.0%"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_scales.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'slopcount.scales'`

- [ ] **Step 3: Write `src/slopcount/scales.py`**

```python
from __future__ import annotations

from dataclasses import dataclass

from slopcount.i18n import fmt_float


@dataclass(frozen=True)
class Grade:
    code: str
    text: str  # английский msgid; переводится через _() при рендере


# doc: откалибровано (спека 2026-09-26-md-sloc-ratio-design.md);
# RECURSION при >= 1.0 — шутка самоскана, живёт вне списка границ.
_DOC: list[tuple[float, Grade]] = [
    (0.05, Grade("HUMAN", "Almost human. Suspiciously clean. Where are you hiding the slop?")),
    (
        0.35,
        Grade("NEURO_CLOUD", "A light neuro-haze: the slop has arrived, but so far it does the dishes"),
    ),
    (
        0.50,
        Grade("ESTABLISHED_SLOP", "The slop has settled in for good. More documentation than meaning"),
    ),
    (0.75, Grade("AGENT_SELF_SERVICE", "Repository on LLM self-service. Humans visit on weekends")),
    (1.00, Grade("AGENT_OCCUPATION", "Agent occupation. Resistance is futile")),
]
_RECURSION = Grade("RECURSION", "You ran slopcount inside slop. Recursion")

# comment/slop: черновые границы до эмпирической калибровки
# (спека 2026-09-27-comprehension-redesign-design.md §7.1; Task 8 уточнит).
_COMMENT: list[tuple[float, Grade]] = [
    (0.05, Grade("ASCETIC", "Not a single comment. The code speaks for itself, apparently")),
    (0.30, Grade("DOCUMENTED", "Healthy commentary. Docs and code in balance")),
    (0.60, Grade("CHATTY", "The code is chatty: comments grow thick")),
    (1.00, Grade("LECTURE_NOTES", "Lecture notes with occasional code samples")),
    (float("inf"), Grade("COMMENT_DRIVEN", "Comment-driven development. The code is an attachment")),
]
_SLOP: list[tuple[float, Grade]] = [
    (0.02, Grade("CLEAN", "Detectors found nothing. Either clean or sneaky")),
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_scales.py -q`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add src/slopcount/scales.py tests/test_scales.py
git commit -m "feat: scales.py — три per-metric шкалы (doc/comment/slop) вместо вердикта"
```

---

### Task 2: `metrics/costs.py` — разбивки стоимостей по корзинам

**Files:**
- Create: `src/slopcount/metrics/costs.py`
- Create: `tests/test_costs.py`

- [ ] **Step 1: Write the failing test**

`tests/test_costs.py`:

```python
from slopcount.metrics.costs import CocomoSplit, attribute_locomo, split_cocomo, split_slocomo
from slopcount.scc import Cocomo, Locomo


def _cocomo():
    # фактические цифры scc 4.1.0 для naumen-smp-mcp (проверено до доллара,
    # спека §5.4): 2.4·(111.841)^1.05 = 339.7 PM × 4690.5 × 2.4
    return Cocomo(cost=3_825_363.5675040204, schedule_months=22.9, people=14.84)


def _locomo():
    return Locomo(
        cost=57.13,
        input_tokens=8_440_553.1,
        output_tokens=2_120_575.3,
        generation_seconds=42_411.5,
        review_hours=18.64,
        cycles=1.9,
        preset="medium",
    )


def test_split_cocomo_independent_buckets():
    cs = split_cocomo(
        _cocomo(),
        docs_lines=71_706,
        code_lines=38_639,
        data_lines=1_496,
        personcost=4690.50,
        overhead=2.4,
    )
    assert isinstance(cs, CocomoSplit)
    assert abs(cs.buckets["docs"].person_months - 2.4 * 71.706**1.05) < 0.05
    assert abs(cs.buckets["code"].person_months - 2.4 * 38.639**1.05) < 0.05
    rate = 4690.50 * 2.4
    assert abs(cs.buckets["docs"].cost - cs.buckets["docs"].person_months * rate) < 1.0
    assert cs.buckets["docs"].lines == 71_706
    # НЕаддитивность: сумма корзин < total (суперлинейность 2.4·K^1.05)
    assert sum(b.cost for b in cs.buckets.values()) < cs.total_person_months * rate


def test_split_cocomo_drift_guard_warns(capsys):
    skewed = Cocomo(cost=10_000_000.0, schedule_months=22.9, people=14.84)
    split_cocomo(
        skewed, docs_lines=71_706, code_lines=38_639, data_lines=1_496,
        personcost=4690.50, overhead=2.4,
    )
    assert "drift" in capsys.readouterr().err


def test_split_cocomo_no_drift_warning_on_match(capsys):
    split_cocomo(
        _cocomo(), docs_lines=71_706, code_lines=38_639, data_lines=1_496,
        personcost=4690.50, overhead=2.4,
    )
    assert capsys.readouterr().err == ""


def test_attribute_locomo_sums_exactly():
    lb = attribute_locomo(_locomo(), docs_lines=71_706, code_lines=38_639, data_lines=1_496)
    total_hours = 42_411.5 / 3600 + 18.64
    assert abs(sum(b.hours for b in lb.values()) - total_hours) < 1e-9
    assert abs(sum(b.cost for b in lb.values()) - 57.13) < 1e-9
    share_docs = 71_706 / 111_841
    assert abs(lb["docs"].hours - total_hours * share_docs) < 1e-6
    assert abs(lb["docs"].cost - 57.13 * share_docs) < 1e-6


def test_split_slocomo_additive():
    comps = {"docs": 135.0, "code": 192.0, "comments": 5.0, "cognitive": 101.0}
    b = split_slocomo(comps, slop_ratio=0.0071, personcost=4690.50, overhead=2.4)
    factor = 1.0071 * 4690.50 * 2.4 / 152
    assert abs(b["docs"] - 135.0 * factor) < 1e-6
    assert abs(b["code"] - (192.0 + 101.0) * factor) < 1e-6
    total_hours = 135.0 + 192.0 + 5.0 + 101.0
    assert abs(sum(b.values()) - total_hours * factor) < 1e-6
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_costs.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'slopcount.metrics.costs'`

- [ ] **Step 3: Write `src/slopcount/metrics/costs.py`**

```python
from __future__ import annotations

import sys
from dataclasses import dataclass, field

from slopcount.i18n import _
from slopcount.scc import Cocomo, Locomo


@dataclass(frozen=True)
class CocomoBucket:
    lines: int
    person_months: float
    cost: float


@dataclass(frozen=True)
class CocomoSplit:
    total_person_months: float
    buckets: dict[str, CocomoBucket] = field(default_factory=dict)


@dataclass(frozen=True)
class LocomoBucket:
    lines: int
    hours: float
    cost: float


def split_cocomo(
    cocomo: Cocomo,
    *,
    docs_lines: int,
    code_lines: int,
    data_lines: int,
    personcost: float,
    overhead: float,
) -> CocomoSplit:
    """Независимые оценки по корзинам: PM = 2.4·(K)^1.05 (репликация
    базового COCOMO organic из scc — проверено до доллара, спека §6.1).
    Неаддитивность принята; сверка total с scc — drift-guard."""
    total_lines = docs_lines + code_lines + data_lines
    pm_total = 2.4 * (total_lines / 1000) ** 1.05
    pm_implied = cocomo.cost / (personcost * overhead) if personcost and overhead else 0.0
    if pm_implied and abs(pm_total - pm_implied) / pm_implied > 0.01:
        print(
            _(
                "slopcount: scc COCOMO model drift detected: replica %.1f vs implied "
                "%.1f person-months; bucket split may differ"
            )
            % (pm_total, pm_implied),
            file=sys.stderr,
        )
    rate = personcost * overhead
    buckets = {
        name: CocomoBucket(lines=lines, person_months=2.4 * (lines / 1000) ** 1.05, cost=0.0)
        for name, lines in (("docs", docs_lines), ("code", code_lines), ("data", data_lines))
    }
    buckets = {
        name: CocomoBucket(lines=b.lines, person_months=b.person_months, cost=b.person_months * rate)
        for name, b in buckets.items()
    }
    return CocomoSplit(total_person_months=pm_total, buckets=buckets)


def attribute_locomo(
    locomo: Locomo, *, docs_lines: int, code_lines: int, data_lines: int
) -> dict[str, LocomoBucket]:
    """Атрибуция фактических цифр LOCOMO по долям Code-строк корзин —
    аддитивно ровно к total; модель scc не реплицируем (спека §6.2)."""
    total_lines = docs_lines + code_lines + data_lines
    total_hours = locomo.generation_seconds / 3600 + locomo.review_hours
    out: dict[str, LocomoBucket] = {}
    for name, lines in (("docs", docs_lines), ("code", code_lines), ("data", data_lines)):
        share = lines / total_lines if total_lines else 0.0
        out[name] = LocomoBucket(lines=lines, hours=total_hours * share, cost=locomo.cost * share)
    return out


def split_slocomo(
    reading_components: dict[str, float], *, slop_ratio: float, personcost: float, overhead: float
) -> dict[str, float]:
    """Точная аддитивная разбивка SLOCOMO-стоимости (линейная модель,
    спека §6.3): code = чтение кода + когнитивная обработка;
    152 = HOURS_PER_PERSON_MONTH (COCOMO II)."""
    factor = (1 + slop_ratio) * personcost * overhead / 152
    return {
        "docs": reading_components["docs"] * factor,
        "comments": reading_components["comments"] * factor,
        "code": (reading_components["code"] + reading_components["cognitive"]) * factor,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_costs.py -q`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add src/slopcount/metrics/costs.py tests/test_costs.py
git commit -m "feat: metrics/costs.py — разбивки COCOMO/LOCOMO/SLOCOMO по корзинам docs/code/data"
```

---

### Task 3: `evidence.py` — блоки VolumeStats/SlopStats + aggregate_slop

**Files:**
- Modify: `src/slopcount/evidence.py` (после `CategoryTotals`, перед `Report`)
- Modify: `src/slopcount/evidence.py:75-100` (`Report` — добавить поля, легаси не трогаем)
- Modify: `tests/test_evidence.py` (полная замена)

Переходное поле нового блока слопа называется `slop_stats` (легаси-поле `slop: int`
ещё живо до Task 7; финальное имя `slop` — переименование в Task 7).

- [ ] **Step 1: Write the failing tests (полная замена `tests/test_evidence.py`)**

```python
from slopcount.evidence import (
    Category,
    CategoryTotals,
    Evidence,
    LanguageRow,
    SlopStats,
    VolumeStats,
    aggregate_slop,
    safe_ratio,
)


def _ev(file, line, cat, weight):
    return Evidence(file=file, line=line, category=cat, weight=weight, description="d")


def test_aggregate_slop_counts_unique_lines_per_category():
    evs = [
        _ev("a.py", 1, Category.PROSE, 5),
        _ev("a.py", 1, Category.PROSE, 2),  # та же строка — не удваивает slop_lines
        _ev("a.py", 9, Category.PROSE, 5),
        _ev("b.py", 3, Category.STYLE, 1),
    ]
    s = aggregate_slop(evs, sloc=100)
    assert s.categories[Category.PROSE].files == 1
    assert s.categories[Category.PROSE].slop_lines == 2
    assert s.categories[Category.PROSE].weight == 12
    assert s.categories[Category.STYLE].files == 1


def test_aggregate_slop_total_and_ratio_with_infected_md():
    evs = [_ev("README.md", 1, Category.DOCS, 5)]
    s = aggregate_slop(evs, sloc=100, infected=[("SPEC.md", 40)])
    # 1 улика + round(40 * 0.8); ratio — доля (33/100), не проценты
    assert s.total == 33
    assert abs(s.ratio - 0.33) < 1e-9
    assert s.infected_md_lines == 32


def test_aggregate_slop_top_files():
    evs = [
        _ev("a.py", 1, Category.PROSE, 5),
        _ev("a.py", 2, Category.PROSE, 5),
        _ev("b.md", 4, Category.DOCS, 2),
    ]
    s = aggregate_slop(evs, sloc=50, infected=[("big.md", 100)])  # +80 строк big.md
    assert s.top_files[0] == ("big.md", 80)
    assert ("a.py", 2) in s.top_files
    assert len(s.top_files) <= 5


def test_aggregate_slop_agency_excluded():
    evs = [_ev(".claude", 0, Category.AGENCY, 3)]
    s = aggregate_slop(evs, sloc=10)
    assert s.total == 0 and s.ratio == 0.0
    assert len(s.agency) == 1
    assert s.details == evs


def test_aggregate_slop_full_formula():
    evs = [
        _ev("a.py", 1, Category.PROSE, 5),
        _ev("a.py", 1, Category.STYLE, 2),  # разные категории на одной строке
        _ev("b.md", 4, Category.DOCS, 2),
        _ev("git:ab12cd34", 2, Category.HISTORY, 5),
        _ev(".claude", 0, Category.AGENCY, 3),  # не входит в SLOP
    ]
    s = aggregate_slop(evs, sloc=50, infected=[("big.md", 100)])
    # уникальных строк с уликами: (a.py,1), (b.md,4), (git:...,2) = 3; md: round(100*.8)=80
    assert s.total == 83
    assert abs(s.ratio - 1.66) < 1e-9  # доля: 83/50


def test_safe_ratio_edges():
    assert safe_ratio(5, 0) == float("inf")
    assert safe_ratio(0, 0) == 0.0
    assert abs(safe_ratio(30, 200) - 0.15) < 1e-9


def test_volume_stats_defaults():
    v = VolumeStats()
    assert (v.sloc, v.md_files, v.md_lines, v.md_words) == (0, 0, 0, 0)
    assert v.languages == []
    assert isinstance(SlopStats().categories, dict)


def test_language_row_ordering_source():
    rows = [LanguageRow("Python", 2, 8), LanguageRow("C", 1, 9)]
    assert sorted(rows, key=lambda r: -r.sloc)[0].language == "C"


def test_cognitivity_grades():
    assert CategoryTotals(files=1, slop_lines=10, weight=40).cognitivity == "high"
    assert CategoryTotals(files=1, slop_lines=10, weight=20).cognitivity == "medium"
    assert CategoryTotals(files=1, slop_lines=10, weight=5).cognitivity == "low"
    assert CategoryTotals(files=1, slop_lines=0, weight=7).cognitivity == "low"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_evidence.py -q`
Expected: FAIL — `ImportError: cannot import name 'LanguageRow'`

- [ ] **Step 3: Добавить блоки в `src/slopcount/evidence.py`**

После `CategoryTotals` (перед `Report`) вставить:

```python
@dataclass
class LanguageRow:
    language: str  # display-имя scc
    files: int
    sloc: int


@dataclass
class VolumeStats:
    """Секция 1 отчёта: объём проекта (спека 0.5.0 §3)."""

    sloc: int = 0  # Σ Code, kind=code
    comment_lines: int = 0  # Σ Comment, kind=code
    complexity: int = 0  # Σ Complexity, kind=code (факт; в формулах не участвует)
    cognitive_total: int = 0  # Σ Cognitive, kind=code — вход reading_hours
    files_total: int = 0  # весь манифест scc (включая data)
    languages: list[LanguageRow] = field(default_factory=list)  # только kind=code
    md_files: int = 0  # .md/.markdown (kind=markdown + фильтр расширения)
    md_lines: int = 0
    md_words: int = 0  # честный Σ слов kind=markdown+prose (для чтения)
    md_sloc_ratio: float = 0.0  # доля; inf при sloc=0 и md>0
    comment_sloc_ratio: float = 0.0


@dataclass
class SlopStats:
    """Секция 3 отчёта: детектированный слоп (спека 0.5.0 §3)."""

    total: int = 0  # SLOP: улики (prose/docs/style/history) + заражённые md
    ratio: float = 0.0  # total/sloc; inf при sloc=0 и total>0
    infected_md_lines: int = 0
    categories: dict[Category, CategoryTotals] = field(
        default_factory=lambda: {c: CategoryTotals() for c in Category}
    )
    top_files: list[tuple[str, int]] = field(default_factory=list)  # топ-5 по слоп-строкам
    agency: list[Evidence] = field(default_factory=list)  # AGENCY не входит в SLOP
    details: list[Evidence] = field(default_factory=list)


def safe_ratio(numerator: float, denominator: float) -> float:
    """Доля; denominator=0 → inf при числителе > 0, иначе 0.0."""
    if denominator == 0:
        return float("inf") if numerator > 0 else 0.0
    return numerator / denominator


def aggregate_slop(
    evidences: list[Evidence], *, sloc: int, infected: list[tuple[str, int]] = ()
) -> SlopStats:
    lines_per_cat: dict[Category, set[tuple[str, int]]] = defaultdict(set)
    files_per_cat: dict[Category, set[str]] = defaultdict(set)
    weight_per_cat: dict[Category, int] = defaultdict(int)
    for e in evidences:
        lines_per_cat[e.category].add((e.file, e.line))
        files_per_cat[e.category].add(e.file)
        weight_per_cat[e.category] += e.weight

    stats = SlopStats(
        agency=[e for e in evidences if e.category is Category.AGENCY],
        details=list(evidences),
    )
    stats.infected_md_lines = sum(round(n * 0.8) for _, n in infected)
    for cat in Category:
        totals = stats.categories[cat]
        totals.files = len(files_per_cat[cat])
        totals.slop_lines = len(lines_per_cat[cat])
        totals.weight = weight_per_cat[cat]

    # SLOP: уникальные строки с уликами (agency не входит) + заражённые md-строки
    slop_lines: set[tuple[str, int]] = set()
    for cat in (Category.PROSE, Category.DOCS, Category.STYLE, Category.HISTORY):
        slop_lines |= lines_per_cat[cat]
    per_file: dict[str, int] = defaultdict(int)
    for file, _line in slop_lines:
        per_file[file] += 1
    for file, n in infected:
        per_file[file] += round(n * 0.8)
    stats.top_files = sorted(per_file.items(), key=lambda kv: (-kv[1], kv[0]))[:5]
    stats.total = len(slop_lines) + stats.infected_md_lines
    stats.ratio = safe_ratio(stats.total, sloc)
    return stats
```

В `Report` добавить новые поля (легаси-поля остаются до Task 7):

```python
    volume: VolumeStats = field(default_factory=VolumeStats)
    slop_stats: SlopStats = field(default_factory=SlopStats)  # Task 7: переименовать в slop
    cocomo_breakdown: "CocomoSplit | None" = None  # TYPE_CHECKING: from slopcount.metrics.costs import CocomoSplit
    locomo_breakdown: dict | None = None
```

И в `TYPE_CHECKING`-блок вверху файла добавить:

```python
    from slopcount.metrics.costs import CocomoSplit
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_evidence.py tests/test_scales.py tests/test_costs.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/slopcount/evidence.py tests/test_evidence.py
git commit -m "feat: VolumeStats/SlopStats/aggregate_slop — блоки новой модели данных"
```

---

### Task 4: `metrics/slocomo.py` — ComprehensionStats и новый compute()

**Files:**
- Modify: `src/slopcount/metrics/slocomo.py` (полная замена)
- Modify: `src/slopcount/evidence.py:9-12` (TYPE_CHECKING: SlocomoResult → ComprehensionStats) и поле `Report.slocomo`
- Modify: `src/slopcount/app.py` (место вызова + счётчик md_words; `flagged_words` удалить)
- Modify: `tests/test_slocomo.py` (полная замена)

- [ ] **Step 1: Write the failing tests (полная замена `tests/test_slocomo.py`)**

```python
from slopcount.app import Options
from slopcount.metrics.slocomo import TEAM_SIZES, compute
from slopcount.scc import Locomo


def _locomo():
    return Locomo(
        cost=57.13,
        input_tokens=100_000.0,
        output_tokens=28_000.0,
        generation_seconds=3600.0,
        review_hours=1.0,
        cycles=1.9,
        preset="medium",
    )


def test_reading_components():
    r = compute(
        md_words=23_800, comment_lines=60, sloc=200, cognitive_total=100,
        slop_ratio=0.0, locomo=None, opts=Options(),
    )
    assert abs(r.reading_components["docs"] - 23_800 / 238 / 60 * 2.3) < 1e-9
    assert abs(r.reading_components["comments"] - 60 * 6 / 238 / 60) < 1e-9
    assert abs(r.reading_components["code"] - 200 / 200) < 1e-9
    assert abs(r.reading_components["cognitive"] - 100 * 0.5 / 60) < 1e-9
    assert abs(r.reading_hours - sum(r.reading_components.values())) < 1e-9


def test_person_months_formula():
    r = compute(
        md_words=0, comment_lines=0, sloc=15_200, cognitive_total=0,
        slop_ratio=0.5, locomo=None, opts=Options(),
    )
    # чтение = 15200/200 = 76 ч; pm = 76/152 × 1.5 = 0.75
    assert abs(r.person_months - 0.75) < 1e-9
    assert abs(r.schedule_months - 2.5 * 0.75**0.38) < 1e-9
    assert abs(r.cost - 0.75 * 4690.50 * 2.4) < 1e-6


def test_tokens_from_locomo():
    r = compute(
        md_words=0, comment_lines=0, sloc=100, cognitive_total=0,
        slop_ratio=0.0, locomo=_locomo(), opts=Options(),
    )
    assert abs(r.comprehension_tokens - 128_000.0) < 1e-6
    assert abs(r.context_windows_200k - 128_000 / 200_000) < 1e-9
    assert abs(r.context_windows_1m - 128_000 / 1_000_000) < 1e-9
    assert abs(r.gpu_hours - 128_000 / 100 / 3600) < 1e-9


def test_tokens_none_without_locomo():
    r = compute(
        md_words=0, comment_lines=0, sloc=100, cognitive_total=0,
        slop_ratio=0.0, locomo=None, opts=Options(),
    )
    assert r.comprehension_tokens is None
    assert r.context_windows_200k is None and r.gpu_hours is None


def test_team_costs():
    r = compute(
        md_words=0, comment_lines=0, sloc=15_200, cognitive_total=0,
        slop_ratio=0.5, locomo=None, opts=Options(),
    )
    assert [n for n, _pm, _c in r.team_costs] == list(TEAM_SIZES)
    one_pm, one_cost = r.team_costs[0][1], r.team_costs[0][2]
    assert abs(one_pm - r.person_months) < 1e-9
    for n, pm, cost in r.team_costs:
        assert abs(pm - n * r.person_months) < 1e-9
        assert abs(cost - n * r.cost) < 1e-6


def test_cost_breakdown_additive():
    r = compute(
        md_words=23_800, comment_lines=60, sloc=200, cognitive_total=100,
        slop_ratio=0.0, locomo=None, opts=Options(),
    )
    assert abs(sum(r.cost_breakdown.values()) - r.cost) < 1e-6
    assert set(r.cost_breakdown) == {"docs", "comments", "code"}


def test_inf_slop_ratio_edges():
    r = compute(
        md_words=100, comment_lines=0, sloc=0, cognitive_total=0,
        slop_ratio=float("inf"), locomo=None, opts=Options(),
    )
    assert r.person_months == float("inf")
    assert r.cost == float("inf")
    assert r.therapists == float("inf")
    assert r.therapy_sessions is None  # ∞
    assert r.coffee_cups == 1  # от конечного reading


def test_zero_reading():
    r = compute(
        md_words=0, comment_lines=0, sloc=0, cognitive_total=0,
        slop_ratio=0.0, locomo=None, opts=Options(),
    )
    assert r.person_months == 0.0 and r.schedule_months == 0.0 and r.therapists == 0.0
    assert r.therapy_sessions == 1  # max(1, ceil(0))
    assert r.coffee_cups == 0


def test_no_therapy_flag():
    r = compute(
        md_words=0, comment_lines=0, sloc=100, cognitive_total=0,
        slop_ratio=0.0, locomo=None, opts=Options(no_therapy=True),
    )
    assert r.therapy_sessions == 0 and r.therapy_cost == 0.0


def test_coffee_and_therapy():
    r = compute(
        md_words=23_800, comment_lines=0, sloc=0, cognitive_total=100,
        slop_ratio=0.0, locomo=None, opts=Options(coffee_price=4.0),
    )
    # чтение = 3.83 ч + 0.83 ч = 4.67 ч → 2 чашки
    assert r.coffee_cups == 2
    assert abs(r.coffee_cost - 8.0) < 1e-9
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_slocomo.py -q`
Expected: FAIL — `TypeError: compute() got an unexpected keyword argument 'md_words'`

- [ ] **Step 3: Полная замена `src/slopcount/metrics/slocomo.py`**

```python
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

from slopcount.metrics.costs import split_slocomo

if TYPE_CHECKING:  # цикл: app → slocomo → app; типы только для аннотаций
    from slopcount.app import Options
    from slopcount.scc import Locomo

WPM = 238.0
REREAD = 2.3
COMMENT_WORDS_PER_LINE = 6.0
SLOC_PER_HOUR = 200.0
COG_MINUTES = 0.5
HOURS_PER_PERSON_MONTH = 152.0  # стандарт COCOMO II (19 дней × 8 ч)
TEAM_SIZES = (1, 2, 3, 5, 8, 13, 21)  # Фибоначчи: шкала команды (спека §5.2)
THERAPY_PRICE = 150.0


@dataclass(frozen=True)
class ComprehensionStats:
    """SLOCOMO на новой концепции: стоимость понимания ПРОЕКТА (спека §5).
    Все величины — в расчёте на одного человека (per person)."""

    reading_hours: float
    reading_components: dict[str, float]  # docs/code/comments/cognitive, часы
    person_months: float
    person_years: float
    schedule_months: float
    therapists: float
    cost: float  # НА ОДНОГО человека
    cost_breakdown: dict[str, float]  # docs/comments/code → $
    team_costs: list[tuple[int, float, float]]  # (человек, person-months, $)
    comprehension_tokens: float | None  # LOCOMO in+out; None → рендер «—»
    context_windows_200k: float | None
    context_windows_1m: float | None
    gpu_hours: float | None
    coffee_cups: int
    coffee_cost: float
    therapy_sessions: int | None  # None = ∞ (slop_ratio=inf); 0 при --no-therapy
    therapy_cost: float


def compute(
    *,
    md_words: int,
    comment_lines: int,
    sloc: int,
    cognitive_total: int,
    slop_ratio: float,
    locomo: "Locomo | None",
    opts: "Options",
) -> ComprehensionStats:
    """reading_hours отражает реальный объём проекта (спека §5.1):
    доки (238 wpm × 2.3 перечитывания) + комментарии (строки × 6 слов)
    + код (200 SLOC/ч) + когнитива (0.5 мин/балл, весь проект)."""
    components = {
        "docs": md_words / WPM / 60 * REREAD,
        "comments": comment_lines * COMMENT_WORDS_PER_LINE / WPM / 60,
        "code": sloc / SLOC_PER_HOUR,
        "cognitive": cognitive_total * COG_MINUTES / 60,
    }
    reading = sum(components.values())
    person_months = reading / HOURS_PER_PERSON_MONTH * (1 + slop_ratio)
    schedule = 2.5 * person_months**0.38
    if math.isinf(person_months):
        therapists = float("inf")
    else:
        therapists = person_months / schedule if schedule else 0.0
    cost = person_months * opts.personcost * opts.overhead
    tokens = None
    if locomo is not None:
        tokens = locomo.input_tokens + locomo.output_tokens
    coffee = math.ceil(reading / 4) if reading > 0 else 0
    if opts.no_therapy:
        sessions: int | None = 0
    elif math.isinf(person_months):
        sessions = None
    else:
        sessions = max(1, math.ceil(person_months * 2))
    return ComprehensionStats(
        reading_hours=reading,
        reading_components=components,
        person_months=person_months,
        person_years=person_months / 12,
        schedule_months=schedule,
        therapists=therapists,
        cost=cost,
        cost_breakdown=split_slocomo(
            components, slop_ratio=slop_ratio, personcost=opts.personcost, overhead=opts.overhead
        ),
        team_costs=[(n, person_months * n, cost * n) for n in TEAM_SIZES],
        comprehension_tokens=tokens,
        context_windows_200k=tokens / 200_000 if tokens is not None else None,
        context_windows_1m=tokens / 1_000_000 if tokens is not None else None,
        gpu_hours=tokens / 100 / 3600 if tokens is not None else None,
        coffee_cups=coffee,
        coffee_cost=coffee * opts.coffee_price,
        therapy_sessions=sessions,
        therapy_cost=sessions * THERAPY_PRICE if sessions else 0.0,
    )
```

- [ ] **Step 4: Обновить ссылки на переименованный тип**

`src/slopcount/evidence.py`, TYPE_CHECKING-блок: `from slopcount.metrics.slocomo import SlocomoResult` → `from slopcount.metrics.slocomo import ComprehensionStats`; аннотация поля `Report.slocomo: SlocomoResult | None = None` → `ComprehensionStats | None = None`.

- [ ] **Step 5: Пропатчить место вызова в `src/slopcount/app.py`**

Удалить функцию `flagged_words` (строки 37-40). В `run()`:

- удалить локальные `prose_words = 0` и `cog_points = 0`, все их накопления
  (`prose_words += flagged_words(...)`, `prose_words += int(len(text.split()) * 0.8)`,
  `if style_evs: cog_points += row.cognitive`);
- в ветке `if sf.kind == "markdown":` добавить `md_words`-накопление; ввести
  локальный `md_words = 0` рядом с `md_files = 0`; для kind=prose слова тоже
  считаются — заменить ветку на:

```python
        if sf.kind == "code":
            row = by_path[sf.path]
            style_evs = style_detector.detect(sf, text)
            evidences.extend(style_evs)
        else:  # markdown | prose — объём доков и заражённость (спека §5.1)
            md_words += len(text.split())
            if sf.kind == "markdown" and sf.path.lower().endswith((".md", ".markdown")):
                md_files += 1
                md_lines += by_path[sf.path].lines
            bloat = docs_bloat.detect(sf, text)
            evidences.extend(bloat.evidences)
            infected.extend(bloat.infected)
```

- заменить финальный вызов:

```python
    report.slocomo = slocomo_compute(
        md_words=md_words,
        comment_lines=comment_lines,
        sloc=sloc,
        cognitive_total=cognitive_total,
        slop_ratio=report.slop_ratio,
        locomo=manifest.locomo,
        opts=opts,
    )
```

(локальные `sloc`, `comment_lines`, `cognitive_total` уже копятся в цикле — не удалять.)

- [ ] **Step 6: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/ -q --ignore=tests/test_render.py`
Expected: PASS, КРОМЕ `test_render.py::test_text_renderer_golden` — он исключён сознательно: числа SLOCOMO в выводе изменились, эталон регенерируется в Task 6 (подписи старого рендера не менялись, остальные e2e-ассерты подстрочные и остаются зелёными).

- [ ] **Step 7: Commit**

```bash
git add src/slopcount/metrics/slocomo.py src/slopcount/evidence.py src/slopcount/app.py tests/test_slocomo.py
git commit -m "feat!: SLOCOMO = стоимость понимания проекта (ComprehensionStats, per person + команда)"
```

---

### Task 5: `app.py` — фазовый конвейер и wiring новой модели

**Files:**
- Modify: `src/slopcount/app.py` (полная замена `run()`)
- Modify: `src/slopcount/evidence.py:103-156` (удалить старую `aggregate()`)
- Modify: `tests/test_render.py` (удалить `test_json_inf_becomes_null` — вернётся в Task 7)

Легаси-поля `Report` пока заполняются зеркалами (рендеры ещё старые — переключаем в Task 6; зеркала и легаси-поля удаляем в Task 7).

- [ ] **Step 1: Replace `run()` в `src/slopcount/app.py`**

Импорты вверху `app.py` заменить на:

```python
from collections import Counter

from slopcount import scc
from slopcount.detectors.code_style import CodeStyleDetector
from slopcount.detectors.docs_bloat import DocsBloatDetector, repo_bloat_evidence
from slopcount.detectors.env_markers import EnvMarkerDetector
from slopcount.detectors.phrase import PhraseDetector
from slopcount.evidence import (
    Evidence,
    LanguageRow,
    Report,
    ScannedFile,
    VolumeStats,
    aggregate_slop,
    read_text,
    safe_ratio,
)
from slopcount.i18n import _
from slopcount.metrics.costs import attribute_locomo, split_cocomo
from slopcount.metrics.slocomo import compute as slocomo_compute
from slopcount.rules import load_languages, load_rules
```

Новое тело `run()` (целиком; детекторы и их порядок не меняются — спека §4):

```python
def run(opts: Options) -> Report:
    root = Path(opts.paths[0])
    if len(opts.paths) > 1:
        print(
            _("slopcount: multiple paths given, scanning only the first: %s") % opts.paths[0],
            file=sys.stderr,
        )
    langmap = load_languages(opts.rules)
    manifest = scc.collect(
        root, personcost=opts.personcost, overhead=opts.overhead, scc_path=opts.scc_path
    )
    # kind/language из каталога языков; неизвестный scc-язык → ("data", None)
    files: list[ScannedFile] = []
    for f in manifest.files:
        kind_lang = langmap.get(f.language_name, ("data", None))
        files.append(ScannedFile(f.path, kind_lang[1], kind_lang[0], f.size))

    # ── Фаза volume: объём проекта из манифеста (спека §4) ──────────────
    volume = VolumeStats(files_total=len(manifest.files))
    lang_files: Counter[str] = Counter()
    lang_sloc: Counter[str] = Counter()
    bucket_lines: Counter[str] = Counter()  # kind → Σ Code (корзины стоимостей)
    for f, sf in zip(manifest.files, files):
        bucket_lines[sf.kind] += f.code
        if sf.kind != "code":
            continue
        volume.sloc += f.code
        volume.comment_lines += f.comment
        volume.complexity += f.complexity
        volume.cognitive_total += f.cognitive
        lang_files[f.language_name] += 1
        lang_sloc[f.language_name] += f.code
    volume.languages = [
        LanguageRow(lang, lang_files[lang], lang_sloc[lang])
        for lang in sorted(lang_sloc, key=lambda l: (-lang_sloc[l], l))
    ]
    docs_bucket_lines = bucket_lines["markdown"] + bucket_lines["prose"]

    # ── Фаза detect: один проход по читаемым файлам ─────────────────────
    phrase = PhraseDetector(load_rules(opts.rules))
    docs_bloat = DocsBloatDetector()
    style_detector = CodeStyleDetector()
    pplx = None
    if opts.perplexity:
        from slopcount.detectors.perplexity import PerplexityDetector, available

        if not available():
            raise RuntimeError(
                _(
                    "slopcount: --perplexity requires extras; "
                    "pipx install 'slopcount[perplexity]' and "
                    "python -m slopcount.download_model"
                )
            )
        pplx = PerplexityDetector()
    by_path = {f.path: f for f in manifest.files}
    evidences: list[Evidence] = []
    infected: list[tuple[str, int]] = []
    md_files = 0
    md_lines = 0
    md_words = 0
    skip = 0
    n = 0
    progressed = False
    is_stderr_tty = sys.stderr.isatty()
    total = sum(1 for f in files if f.kind in ("code", "markdown", "prose"))
    for sf in files:
        if sf.kind not in ("code", "markdown", "prose"):
            continue
        text = read_text(root / sf.path)
        if text is None:
            skip += 1
            continue
        n += 1
        if is_stderr_tty and n % 200 == 0:
            print(f"\rscanned {n}/{total} files...", end="", file=sys.stderr)
            progressed = True
        if sf.kind == "code":
            evidences.extend(style_detector.detect(sf, text))
        else:  # markdown | prose — объём доков (спека §5.1)
            md_words += len(text.split())
            if sf.kind == "markdown":
                if sf.path.lower().endswith((".md", ".markdown")):
                    md_files += 1
                    md_lines += by_path[sf.path].lines
                bloat = docs_bloat.detect(sf, text)  # детекция — только markdown (спека §4)
                evidences.extend(bloat.evidences)
                infected.extend(bloat.infected)
        evidences.extend(phrase.detect(sf, text))
        if pplx is not None and sf.kind in ("markdown", "prose"):
            evidences.extend(pplx.detect(sf, text))
    if progressed:
        print(file=sys.stderr)  # завершаем строку прогресса
    rb = repo_bloat_evidence(files, volume.sloc)
    if rb:
        evidences.append(rb)
    evidences.extend(EnvMarkerDetector().detect(root, files, read_text))
    history_commits: int | None = None
    if opts.history:
        from slopcount.detectors.git_history import GitUnavailable
        from slopcount.detectors.git_history import detect as git_detect

        try:
            hist_evs, commits = git_detect(root, opts.history)
            evidences.extend(hist_evs)
            history_commits = commits
        except GitUnavailable:
            print(_("slopcount: git history unavailable; skipping archaeology"), file=sys.stderr)
    volume.md_files = md_files
    volume.md_lines = md_lines
    volume.md_words = md_words
    volume.md_sloc_ratio = safe_ratio(md_lines, volume.sloc)
    volume.comment_sloc_ratio = safe_ratio(volume.comment_lines, volume.sloc)

    # ── Фаза aggregate: SlopStats ───────────────────────────────────────
    slop_stats = aggregate_slop(evidences, sloc=volume.sloc, infected=infected)

    # ── Фаза comprehension: SLOCOMO + разбивки стоимостей ───────────────
    # (slocomo_compute импортирован наверху: цикла больше нет — Options в
    # slocomo.py живёт только в TYPE_CHECKING)
    slocomo = slocomo_compute(
        md_words=md_words,
        comment_lines=volume.comment_lines,
        sloc=volume.sloc,
        cognitive_total=volume.cognitive_total,
        slop_ratio=slop_stats.ratio,
        locomo=manifest.locomo,
        opts=opts,
    )
    report = Report(
        root=str(root),
        skip_count=skip,
        history_commits=history_commits,
        volume=volume,
        slop_stats=slop_stats,
        scc_version=manifest.scc_version,
        cocomo=manifest.cocomo,
        locomo=manifest.locomo,
        slocomo=slocomo,
    )
    if manifest.cocomo is not None:
        report.cocomo_breakdown = split_cocomo(
            manifest.cocomo,
            docs_lines=docs_bucket_lines,
            code_lines=bucket_lines["code"],
            data_lines=bucket_lines["data"],
            personcost=opts.personcost,
            overhead=opts.overhead,
        )
    if manifest.locomo is not None:
        report.locomo_breakdown = attribute_locomo(
            manifest.locomo,
            docs_lines=docs_bucket_lines,
            code_lines=bucket_lines["code"],
            data_lines=bucket_lines["data"],
        )

    # ── Переходные зеркала старой модели (удаляются в Task 7) ───────────
    report.sloc = volume.sloc
    report.categories = slop_stats.categories
    report.slop = slop_stats.total
    report.slop_ratio = slop_stats.ratio
    report.infected_md_lines = slop_stats.infected_md_lines
    report.md_files = md_files
    report.md_lines = md_lines
    report.md_sloc_ratio = volume.md_sloc_ratio
    report.comment_lines = volume.comment_lines
    report.comment_sloc_ratio = volume.comment_sloc_ratio
    report.details = slop_stats.details
    report.agency = slop_stats.agency
    report.complexity = volume.complexity
    report.cognitive_total = volume.cognitive_total
    report.files_total = volume.files_total
    return report
```

- [ ] **Step 2: Удалить старую `aggregate()` из `evidence.py`** (функция `aggregate`, строки с `def aggregate(` по конец функции) — пользователей больше нет.

- [ ] **Step 3: Удалить `test_json_inf_becomes_null` из `tests/test_render.py`** (использует удалённую `aggregate`; новая версия на новой схеме вернётся в Task 7).

- [ ] **Step 4: Run full suite**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: PASS — все тесты, включая e2e (старые рендеры работают от зеркал; формулы SLOCOMO в выводе изменились, но старые e2e-ассерты их не пинят, кроме `"SLOCOMO model, Person-Months = 2.4 * (KSLOP**1.05))"` — этой строки больше нет!)

Если `test_slocomo_block_present` падает на `"Cognitive Awareness Effort"` / `"(SLOCOMO model, ...)"` — это ожидаемо: временно поправить ассерты в `tests/test_e2e.py::test_slocomo_block_present` на:

```python
def test_slocomo_block_present():
    _code, out = run_cli([str(SLOP), "--lang", "en"])
    assert "Reading documentation" in out  # новая компонентная раскладка
    assert "Total reading time" in out
    assert "GPU-hours of Regret" in out
```

- [ ] **Step 5: Commit**

```bash
git add src/slopcount/app.py src/slopcount/evidence.py tests/test_render.py tests/test_e2e.py
git commit -m "feat: фазовый конвейер run() — volume/detect/aggregate/comprehension + разбивки"
```

---

### Task 6: Рендеры трёх секций, `--evidence`, CLI, i18n

**Files:**
- Modify: `src/slopcount/render/text.py` (полная замена)
- Modify: `src/slopcount/cli.py`
- Modify: `src/slopcount/app.py` (`Options`: `details`→`evidence`, удалить `fail_above`/`verdict_only`)
- Modify: `src/slopcount/locale/ru/LC_MESSAGES/slopcount.po` + перекомпиляция `.mo`
- Modify: `tests/test_e2e.py`, `tests/test_cli.py`
- Regenerate: `tests/golden/slop_project_en.txt`

- [ ] **Step 1: Полная замена `src/slopcount/render/text.py`**

```python
from __future__ import annotations

from pathlib import Path

from slopcount.evidence import Category, Report
from slopcount.i18n import _, fmt_float, fmt_int, ngettext
from slopcount.metrics import slocomo as sc
from slopcount.scales import grade, progress_bar

# _ROW_LABELS — существующий словарь Category → подпись; НЕ менять.
_ROW_LABELS: dict[Category, str] = {
    Category.PROSE: "Prose (comments/docstrings)",
    Category.DOCS: "Markdown specs",
    Category.STYLE: "Code style",
    Category.AGENCY: "Environment markers",
    Category.HISTORY: "Git history",
}


def _fmt_ratio(x: float) -> str:
    return "∞" if x == float("inf") else fmt_float(x, 3)


def _fmt_money(x: float) -> str:
    return "∞" if x == float("inf") else fmt_float(x, 0)


def _snippet(root: Path, file: str, line: int) -> str:
    """Текст исходной строки улики; лениво, для рендера (в Evidence не хранится)."""
    if line <= 0 or file.startswith("git:"):
        return "—"
    try:
        text = (root / file).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return "—"
    lines = text.split("\n")
    if line > len(lines):
        return "—"
    return lines[line - 1].strip()[:120]


# ── Секция 1: PROJECT VOLUME ───────────────────────────────────────────


def _ratio_line(label: str, ratio: float, metric: str) -> str:
    g = grade(metric, ratio)
    head = (
        f"{label:<55} = {_fmt_ratio(ratio)} {progress_bar(ratio * 100)} {g.code}"
    )
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
    out.append(_ratio_line(_("Comments-to-Code Ratio (comment/SLOC)"), v.comment_sloc_ratio, "comment"))
    sl = ngettext("%d line", "%d lines", report.slop_stats.total) % report.slop_stats.total
    out.append(f"{_('Detected SLOP'):<55} = {sl}")
    out.append(_ratio_line(_("Slop-to-Code Ratio (SLOP/SLOC)"), report.slop_stats.ratio, "slop"))
    return "\n".join(out)


# ── Секция 2: COMPREHENSION EFFORT & COST ──────────────────────────────


def _cocomo_rows(report: Report) -> list[str]:
    rows = []
    cb = report.cocomo_breakdown
    if cb is None:
        return rows
    for name in ("docs", "code", "data"):
        b = cb.buckets[name]
        pm = _fmt_ratio(b.person_months)
        rows.append(f"{'':>11}{_(name):<10}{pm:>8} {_('person-months')} · $ {_fmt_money(b.cost)}")
    rows.append(f"{'':>11}{_('comments'):<10}{'—':>8}  {_('(outside the scc COCOMO model)')}")
    return rows


def _locomo_rows(report: Report) -> list[str]:
    rows = []
    lb = report.locomo_breakdown
    if lb is None:
        return rows
    for name in ("docs", "code", "data"):
        b = lb[name]
        rows.append(f"{'':>11}{_(name):<10}{fmt_float(b.hours, 1):>8} h · $ {fmt_float(b.cost, 2)}")
    return rows


def _slocomo_rows(report: Report) -> list[str]:
    r = report.slocomo
    rows = []
    if r is None:
        return rows
    hours = {
        "docs": r.reading_components["docs"],
        "comments": r.reading_components["comments"],
        "code": r.reading_components["code"] + r.reading_components["cognitive"],
    }
    for name in ("docs", "comments", "code"):
        cost = r.cost_breakdown.get(name, 0.0)
        rows.append(
            f"{'':>11}{_(name):<10}{fmt_float(hours[name], 1):>8} h · $ {_fmt_money(cost)}"
        )
    return rows


def _cost_ladder(report: Report) -> list[str]:
    out = ["-" * 79, _("Cost Ladder (write / regenerate / comprehend)"), "-" * 79]
    if report.cocomo is not None and report.cocomo_breakdown is not None:
        cb = report.cocomo_breakdown
        out.append(
            f"{_('COCOMO  write the whole tree (docs count as code)'):<49}"
            f"= $ {_fmt_money(report.cocomo.cost)}"
            f" ({_fmt_ratio(cb.total_person_months)} {_('person-months')}"
            f" · {fmt_float(report.cocomo.schedule_months, 1)} {_('mo')}"
            f" · {fmt_float(report.cocomo.people, 1)} {_('people')})"
        )
        out.extend(_cocomo_rows(report))
    if report.locomo is not None:
        gen_h = report.locomo.generation_seconds / 3600
        out.append(
            f"{_('LOCOMO  regenerate it with an LLM'):<49}"
            f"= $ {fmt_float(report.locomo.cost, 2)}"
            f" ({fmt_float(gen_h, 1)} {_('h')} + {fmt_float(report.locomo.review_hours, 1)}"
            f" {_('h')} {_('review')})"
        )
        out.extend(_locomo_rows(report))
    r = report.slocomo
    if r is not None:
        out.append(
            f"{_('SLOCOMO comprehend the project'):<49}"
            f"= $ {_fmt_money(r.cost)} ({fmt_float(r.reading_hours, 1)} h reading"
            f" · {_fmt_ratio(r.person_months)} {_('person-months')}) — {_('per person')}"
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
            pm = _fmt_ratio(person_months)
            out.append(f"{unit:>12} = {pm} {_('person-months')} · $ {_fmt_money(cost)}")
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
            sessions = ngettext("%d session", "%d sessions", r.therapy_sessions) % r.therapy_sessions
            out.append(
                f"{_('Therapy Recommended'):<55} = {sessions} ($ {fmt_float(r.therapy_cost)})"
            )
    return "\n".join(out)


# ── Секция 3: DETECTED SLOP ────────────────────────────────────────────


def render_slop(report: Report) -> str:
    s = report.slop_stats
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
    for e in sorted(report.slop_stats.details, key=lambda e: -e.weight):
        out.append(
            f"{e.file}:{e.line}  [{e.category.value}]  {e.description} → +{e.weight}"
            f"  | {_snippet(root, e.file, e.line)}"
        )
    return "\n".join(out)
```

(Если в текущем файле `_ROW_LABELS` содержит другие подписи — сохранить текущие значения, меняется только окружающий код.)

- [ ] **Step 2: Обновить `src/slopcount/app.py` Options и `src/slopcount/cli.py`**

`Options`: поле `details: bool = False` → `evidence: bool = False`; удалить `fail_above` и `verdict_only`.

`cli.py`, функция `scan`:
- параметр `details` → `evidence: bool = typer.Option(False, "--evidence", help="List every finding with its source line")`;
- удалить параметры `fail_above` и `verdict_only` (и их `typer.Option`-блоки);
- в конструкторе `Options(...)` — соответственно `evidence=evidence`, без удалённых полей;
- заменить блок вывода:

```python
    if json_out:
        print(render_json(report))
    elif csv_out:
        print(render_csv(report), end="")
    else:
        print(render_volume(report))
        print(render_comprehension(report))
        print(render_slop(report))
        if evidence:
            print(render_evidence(report))
```

- удалить финальный блок `if fail_above is not None and report.md_sloc_ratio > fail_above:`;
- обновить импорты из `slocount.render.text`: `render_volume, render_comprehension, render_slop, render_evidence` вместо старых.

- [ ] **Step 3: Обновить тесты `tests/test_e2e.py`**

Заменить/удалить следующие тесты (остальные не трогать):

```python
def test_mvp_run_on_slop_fixture():
    code, out = run_cli([str(SLOP), "--lang", "en"])
    assert code == 0
    assert "PROJECT VOLUME" in out
    assert "Total SLOC" in out
    assert "Detected SLOP" in out
    assert "DETECTED SLOP" in out
    assert "Prose (comments/docstrings)" in out


def test_docs_category_in_output():
    import re

    _code, out = run_cli([str(SLOP), "--lang", "en"])
    m = re.search(r"Markdown specs\s+\d+\s+(\d+)", out)
    assert m and int(m.group(1)) == 2  # DOCS slop lines from fixture
    assert re.search(r"Detected SLOP\s+= 16", out)  # 7 улик + 9 заражённых


def test_style_category_in_output():
    import re

    _code, out = run_cli([str(SLOP), "--lang", "en"])
    m = re.search(r"Code style\s+\d+\s+(\d+)", out)
    assert m and int(m.group(1)) == 2  # STYLE: defensive.py lines 2+13
    assert re.search(r"Detected SLOP\s+= 16", out)


def test_recursion_grade_on_pure_slop(tmp_path):
    (tmp_path / "ONLY_SLOP.md").write_text("Great question! " * 200)
    _code, out = run_cli([str(tmp_path), "--lang", "en"])
    assert "RECURSION" in out


def test_slocomo_block_present():
    _code, out = run_cli([str(SLOP), "--lang", "en"])
    assert "COMPREHENSION EFFORT & COST" in out
    assert "Reading documentation" in out
    assert "Total reading time" in out
    assert "Team Comprehension Cost" in out
    assert "GPU-hours of Regret" in out


def test_evidence_lists_findings_with_snippets():
    _code, out = run_cli([str(SLOP), "--evidence", "--lang", "en"])
    assert "EVIDENCE" in out
    assert "greeter.py" in out
    assert "[prose]" in out and "+5" in out
    assert "|" in out  # разделитель сниппета исходной строки


def test_evidence_ru_translated():
    _code, out = run_cli([str(SLOP), "--evidence", "--lang", "ru"])
    assert "УЛИКИ" in out
    assert "greeter.py" in out
    assert "Классический энтузиазм LLM" in out  # описание улики из каталога фраз


def test_ru_output():
    _code, out = run_cli([str(SLOP), "--lang", "ru"])
    assert "ОБЪЁМ ПРОЕКТА" in out
    assert "УСИЛИЕ И СТОИМОСТЬ ПОНИМАНИЯ" in out
    assert "Итоги по источникам слопа" in out


def test_md_sloc_lines_in_output():
    _code, out = run_cli([str(SLOP), "--lang", "en"])
    assert "Documentation-to-Code Ratio (MD/SLOC)" in out
    assert "RECURSION" in out
    assert "Comments-to-Code Ratio (comment/SLOC)" in out
    assert "Slop-to-Code Ratio (SLOP/SLOC)" in out


def test_ru_md_sloc_lines():
    _code, out = run_cli([str(SLOP), "--lang", "ru"])
    assert "Документация на код (MD/SLOC)" in out
    assert "Комментарии к коду (comment/SLOC)" in out


def test_human_fixture_stays_clean():
    _code, out = run_cli([str(HUMAN), "--lang", "en"])
    assert "Slop-to-Code Ratio (SLOP/SLOC)" in out
    assert "HUMAN" in out  # doc-шкала: md=0 → HUMAN
    assert "Almost human" in out
```

Удалить: старый `test_recursion_verdict_on_pure_slop`, `test_details_lists_evidence`, `test_details_ru_translated`, старые версии заменённых тестов. В `test_history_flag_on_git_repo` заменить `assert re.search(r"Total Suspicious Lines Of Prose \(SLOP\)\s+= \d+", out)` на `assert re.search(r"Detected SLOP\s+= \d+", out)`.

- [ ] **Step 4: Обновить тесты `tests/test_cli.py`**

- удалить `test_fail_above_triggers_exit_1`, `test_fail_below_ok`, `test_verdict_only_suppresses_details`;
- `test_help_exit_0`: список флагов → `("--evidence", "--history", "--perplexity")`;
- `test_rules_repeated_accumulates`: `"--details"` → `"--evidence"`;
- добавить:

```python
def test_removed_flags_rejected(tmp_path):
    for flag in ("--details", "--fail-above", "--verdict-only"):
        code, _ = run_cli([str(tmp_path), flag, "--lang", "en"])
        assert code == 2
```

- [ ] **Step 5: i18n — добавить новые msgid в po и перекомпилировать mo**

В `src/slopcount/locale/ru/LC_MESSAGES/slopcount.po` добавить блоки (в конец файла; существующие не трогать):

```po
msgid "PROJECT VOLUME"
msgstr "ОБЪЁМ ПРОЕКТА"

msgid "Code by language:"
msgstr "Код по языкам:"

msgid "… %d more language"
msgid_plural "… %d more languages"
msgstr[0] "… ещё %d язык"
msgstr[1] "… ещё %d языка"
msgstr[2] "… ещё %d языков"

msgid "Total SLOC"
msgstr "Всего SLOC"

msgid "Files in scan"
msgstr "Файлов в скане"

msgid "Documentation"
msgstr "Документация"

msgid "Comments"
msgstr "Комментарии"

msgid "Detected SLOP"
msgstr "Детектированный слоп"

msgid "Slop-to-Code Ratio (SLOP/SLOC)"
msgstr "Доля слопа (SLOP/SLOC)"

msgid "COMPREHENSION EFFORT & COST"
msgstr "УСИЛИЕ И СТОИМОСТЬ ПОНИМАНИЯ"

msgid "Reading documentation"
msgstr "Чтение документации"

msgid "Reading code"
msgstr "Чтение кода"

msgid "Reading comments"
msgstr "Чтение комментариев"

msgid "Cognitive processing"
msgstr "Когнитивная обработка"

msgid "Total reading time"
msgstr "Полное время чтения"

msgid "%d word"
msgid_plural "%d words"
msgstr[0] "%d слово"
msgstr[1] "%d слова"
msgstr[2] "%d слов"

msgid "%d point"
msgid_plural "%d points"
msgstr[0] "%d балл"
msgstr[1] "%d балла"
msgstr[2] "%d баллов"

msgid "per hour"
msgstr "в час"

msgid "lines × %d estimate"
msgstr "строки × %d — оценка"

msgid "COCOMO  write the whole tree (docs count as code)"
msgstr "COCOMO  написать всё дерево (доки считаются кодом)"

msgid "SLOCOMO comprehend the project"
msgstr "SLOCOMO понять проект"

msgid "per person"
msgstr "на человека"

msgid "(a team multiplies by headcount — see the scale below)"
msgstr "(команда умножает стоимость на численность — см. шкалу ниже)"

msgid "Team Comprehension Cost (headcount × per person)"
msgstr "Стоимость понимания командой (численность × на человека)"

msgid "%d person"
msgid_plural "%d people"
msgstr[0] "%d человек"
msgstr[1] "%d человека"
msgstr[2] "%d человек"

msgid "person-months"
msgstr "человеко-месяцев"

msgid "people"
msgstr "человек"

msgid "Comprehension Tokens (LOCOMO round-trip: in + out)"
msgstr "Токены понимания (полный цикл LOCOMO: вход + выход)"

msgid "(outside the scc COCOMO model)"
msgstr "(вне модели COCOMO у scc)"

msgid "docs"
msgstr "доки"

msgid "code"
msgstr "код"

msgid "data"
msgstr "данные"

msgid "comments"
msgstr "комментарии"

msgid "DETECTED SLOP"
msgstr "ДЕТЕКТИРОВАННЫЙ СЛОП"

msgid "Top slop files:"
msgstr "Топ файлов по слопу:"

msgid "Agents detected (not counted as slop):"
msgstr "Обнаружены агенты (в слоп не входит):"

msgid "Run with --evidence to see every finding with its source line."
msgstr "Запустите с --evidence, чтобы увидеть каждую улику с текстом строки."

msgid "EVIDENCE (every finding, most severe first, with source lines)"
msgstr "УЛИКИ (все находки, по убыванию веса, с текстом строк)"

msgid ""
"slopcount: scc COCOMO model drift detected: replica %.1f vs implied %.1f "
"person-months; bucket split may differ"
msgstr ""
"slopcount: обнаружен дрейф модели COCOMO у scc: реплика %.1f против "
"подразумеваемых %.1f человеко-месяцев; разбивка может отличаться"

msgid "Not a single comment. The code speaks for itself, apparently"
msgstr "Ни одного комментария. Код, видимо, говорит сам за себя"

msgid "Healthy commentary. Docs and code in balance"
msgstr "Здоровые комментарии. Доки и код в балансе"

msgid "The code is chatty: comments grow thick"
msgstr "Код разговорчив: комментарии разрастаются"

msgid "Lecture notes with occasional code samples"
msgstr "Конспект лекций с редкими примерами кода"

msgid "Comment-driven development. The code is an attachment"
msgstr "Разработка в комментариях. Код — приложение"

msgid "Detectors found nothing. Either clean or sneaky"
msgstr "Детекторы ничего не нашли. Либо чисто, либо хитро"

msgid "Traces of slop. Nothing a mop cannot handle"
msgstr "Следы слопа. Швабра справится"

msgid "Noticeable slop. The mop is wearing out"
msgstr "Заметный слоп. Швабра изнашивается"

msgid "Heavy slop contamination"
msgstr "Сильное загрязнение слопом"

msgid "Full slop infestation. Call the exterminators"
msgstr "Полное засилье слопа. Зовите дезинсекторов"
```

Проверить покрытие (используемые `_()`-строки и тексты `Grade(` из `scales.py` должны быть в po):

```bash
.venv/bin/python - <<'EOF'
import re, pathlib
po = pathlib.Path("src/slopcount/locale/ru/LC_MESSAGES/slopcount.po").read_text()
po_ids = set(re.findall(r'^msgid "((?:[^"\\]|\\.)*)"', po, re.M))
src = "".join(p.read_text() for p in pathlib.Path("src/slopcount").rglob("*.py"))
used = set(re.findall(r'_\(\s*"((?:[^"\\]|\\.)*)"', src))
used |= set(re.findall(r'Grade\("[A-Z_]+", "((?:[^"\\]|\\.)*)"\)', src))
missing = sorted(m for m in used if m not in po_ids)
print("MISSING:", missing if missing else "none")
EOF
```

Expected: `MISSING: none` (строки вида `_('Origin')` и т.п. уже есть в po).

Перекомпилировать (drift-тест `test_i18n.py` проверяет побайтово):

```bash
msgfmt --check -o src/slopcount/locale/ru/LC_MESSAGES/slopcount.mo \
  src/slopcount/locale/ru/LC_MESSAGES/slopcount.po
```

- [ ] **Step 6: Регенерация golden-файла**

```bash
rm tests/golden/slop_project_en.txt
GOLDEN=1 .venv/bin/python -m pytest tests/test_render.py::test_text_renderer_golden -q
```

Просмотреть новый эталон глазами: `cat tests/golden/slop_project_en.txt` — три секции, RECURSION/COMMENT_DRIVEN/INFESTED у трёх ratio, разбивки лестницы, шкала команды, подсказка `--evidence`.

- [ ] **Step 7: Run full suite**

Run: `.venv/bin/python -m pytest tests/ -q && .venv/bin/ruff check . && .venv/bin/ruff format --check .`
Expected: PASS (json/csv-тесты старой схемы всё ещё зелёные — они идут от зеркал)

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat!: три секции отчёта + --evidence; awareness→comprehension; ru-каталог"
```

---

### Task 7: JSON/CSV новой схемы + чистка легаси

**Files:**
- Modify: `src/slopcount/render/json_out.py` (полная замена)
- Modify: `src/slopcount/render/csv_out.py`
- Modify: `src/slopcount/evidence.py` (`Report` — финальная форма, `slop_stats` → `slop`)
- Modify: `src/slopcount/app.py` (удалить зеркала)
- Delete: `src/slopcount/verdicts.py`
- Modify: `tests/test_render.py` (полная замена), `tests/test_e2e.py` (app-level тесты на `report.volume.*`)

- [ ] **Step 1: Полная замена `src/slopcount/render/json_out.py`**

```python
from __future__ import annotations

import json
import math

from slopcount.evidence import Report
from slopcount.scales import grade


def _rf(x: float | None, nd: int) -> float | None:
    """Округление; inf/nan → None (JSON не любит Infinity)."""
    if x is None or not math.isfinite(x):
        return None
    return round(x, nd)


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
            "cost_breakdown": {k: _rf(x, 2) for k, x in r.cost_breakdown.items()},
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
            "breakdown": {
                name: {
                    "lines": b.lines,
                    "person_months": _rf(b.person_months, 2),
                    "cost": _rf(b.cost, 2),
                }
                for name, b in cb.buckets.items()
            },
        }
    if report.locomo is not None:
        lb = report.locomo_breakdown or {}
        locomo = {
            "cost": _rf(report.locomo.cost, 2),
            "input_tokens": _rf(report.locomo.input_tokens, 1),
            "output_tokens": _rf(report.locomo.output_tokens, 1),
            "generation_seconds": _rf(report.locomo.generation_seconds, 1),
            "review_hours": _rf(report.locomo.review_hours, 2),
            "cycles": _rf(report.locomo.cycles, 2),
            "preset": report.locomo.preset,
            "breakdown": {
                name: {"lines": b.lines, "hours": _rf(b.hours, 2), "cost": _rf(b.cost, 2)}
                for name, b in lb.items()
            },
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
```

- [ ] **Step 2: `src/slopcount/render/csv_out.py` — колонка source**

```python
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
            [e.file, e.line, e.category.value, e.weight, e.description, _snippet(root, e.file, e.line)]
        )
    return buf.getvalue()
```

- [ ] **Step 3: Финальная форма `Report` + переименование `slop_stats` → `slop`**

В `src/slopcount/evidence.py` заменить класс `Report` целиком (легаси-поля удаляются):

```python
@dataclass
class Report:
    root: str
    skip_count: int = 0
    history_commits: int | None = None
    volume: VolumeStats = field(default_factory=VolumeStats)
    slop: SlopStats = field(default_factory=SlopStats)
    scc_version: str = ""
    cocomo: SccCocomo | None = None
    locomo: SccLocomo | None = None
    cocomo_breakdown: "CocomoSplit | None" = None
    locomo_breakdown: "dict[str, LocomoBucket] | None" = None
    slocomo: ComprehensionStats | None = None  # модуль metrics.slocomo
```

В TYPE_CHECKING-блок добавить: `from slopcount.metrics.costs import CocomoSplit, LocomoBucket`.

Массовое переименование по всему репозиторию (рендеры/тесты уже пишутся через `report.slop_stats` в Task 6 — переименовываем):

```bash
grep -rl slop_stats src tests | xargs sed -i 's/slop_stats/slop/g'
```

В `src/slopcount/app.py` удалить весь переходный блок зеркал (комментарий «Переходные зеркала старой модели…» и все присваивания `report.sloc = …` … `report.files_total = …`).

- [ ] **Step 4: Удалить `src/slopcount/verdicts.py`**

```bash
git rm src/slopcount/verdicts.py
grep -rn "verdicts" src tests || echo "ссылок нет"
```

- [ ] **Step 5: Полная замена `tests/test_render.py`**

```python
import csv
import io
import json

import pytest
from test_e2e import HUMAN, SLOP, run_cli

pytestmark = pytest.mark.usefixtures("scc_ready")


def test_json_output_new_model():
    _code, out = run_cli([str(SLOP), "--json", "--lang", "en"])
    data = json.loads(out)
    assert set(data) == {"scan", "volume", "slop", "comprehension", "costs", "evidence_count"}
    assert set(data["scan"]) == {"tool", "files", "skipped", "history_commits"}
    assert set(data["volume"]) == {
        "sloc", "comment_lines", "complexity", "cognitive",
        "md_files", "md_lines", "md_words", "md_sloc_ratio", "comment_sloc_ratio",
        "languages", "grades",
    }
    assert set(data["slop"]) == {"total", "ratio", "infected_md_lines", "categories", "top_files"}
    assert set(data["costs"]) == {"cocomo", "locomo"}
    assert data["volume"]["sloc"] == 8
    assert data["volume"]["comment_lines"] == 12
    assert data["volume"]["md_files"] == 2 and data["volume"]["md_lines"] == 12
    assert data["volume"]["md_sloc_ratio"] == 1.5
    assert data["volume"]["grades"]["doc"] == "RECURSION"
    assert data["slop"]["total"] == 16
    assert data["slop"]["infected_md_lines"] == 9
    assert data["slop"]["top_files"][0]["file"] == "README.md"
    assert data["scan"]["tool"].startswith("scc ")
    assert data["costs"]["locomo"]["preset"] == "medium"
    assert set(data["costs"]["locomo"]["breakdown"]) == {"docs", "code", "data"}
    assert set(data["costs"]["cocomo"]["breakdown"]) == {"docs", "code", "data"}
    comp = data["comprehension"]
    assert set(comp) == {
        "reading_hours", "reading_components", "person_months", "person_years",
        "schedule_months", "therapists", "cost_per_person", "cost_breakdown",
        "team_costs", "comprehension_tokens", "context_windows_200k",
        "context_windows_1m", "gpu_hours", "coffee_cups", "coffee_cost",
        "therapy_sessions", "therapy_cost",
    }
    assert set(comp["reading_components"]) == {"docs", "code", "comments", "cognitive"}
    assert [t["people"] for t in comp["team_costs"]] == [1, 2, 3, 5, 8, 13, 21]
    assert abs(comp["team_costs"][2]["cost"] - 3 * comp["cost_per_person"]) < 0.02
    assert abs(sum(comp["cost_breakdown"].values()) - comp["cost_per_person"]) < 0.01
    json.dumps(data)  # сериализуемо


def test_json_human_fixture_zero_md():
    _code, out = run_cli([str(HUMAN), "--json", "--lang", "en"])
    data = json.loads(out)
    assert data["volume"]["md_files"] == 0
    assert data["volume"]["md_sloc_ratio"] == 0.0
    assert data["volume"]["grades"]["doc"] == "HUMAN"


def test_json_inf_becomes_null(tmp_path):
    from pathlib import Path

    from slopcount.evidence import Report, SlopStats, VolumeStats, safe_ratio
    from slopcount.render.json_out import render_json

    (tmp_path / "ONLY.md").write_text("just text\n")
    rep = Report(
        root=str(tmp_path),
        volume=VolumeStats(md_lines=5, md_sloc_ratio=safe_ratio(5, 0)),
        slop=SlopStats(total=3, ratio=safe_ratio(3, 0)),
    )
    d = json.loads(render_json(rep))
    assert d["volume"]["md_sloc_ratio"] is None
    assert d["slop"]["ratio"] is None
    assert d["comprehension"] is None


def test_csv_rows_with_source():
    _code, out = run_cli([str(SLOP), "--csv", "--lang", "en"])
    rows = list(csv.reader(io.StringIO(out)))
    assert rows[0] == ["file", "line", "category", "weight", "description", "source"]
    assert any(r[3] == "5" for r in rows[1:])
    assert any(len(r[5]) > 0 for r in rows[1:])  # сниппеты не пустые


def test_text_renderer_golden():
    """Golden-file тест из спеки §8. Первый запуск/обновление эталона:
    GOLDEN=1 python -m pytest tests/test_render.py -v"""
    import os
    from pathlib import Path

    _code, out = run_cli([str(SLOP), "--lang", "en"])
    golden = Path(__file__).parent / "golden" / "slop_project_en.txt"
    if golden.exists():
        assert out == golden.read_text()
    elif os.environ.get("GOLDEN"):
        golden.parent.mkdir(exist_ok=True)
        golden.write_text(out)
    else:
        raise AssertionError("golden file missing; regenerate with GOLDEN=1")
```

- [ ] **Step 6: Обновить app-level тесты в `tests/test_e2e.py`**

Заменить обращения к легаси-полям на новые:

```python
def test_run_reports_md_and_comment_metrics(tmp_path):
    from slopcount.app import Options, run

    (tmp_path / "a.py").write_text("x = 1\ny = 2  # trailing\n")
    (tmp_path / "doc.md").write_text("# t\n\ntext\n")
    (tmp_path / "spec.rst").write_text("rst docs\n")
    report = run(Options(paths=[str(tmp_path)]))
    v = report.volume
    assert v.md_files == 1  # .rst не считается
    assert v.md_lines == 3
    assert abs(v.md_sloc_ratio - 1.5) < 1e-9
    assert v.comment_lines == 0
    assert abs(v.comment_sloc_ratio - 0.0) < 1e-9
    assert v.md_words == 2  # "# t" + "text"


def test_run_docs_only_repo_inf_md_ratio(tmp_path):
    from slopcount.app import Options, run

    (tmp_path / "ONLY.md").write_text("just text\n")
    report = run(Options(paths=[str(tmp_path)]))
    assert report.volume.md_sloc_ratio == float("inf")


def test_run_counts_uppercase_md_extension(tmp_path):
    from slopcount.app import Options, run

    (tmp_path / "a.py").write_text("x = 1\n")
    (tmp_path / "README.MD").write_text("# head\nbody\n")
    report = run(Options(paths=[str(tmp_path)]))
    assert report.volume.md_files == 1
    assert report.volume.md_lines == 2
```

Добавить тест языковой разбивки и md_words:

```python
def test_volume_languages_breakdown(tmp_path):
    from slopcount.app import Options, run

    (tmp_path / "a.py").write_text("x = 1\n")
    (tmp_path / "b.c").write_text("int b() { return 42; }\n")
    report = run(Options(paths=[str(tmp_path)]))
    langs = {row.language: row for row in report.volume.languages}
    assert langs["Python"].sloc == 1 and langs["Python"].files == 1
    assert langs["C"].sloc == 1
```

- [ ] **Step 7: Run full suite + линтер**

Run: `.venv/bin/python -m pytest tests/ -q && .venv/bin/ruff check . && .venv/bin/ruff format --check .`
Expected: PASS; `grep -rn "slop_ratio\b" src` не находит легаси-полей (только `safe_ratio`/`md_sloc_ratio`/`comment_sloc_ratio`/`slop_ratio=` kwargs)

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat!: JSON/CSV схемы 0.5.0 (volume/slop/comprehension/costs+breakdown); легаси-модель удалена"
```

---

### Task 8: Эмпирическая калибровка шкал comment/slop

**Files:**
- Modify: `src/slopcount/scales.py` (границы/тексты `_COMMENT`, `_SLOP`)
- Modify: `docs/superpowers/specs/2026-09-27-comprehension-redesign-design.md` (§7 таблица границ, §14 сводка)

- [ ] **Step 1: Снять цифры с эталонных репозиториев**

```bash
mkdir -p /tmp/slopcount-cal && cd /tmp/slopcount-cal
for repo in "django/django" "pallets/flask" "psf/requests" "redis/redis" "sqlite/sqlite"; do
  name=$(basename "$repo")
  [ -d "$name" ] || git clone --depth 1 "https://github.com/$repo" "$name" 2>/dev/null || echo "SKIP $repo (offline?)"
done
for d in django flask requests redis sqlite; do
  [ -d "$d" ] && /stg/git/slopcount/.venv/bin/slopcount "/tmp/slopcount-cal/$d" --json 2>/dev/null | \
    /stg/git/slopcount/.venv/bin/python -c "import json,sys; r=json.load(sys.stdin); v=r['volume']; print('$d', 'doc=%.4f comment=%.4f slop=%.4f' % (v['md_sloc_ratio'], v['comment_sloc_ratio'], r['slop']['ratio']))"
done
/stg/git/slopcount/.venv/bin/slopcount /stg/git/naumen-smp-mcp --json 2>/dev/null | \
  /stg/git/slopcount/.venv/bin/python -c "import json,sys; r=json.load(sys.stdin); v=r['volume']; print('naumen-smp-mcp', 'doc=%.4f comment=%.4f slop=%.4f' % (v['md_sloc_ratio'], v['comment_sloc_ratio'], r['slop']['ratio']))"
```

Записать результаты (ожидаемо: чистые — comment 0.1–0.3, slop ≈ 0; docs-тяжёлые humane — doc до 0.34; naumen — comment 0.331, slop 0.0071).

- [ ] **Step 2: Установить границы в `scales.py`**

По разрывам между классами в снятых цифрах обновить `_COMMENT` и `_SLOP` (черновые значения — если данные не противоречат, оставить). Обновить комментарий над списками: убрать слово «черновые», вписать источник калибровки с датой.

- [ ] **Step 3: Обновить спеку**

В `docs/superpowers/specs/2026-09-27-comprehension-redesign-design.md` §7: в таблице заменить «черновик» на финальные границы с колонкой фактических значений эталонов; §14: заполнить «— (снять)» снятыми цифрами.

- [ ] **Step 4: Run tests**

Run: `.venv/bin/python -m pytest tests/test_scales.py tests/test_e2e.py -q`
Expected: PASS (тесты шкал структурные — границы проверяют сортировку/уникальность, а не конкретные значения)

- [ ] **Step 5: Commit**

```bash
git add src/slopcount/scales.py docs/superpowers/specs/2026-09-27-comprehension-redesign-design.md
git commit -m "calibrate: границы шкал comment/slop по эталонным репозиториям"
```

---

### Task 9: Версия 0.5.0, документация, финал

**Files:**
- Modify: `pyproject.toml` (version), `src/slopcount/__init__.py`, po-заголовок + `.mo`
- Modify: `CLAUDE.md`, `README.md`
- Modify: память `/home/echernyshev/.claude/projects/-stg-git-slopcount/memory/typer-migration-status.md`

- [ ] **Step 1: Версия**

`pyproject.toml`: `version = "0.4.0"` → `version = "0.5.0"`. `src/slopcount/__init__.py`: `__version__ = "0.4.0"` → `"0.5.0"`. В po: `"Project-Id-Version: slopcount 0.4.0\n"` → `0.5.0`, затем:

```bash
msgfmt --check -o src/slopcount/locale/ru/LC_MESSAGES/slopcount.mo \
  src/slopcount/locale/ru/LC_MESSAGES/slopcount.po
```

- [ ] **Step 2: CLAUDE.md**

В разделе «Архитектура» внести правки (существующие bullets про конвейер/SLOP/MD-SLOC заменить):

- конвейер: `scc (один subprocess) → volume (VolumeStats: языки/SLOC/комментарии/md) → detect (детекторы, Evidence[]) → aggregate_slop (SlopStats) → comprehension (SLOCOMO + разбивки costs.py) → render (3 секции)`;
- заменить bullet про **SLOP**/MD-SLOC block на: «**Три секции отчёта** (спека 2026-09-27-comprehension-redesign): Project Volume / Comprehension Effort & Cost / Detected Slop; три шкалы `scales.py` (doc/comment/slop) вместо вердикта; `--evidence` вместо `--details` (улики + текст строк); `--fail-above`/`--verdict-only` удалены»;
- заменить bullet про **`metrics/`**: «`metrics/slocomo.py`: ComprehensionStats — чтение доков (238 wpm × 2.3) + комментарии (строки × 6 слов) + код (200 SLOC/ч) + cognitive×0.5 мин (весь проект); `person_months = reading_hours/152 × (1+slop_ratio)`, всё per person + шкала команды 1/2/3/5/8/13/21; токены/окна/GPU — из LOCOMO (in+out). `metrics/costs.py`: разбивки стоимостей по корзинам docs/code/comments/data — COCOMO независимым пересчётом (2.4·K^1.05, drift-guard против estimatedCost scc), LOCOMO атрибуцией по долям Code-строк, SLOCOMO точной суммой. Комментарии и blank-строки scc в COCOMO не включает (меморандум в отчёте)»;
- в «Что это» — «стоимость его *осознания*» → «стоимость его *понимания* (comprehension)».

- [ ] **Step 3: README.md**

- заменить пример вывода на фактический (`sed -n` вывода `--evidence`-фрагмента не нужен — только базовый запуск):
  `.venv/bin/slopcount tests/fixtures/slop_project` → вставить вывод в пример;
- в списке изменений/фич добавить блок 0.5.0: «Отчёт из трёх секций (объём → понимание → детекция); SLOCOMO от объёма проекта (per person + шкала команды); разбивки COCOMO/LOCOMO/SLOCOMO по корзинам; три шкалы вместо вердикта; `--evidence` вместо `--details`; удалены `--fail-above`/`--verdict-only`; JSON schema: scan/volume/slop/comprehension/costs».

- [ ] **Step 4: Обновить память**

В `/home/echernyshev/.claude/projects/-stg-git-slopcount/memory/typer-migration-status.md` пункт 4 заменить фразу «НЕ реализована» на «реализована 2026-09-27 (HEAD <хэш финального коммита>)»; обновить строку `description` в frontmatter и `MEMORY.md`-строку.

- [ ] **Step 5: Финальная проверка**

```bash
.venv/bin/python -m pytest tests/ -q && .venv/bin/ruff check . && .venv/bin/ruff format --check .
.venv/bin/slopcount . | head -30   # самоскан: три секции на живом проекте
.venv/bin/slopcount /stg/git/naumen-smp-mcp | head -40
```

Expected: все тесты PASS; в самоскане видны три секции, у doc-шкалы — RECURSION (шутка самоскана сохранена).

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "docs: 0.5.0 — CLAUDE.md/README под comprehension-конвейер; версия поднята"
```

---

## Self-Review (выполнен при написании плана)

1. **Spec coverage:** §3 модель → Tasks 3/5/7; §4 фазы → Task 5; §5.1 формулы чтения → Task 4; §5.2 SLOCOMO/команда → Task 4; §5.4 drift → Tasks 2/5; §6 разбивки → Tasks 2/5/6; §7 шкалы+калибровка → Tasks 1/8; §8 макет → Task 6 (+golden); §9 флаги → Tasks 6/7; §10 JSON/CSV → Task 7; §11 i18n → Task 6 (+0.5.0 заголовок Task 9); §12 версия/breaking → Task 9; §13 тесты — в каждом task; §14 цифры → Task 8.
2. **Placeholders:** буквальных TBD нет; единственные «определяемые по данным» места — границы калибровки (Task 8) с явной процедурой и командами.
3. **Type consistency:** `ComprehensionStats` (Task 4) используется в `Report` (Tasks 3/7) и рендерах (Task 6); `CocomoSplit.total_person_months`/`buckets` согласованы между Tasks 2/6/7; переименование `slop_stats→slop` — один sed в Task 7; `_snippet` определён в Task 6 и импортируется csv в Task 7.

