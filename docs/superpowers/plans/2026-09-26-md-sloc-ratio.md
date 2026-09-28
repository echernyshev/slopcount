# MD/SLOC Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Вердикт и `--fail-above` считаются от новой метрики MD/SLOC (md-строки/SLOC, доля); информационная метрика `comment_sloc_ratio` в отчёте и JSON.

**Architecture:** Конвейер не меняется: `scanner → detectors → aggregate → render`. В `aggregate` добавляются два числовых входа (`md_lines`, `comment_lines`), `Report` несёт пять новых полей-долей, `verdict_for` меняет вход с процентов slop_ratio на долю md_sloc_ratio с перекалиброванной шкалой. Рендеры (text/json) и CLI-гейт переключаются на новые поля. CSV не трогается.

**Tech Stack:** Python 3.11, pytest, gettext (`.po`/`.mo` + msgfmt), typer.

**Спека:** `docs/superpowers/specs/2026-09-26-md-sloc-ratio-design.md`
**Ветка:** текущая `slopcount-design`. Команда тестов: `.venv/bin/python -m pytest`.

**Ключевые числа fixture `slop_project` после правки (Task 5):** md_files=2, md_lines=12, sloc=8 → md_sloc_ratio=1.5; comment_lines=12 → comment_sloc_ratio=1.5; SLOP=16 (было 13), slop_ratio=200.0%, вердикт RECURSION.

---

### Task 1: `count_sloc_and_comments()` — SLOC и комментарии одним проходом

**Files:**
- Modify: `src/slopcount/metrics/sloc.py`
- Test: `tests/test_sloc.py`

- [x] **Step 1: Write the failing test**

Добавить в конец `tests/test_sloc.py` (импорт в строке 1 менять не нужно —
добавь `count_sloc_and_comments` в существующий импорт):

```python
# меняет строку 1 на:
from slopcount.metrics.sloc import count_sloc, count_sloc_and_comments
```

```python
def test_count_sloc_and_comments_python():
    # docstring 3 строки + # comment 1 + trailing 1 = 5 комментарных
    assert count_sloc_and_comments(SRC, "python") == (2, 5)


def test_count_sloc_and_comments_c():
    assert count_sloc_and_comments("// c\nint x;\n\n/* multi\nline */\nint y;\n", "c") == (2, 3)


def test_count_sloc_and_comments_unknown_lang():
    # неизвестный язык: комментариев не знаем, все непустые — код
    assert count_sloc_and_comments("-- sql\nselect 1;\n", "sql") == (2, 0)
```

- [x] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_sloc.py -q`
Expected: FAIL — `ImportError: cannot import name 'count_sloc_and_comments'`

- [x] **Step 3: Write minimal implementation**

Полное новое содержимое `src/slopcount/metrics/sloc.py`:

```python
from __future__ import annotations

from slopcount.extractors import extract_comments


def count_sloc_and_comments(text: str, language: str) -> tuple[int, int]:
    """(SLOC, comment_lines) одним проходом extract_comments.

    SLOC: непустые строки, не являющиеся комментариями целиком
    (докстринги — комментарии). Ограничение сканера: строка «код +
    трейлинг-комментарий» тоже исключается — колонок у нас нет.
    comment_lines: количество физических строк внутри блоков
    (инвариант: блок занимает ровно len(lines) строк; пустые внутри
    блока считаются — консистентно с подсчётом md-строк). Для
    неизвестных extractor'у языков комментариев не знаем — 0."""
    lines = text.split("\n")
    comment_lines: set[int] = set()
    for block in extract_comments(text, language):
        comment_lines.update(range(block.start_line, block.start_line + len(block.lines)))
    n = sum(1 for i, line in enumerate(lines, 1) if line.strip() and i not in comment_lines)
    return n, len(comment_lines)


def count_sloc(text: str, language: str) -> int:
    return count_sloc_and_comments(text, language)[0]
```

- [x] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_sloc.py tests/test_extractors.py -q`
Expected: PASS (все)

- [x] **Step 5: Commit**

```bash
git add src/slopcount/metrics/sloc.py tests/test_sloc.py
git commit -m "feat: count_sloc_and_comments — SLOC и комментарии одним проходом"
```

---

### Task 2: Поля `Report` и параметры `aggregate()`

**Files:**
- Modify: `src/slopcount/evidence.py:47-105`
- Test: `tests/test_evidence.py`

- [x] **Step 1: Write the failing test**

Добавить в конец `tests/test_evidence.py`:

```python
def test_aggregate_md_and_comment_ratios():
    report = aggregate([], sloc=200, md_files=3, md_lines=30, comment_lines=100)
    assert report.md_files == 3
    assert report.md_lines == 30
    assert abs(report.md_sloc_ratio - 0.15) < 1e-9
    assert report.comment_lines == 100
    assert abs(report.comment_sloc_ratio - 0.5) < 1e-9


def test_aggregate_md_ratio_zero_sloc():
    assert aggregate([], sloc=0, md_files=1, md_lines=5).md_sloc_ratio == float("inf")
    assert aggregate([], sloc=0).md_sloc_ratio == 0.0
    assert aggregate([], sloc=0, comment_lines=7).comment_sloc_ratio == float("inf")


def test_aggregate_md_defaults_zero():
    report = aggregate([], sloc=100)
    assert (report.md_files, report.md_lines, report.md_sloc_ratio) == (0, 0, 0.0)
    assert (report.comment_lines, report.comment_sloc_ratio) == (0, 0.0)
```

- [x] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_evidence.py -q`
Expected: FAIL — `TypeError: aggregate() got an unexpected keyword argument 'md_files'`

- [x] **Step 3: Write minimal implementation**

В `src/slopcount/evidence.py` — dataclass `Report`, после строки
`infected_md_lines: int = 0` (строка 57) добавить:

```python
    md_files: int = 0
    md_lines: int = 0
    md_sloc_ratio: float = 0.0  # доля, не проценты; inf при sloc=0 и md>0
    comment_lines: int = 0
    comment_sloc_ratio: float = 0.0  # информационная, на вердикт не влияет
```

Внимание: новые поля идут до `history_commits` с дефолтом — порядок полей
с дефолтами не ломается, все ниже тоже имеют дефолты.

Сигнатуру `aggregate` (строка 64) привести к виду:

```python
def aggregate(
    evidences: list[Evidence],
    *,
    sloc: int,
    infected: list[tuple[str, int]] = (),
    history_commits: int | None = None,
    skip_count: int = 0,
    root: str = ".",
    md_files: int = 0,
    md_lines: int = 0,
    comment_lines: int = 0,
) -> Report:
```

Перед `return report` (после блока с `report.slop_ratio`, строки 101-104)
добавить:

```python
    report.md_files = md_files
    report.md_lines = md_lines
    report.comment_lines = comment_lines
    if sloc == 0:
        report.md_sloc_ratio = float("inf") if md_lines > 0 else 0.0
        report.comment_sloc_ratio = float("inf") if comment_lines > 0 else 0.0
    else:
        report.md_sloc_ratio = md_lines / sloc
        report.comment_sloc_ratio = comment_lines / sloc
```

- [x] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_evidence.py -q`
Expected: PASS (все, включая старые)

- [x] **Step 5: Commit**

```bash
git add src/slopcount/evidence.py tests/test_evidence.py
git commit -m "feat: поля MD/SLOC и comment_sloc_ratio в Report и aggregate"
```

---

### Task 3: Обвязка `app.py` — подсчёт md-строк и комментариев

**Files:**
- Modify: `src/slopcount/app.py:19,77-100`
- Test: `tests/test_e2e.py`

- [x] **Step 1: Write the failing test**

Добавить в конец `tests/test_e2e.py`:

```python
def test_run_reports_md_and_comment_metrics(tmp_path):
    from slopcount.app import Options, run

    (tmp_path / "a.py").write_text("x = 1\ny = 2  # trailing\n")
    (tmp_path / "doc.md").write_text("# t\n\ntext\n")
    (tmp_path / "spec.rst").write_text("rst docs\n")
    report = run(Options(paths=[str(tmp_path)]))
    assert report.md_files == 1  # .rst не считается
    assert report.md_lines == 3
    assert abs(report.md_sloc_ratio - 3.0) < 1e-9  # sloc=1 (y-строка целиком комментарий)
    assert report.comment_lines == 1
    assert abs(report.comment_sloc_ratio - 1.0) < 1e-9


def test_run_docs_only_repo_inf_md_ratio(tmp_path):
    from slopcount.app import Options, run

    (tmp_path / "ONLY.md").write_text("just text\n")
    report = run(Options(paths=[str(tmp_path)]))
    assert report.md_sloc_ratio == float("inf")
```

- [x] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_e2e.py::test_run_reports_md_and_comment_metrics -q`
Expected: FAIL — `assert 0 == 1` (md_files ещё не считается)

- [x] **Step 3: Write minimal implementation**

В `src/slopcount/app.py`:

1. Импорт (строка 19): `from slopcount.metrics.sloc import count_sloc` →
   `from slopcount.metrics.sloc import count_sloc_and_comments`

2. Инициализация счётчиков — после `skip = 0` (строка 78) добавить:

```python
    md_files = 0
    md_lines = 0
    comment_lines = 0
```

3. Блок кода-файла (строка 100) `sloc += count_sloc(text, sf.language or "")` заменить на:

```python
            s, c = count_sloc_and_comments(text, sf.language or "")
            sloc += s
            comment_lines += c
```

4. В ветке markdown (строки 113-119) — первой строкой ветки добавить:

```python
            if sf.path.endswith((".md", ".markdown")):
                md_files += 1
                mlines = text.split("\n")
                md_lines += len(mlines) - (1 if mlines and mlines[-1] == "" else 0)
```

(формула та же, что в `docs_bloat.detect` для total).

5. Вызов `aggregate` (строка 143) дополнить параметрами:

```python
    report = aggregate(
        evidences,
        sloc=sloc,
        infected=infected,
        skip_count=skip,
        root=str(root),
        history_commits=history_commits,
        md_files=md_files,
        md_lines=md_lines,
        comment_lines=comment_lines,
    )
```

- [x] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_e2e.py -q`
Expected: PASS (все)

- [x] **Step 5: Commit**

```bash
git add src/slopcount/app.py tests/test_e2e.py
git commit -m "feat: app считает md-строки (.md/.markdown) и комментарии, передаёт в aggregate"
```

---

### Task 4: Шкала вердикта от MD/SLOC

**Files:**
- Modify: `src/slopcount/verdicts.py`
- Test: `tests/test_verdicts.py` (полная замена)

- [x] **Step 1: Write the failing test**

Полное новое содержимое `tests/test_verdicts.py`:

```python
from slopcount.i18n import setup
from slopcount.verdicts import progress_bar, verdict_for


def test_scale_boundaries():
    assert verdict_for(0).code == "HUMAN"
    assert verdict_for(0.049).code == "HUMAN"
    assert verdict_for(0.05).code == "NEURO_CLOUD"
    assert verdict_for(0.349).code == "NEURO_CLOUD"
    assert verdict_for(0.35).code == "ESTABLISHED_SLOP"
    assert verdict_for(0.499).code == "ESTABLISHED_SLOP"
    assert verdict_for(0.50).code == "AGENT_SELF_SERVICE"
    assert verdict_for(0.749).code == "AGENT_SELF_SERVICE"
    assert verdict_for(0.75).code == "AGENT_OCCUPATION"
    assert verdict_for(0.999).code == "AGENT_OCCUPATION"
    assert verdict_for(1.0).code == "RECURSION"
    assert verdict_for(float("inf")).code == "RECURSION"


def test_texts_are_english_msgids():
    assert "slop" in verdict_for(0.4).text.lower()


def test_progress_bar():
    setup("en")  # в прогресс-баре локализованный процент — фиксируем en
    assert progress_bar(50.0, width=4) == "[██░░] 50.0%"


def test_progress_bar_edges():
    setup("en")
    assert progress_bar(float("inf")) == "[░░░░░░░░░░░░░░░░░░░░] inf%"
    assert progress_bar(150.0, width=4) == "[████] 150.0%"
    # вердикт-бар кормится долей MD/SLOC, умноженной на 100
    assert progress_bar(0.6 * 100, width=4) == "[██░░] 60.0%"
```

- [x] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_verdicts.py -q`
Expected: FAIL — `assert 'HUMAN' == 'NEURO_CLOUD'` (старая шкала в процентах)

- [x] **Step 3: Write minimal implementation**

Полное новое содержимое `src/slopcount/verdicts.py`:

```python
from __future__ import annotations

from dataclasses import dataclass

from slopcount.i18n import fmt_float


@dataclass(frozen=True)
class Verdict:
    code: str
    text: str  # английский msgid; переводится через _() при рендере


# Шкала откалибрована (спека 2026-09-26-md-sloc-ratio-design.md):
# HUMAN < 0.05 — классические эталоны (django 0.0005, flask 0.015);
# NEURO_CLOUD < 0.35 — потолок человеческого README (requests 0.34);
# RECURSION >= 1.0 — недетерминированного текста не меньше, чем кода.
_SCALE: list[tuple[float, Verdict]] = [
    (0.05, Verdict("HUMAN", "Almost human. Suspiciously clean. Where are you hiding the slop?")),
    (
        0.35,
        Verdict(
            "NEURO_CLOUD", "A light neuro-haze: the slop has arrived, but so far it does the dishes"
        ),
    ),
    (
        0.50,
        Verdict(
            "ESTABLISHED_SLOP", "The slop has settled in for good. More documentation than meaning"
        ),
    ),
    (
        0.75,
        Verdict("AGENT_SELF_SERVICE", "Repository on LLM self-service. Humans visit on weekends"),
    ),
    (1.00, Verdict("AGENT_OCCUPATION", "Agent occupation. Resistance is futile")),
]
_RECURSION = Verdict("RECURSION", "You ran slopcount inside slop. Recursion")


def verdict_for(md_sloc_ratio: float) -> Verdict:
    if md_sloc_ratio >= 1.0:
        return _RECURSION
    for bound, v in _SCALE:
        if md_sloc_ratio < bound:
            return v
    return _SCALE[-1][1]


def progress_bar(pct: float, width: int = 20) -> str:
    filled = 0 if pct != pct or pct == float("inf") else round(pct / 100 * width)
    filled = max(0, min(width, filled))
    return "[" + "█" * filled + "░" * (width - filled) + f"] {fmt_float(pct, 1)}%"
```

Примечание: рендеры пока ещё зовут `verdict_for(report.slop_ratio)` —
переключение в Task 6. Промежуточное состояние консистентно: slop-фикстура
(162.5%) и docs-only (inf) дают RECURSION и по старому входу.

- [x] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_verdicts.py tests/test_e2e.py -q`
Expected: PASS (все)

- [x] **Step 5: Commit**

```bash
git add src/slopcount/verdicts.py tests/test_verdicts.py
git commit -m "feat!: вердикт от MD/SLOC — пороги 0.05/0.35/0.50/0.75/1.0, RECURSION при >=1.0"
```

---

### Task 5: Fixtures — slop с запасом рекурсии, human без markdown

**Files:**
- Modify: `tests/fixtures/slop_project/README.md`
- Delete: `tests/fixtures/human_project/README.md`
- Modify: `tests/test_e2e.py:45-61` (два asserts `= 13`)
- Modify: `tests/golden/slop_project_en.txt` (регенерация)

- [x] **Step 1: Обновить fixture slop_project**

`tests/fixtures/slop_project/README.md` — полное новое содержимое (11 строк;
добавленные 4 строки нейтральны к каталогам фраз — проверено грепом):

```markdown
# Awesome Project 🚀

Great question! This README explains everything seamlessly.

## 🎯 Quick Start

It's important to note that this project is a robust solution.

see changelog for details
tested on one machine
good luck
```

Итог: md = 11 (README) + 1 (CLAUDE.md) = 12 строк, sloc = 8, md_sloc_ratio = 1.5.
SLOP: улик по-прежнему 7, infected = round(11 × 0.8) = 9 → SLOP = 16.

- [x] **Step 2: Удалить README у human_project**

```bash
git rm tests/fixtures/human_project/README.md
```

md = 0 → md_sloc_ratio = 0.0 → HUMAN. (Альтернатива «сократить README»
не проходит: даже 1 строка даёт 1/17 = 0.059 > 0.05.)

- [x] **Step 3: Обновить ожидания в test_e2e.py**

В `test_docs_category_in_output` (строка 51) и
`test_style_category_in_output` (строка 61): `assert "= 13" in out` →
`assert "= 16" in out`; комментарий `# total SLOP: 7 evidence lines + 6 infected` →
`# total SLOP: 7 evidence lines + 9 infected` (в обоих местах).

- [x] **Step 4: Регенерировать golden-файл**

```bash
GOLDEN=1 .venv/bin/python -m pytest tests/test_render.py::test_text_renderer_golden -q
```

Expected: 1 passed (golden перезаписан). Проверить глазами: SLOP=16,
Slop Ratio 200.0%, вердикт-строка «162.5%» → «200.0%» (пока от slop_ratio).

- [x] **Step 5: Прогнать suite**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: PASS (все; SLOCOMO-числа в golden обновились автоматически)

- [x] **Step 6: Commit**

```bash
git add tests/fixtures/slop_project/README.md tests/test_e2e.py tests/golden/slop_project_en.txt
git commit -m "test: slop-фикстура 12 md-строк (MD/SLOC 1.5), human — без markdown"
```

---

### Task 6: Рендер текста, вердикт от MD/SLOC, локализация

**Files:**
- Modify: `src/slopcount/render/text.py:49-52,87-89`
- Modify: `src/slopcount/locale/ru/LC_MESSAGES/slopcount.po`
- Modify: `src/slopcount/locale/ru/LC_MESSAGES/slopcount.mo` (msgfmt)
- Modify: `tests/test_e2e.py` (новые тесты)
- Modify: `tests/golden/slop_project_en.txt` (регенерация)

- [x] **Step 1: Write the failing test**

Добавить в конец `tests/test_e2e.py`:

```python
def test_md_sloc_lines_in_output():
    _code, out = run_cli([str(SLOP), "--lang", "en"])
    assert "Documentation-to-Code Ratio (MD/SLOC)" in out
    assert "= 1.500 (md: 2 files, 12 lines)" in out
    assert "Comments-to-Code Ratio (comment/SLOC)" in out


def test_ru_md_sloc_lines():
    _code, out = run_cli([str(SLOP), "--lang", "ru"])
    assert "Документация на код (MD/SLOC)" in out
    assert "Комментарии к коду (comment/SLOC)" in out
    assert "(md: 2 файла, 12 строк)" in out
```

- [x] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_e2e.py::test_md_sloc_lines_in_output -q`
Expected: FAIL — строка отсутствует в выводе

- [x] **Step 3: Реализовать рендер**

В `src/slopcount/render/text.py`:

1. После строки 51 (`Slop Ratio (SLOP/SLOC)`) добавить:

```python
out.append(
    f"{_('Documentation-to-Code Ratio (MD/SLOC)'):<55}"
    f" = {fmt_float(report.md_sloc_ratio, 3)}"
    f" (md: {ngettext('%d file', '%d files', report.md_files) % report.md_files},"
    f" {ngettext('%d line', '%d lines', report.md_lines) % report.md_lines})"
)
out.append(
    f"{_('Comments-to-Code Ratio (comment/SLOC)'):<55} = {fmt_float(report.comment_sloc_ratio, 3)}"
)
```

2. `render_verdict` (строки 87-89) заменить на:

```python
def render_verdict(report: Report) -> str:
    v = verdict_for(report.md_sloc_ratio)
    return f"{_('VERDICT:')} {progress_bar(report.md_sloc_ratio * 100)}  {_(v.text)}"
```

- [x] **Step 4: Локализация — добавить msgid в .po**

В конец `src/slopcount/locale/ru/LC_MESSAGES/slopcount.po` добавить:

```po

msgid "Documentation-to-Code Ratio (MD/SLOC)"
msgstr "Документация на код (MD/SLOC)"

msgid "Comments-to-Code Ratio (comment/SLOC)"
msgstr "Комментарии к коду (comment/SLOC)"

msgid "%d file"
msgid_plural "%d files"
msgstr[0] "%d файл"
msgstr[1] "%d файла"
msgstr[2] "%d файлов"

msgid "%d line"
msgid_plural "%d lines"
msgstr[0] "%d строка"
msgstr[1] "%d строки"
msgstr[2] "%d строк"
```

Перекомпилировать (обязательно — drift guard `test_i18n`):

```bash
msgfmt --check -o src/slopcount/locale/ru/LC_MESSAGES/slopcount.mo \
  src/slopcount/locale/ru/LC_MESSAGES/slopcount.po
```

- [x] **Step 5: Регенерировать golden-файл**

```bash
GOLDEN=1 .venv/bin/python -m pytest tests/test_render.py::test_text_renderer_golden -q
```

Проверить глазами новые строки эталона:

```
Slop Ratio (SLOP/SLOC)                                  = 200.0%
Documentation-to-Code Ratio (MD/SLOC)                   = 1.500 (md: 2 files, 12 lines)
Comments-to-Code Ratio (comment/SLOC)                   = 1.500
...
VERDICT: [████████████████████] 150.0%  You ran slopcount inside slop. Recursion
```

- [x] **Step 6: Прогнать suite**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: PASS (все, включая test_i18n и golden)

- [x] **Step 7: Commit**

```bash
git add src/slopcount/render/text.py src/slopcount/locale/ru/LC_MESSAGES/slopcount.po \
  src/slopcount/locale/ru/LC_MESSAGES/slopcount.mo tests/test_e2e.py \
  tests/golden/slop_project_en.txt
git commit -m "feat: строки MD/SLOC и comment/SLOC в отчёте; вердикт от MD/SLOC; ru-локализация"
```

---

### Task 7: JSON-ключи

**Files:**
- Modify: `src/slopcount/render/json_out.py`
- Test: `tests/test_render.py:9-37`

- [x] **Step 1: Write the failing test**

В `tests/test_render.py`:

1. Импорт (строка 6): `from test_e2e import SLOP, run_cli` →
   `from test_e2e import HUMAN, SLOP, run_cli`

2. В `test_json_output_stable_keys` — множество ключей (строки 12-23)
   дополнить пятью:

```python
    assert set(data) == {
        "sloc",
        "slop",
        "slop_ratio",
        "md_files",
        "md_lines",
        "md_sloc_ratio",
        "comment_lines",
        "comment_sloc_ratio",
        "skipped_files",
        "infected_md_lines",
        "history_commits",
        "categories",
        "evidence_count",
        "slocomo",
        "verdict",
    }
```

3. После блока с `data["verdict"]["code"]` (строки 25-32) добавить:

```python
    assert set(data["verdict"]) == {"code", "md_sloc_ratio"}
    assert data["md_files"] == 2
    assert data["md_lines"] == 12
    assert data["md_sloc_ratio"] == 1.5
    assert data["comment_lines"] == 12
    assert data["comment_sloc_ratio"] == 1.5
    assert data["verdict"]["code"] == "RECURSION"
    assert data["verdict"]["md_sloc_ratio"] == 1.5
```

4. Новый тест в конец файла:

```python
def test_json_human_fixture_zero_md():
    _code, out = run_cli([str(HUMAN), "--json", "--lang", "en"])
    data = json.loads(out)
    assert data["md_files"] == 0
    assert data["md_sloc_ratio"] == 0.0
    assert data["verdict"]["code"] == "HUMAN"
```

- [x] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_render.py::test_json_output_stable_keys -q`
Expected: FAIL — множества не совпадают (ключей ещё нет)

- [x] **Step 3: Реализовать**

В `src/slopcount/render/json_out.py`:

1. После импортов добавить хелпер:

```python
def _ratio4(x: float) -> float | None:
    return None if math.isinf(x) else round(x, 4)
```

2. `v = verdict_for(report.slop_ratio)` (строка 25) → `v = verdict_for(report.md_sloc_ratio)`

3. Строку 26 (`ratio = round(...)`) заменить на `ratio = _ratio4(report.slop_ratio)`

4. В словарь `json.dumps` после `"slop_ratio": ratio,` добавить:

```python
            "md_files": report.md_files,
            "md_lines": report.md_lines,
            "md_sloc_ratio": _ratio4(report.md_sloc_ratio),
            "comment_lines": report.comment_lines,
            "comment_sloc_ratio": _ratio4(report.comment_sloc_ratio),
```

5. `"verdict": {"code": v.code, "ratio": ratio}` →
   `"verdict": {"code": v.code, "md_sloc_ratio": _ratio4(report.md_sloc_ratio)}`

- [x] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_render.py -q`
Expected: PASS (все)

- [x] **Step 5: Commit**

```bash
git add src/slopcount/render/json_out.py tests/test_render.py
git commit -m "feat: JSON — md_files/md_lines/md_sloc_ratio/comment_lines/comment_sloc_ratio, verdict.md_sloc_ratio"
```

---

### Task 8: `--fail-above` на доле MD/SLOC

**Files:**
- Modify: `src/slopcount/cli.py:48-50,103-104`
- Test: `tests/test_cli.py:24-31`

- [x] **Step 1: Write the failing test**

В `tests/test_cli.py` заменить `test_fail_above_triggers_exit_1` и
`test_fail_below_ok`:

```python
def test_fail_above_triggers_exit_1():
    # MD/SLOC фикстуры = 1.5 > 1 → exit 1
    code, out = run_cli([str(SLOP), "--fail-above", "1", "--verdict-only", "--lang", "en"])
    assert code == 1 and out.startswith("VERDICT:")


def test_fail_below_ok():
    # 1.5 < 2 → exit 0
    code, _ = run_cli([str(SLOP), "--fail-above", "2", "--lang", "en"])
    assert code == 0
```

- [x] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_cli.py::test_fail_above_triggers_exit_1 -q`
Expected: FAIL — `assert 0 == 1` (гейт ещё на slop_ratio: 200% > 1 → тоже бы
сработал... если упал не так — проверь, что MD/SLOC уже в Report; гейт
меняется в Step 3 в любом случае)

Примечание: если тест неожиданно PASS (старый гейт на slop_ratio тоже даёт
exit 1 при `--fail-above 1`, т.к. 200 > 1) — это ожидаемо; инверсия видна на
`test_fail_below_ok` не сразу. Поэтому диагностический шаг: временно
поставить `--fail-above 1.2` — старый гейт (200 > 1.2) дал бы exit 1,
новый (1.5 > 1.2) тоже 1; а `--fail-above 1.7`: старый → 1, новый → 0.
Проверь руками после Step 3: `run_cli([str(SLOP), "--fail-above", "1.7"])`
должен стать 0.

- [x] **Step 3: Реализовать**

В `src/slopcount/cli.py`:

1. Опция (строки 48-50):

```python
fail_above: float | None = (
    typer.Option(
        None,
        "--fail-above",
        help="Exit 1 if MD/SLOC above (fraction: 0.5 = half as much text as code)",
    ),
)
```

2. Гейт (строки 103-104):

```python
    if fail_above is not None and report.md_sloc_ratio > fail_above:
        raise typer.Exit(code=1)
```

- [x] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_cli.py -q && .venv/bin/slopcount tests/fixtures/slop_project --fail-above 1.7 --verdict-only; echo "exit=$?"`
Expected: PASS; exit=0 (доказательство, что гейт на MD/SLOC, не на slop_ratio)

- [x] **Step 5: Commit**

```bash
git add src/slopcount/cli.py tests/test_cli.py
git commit -m "feat!: --fail-above на доле MD/SLOC (0.5 = половина текста от кода)"
```

---

### Task 9: Документация и версия 0.3.0

**Files:**
- Modify: `README.md:40-63` (скриншот, CI), новая секция после скриншота
- Modify: `CLAUDE.md` (раздел «Архитектура», после пункта про SLOP)
- Modify: `pyproject.toml:7`, `src/slopcount/__init__.py:1`

- [x] **Step 1: README — скриншот и CI**

В блоке скриншота (`## Скриншот вывода`, строки 44-58) привести к
актуальному выводу:

```
    Total Physical Source Lines of Code (SLOC)              = 8
    Total Suspicious Lines Of Prose (SLOP)                  = 16
    Slop Ratio (SLOP/SLOC)                                  = 200.0%
    Documentation-to-Code Ratio (MD/SLOC)                   = 1.500 (md: 2 files, 12 lines)
    Comments-to-Code Ratio (comment/SLOC)                   = 1.500
    ----------------------------------------------------------------------------
    ...
    VERDICT: [████████████████████] 150.0%  You ran slopcount inside slop. Recursion
```

(точные SLOCOMO-строки между `...` не менять). Пример CI-режима (строка 62):

```
    slopcount . --json --fail-above 0.5 || echo "too much slop"
```

- [x] **Step 2: README — новая секция**

После `## Скриншот вывода` (перед `## CI-режим`) вставить:

```markdown
## Метрика MD/SLOC и вердикт (0.3.0)

Вердикт считается не по детектированному слопу, а по объёму
недетерминированного текста: **MD/SLOC** = строки `.md`/`.markdown` /
строки кода. `.rst` не считается — это классическая Sphinx-эпоха
человеческих доков (flask с rst дал бы 1.44 — абсурд; без rst — 0.015).
Пороги откалиброваны замерами эталонных и агентских репо:

| Вердикт | MD/SLOC |
|---|---|
| HUMAN | < 0.05 |
| NEURO_CLOUD | < 0.35 |
| ESTABLISHED_SLOP | < 0.50 |
| AGENT_SELF_SERVICE | < 0.75 |
| AGENT_OCCUPATION | < 1.00 |
| RECURSION | >= 1.00 |

Ориентиры: django 0.0005, flask 0.015, requests 0.34 (человеческий
потолок README-усердия), sdd-example 1.06, naumen-vibes 2.9. Слепые
зоны: md-native проекты (презентации, заметки — честный RECURSION),
малые репо (шумно при < 100 строк кода).

`comment_sloc_ratio` (комментарии/SLOC) — информационная метрика
баланса прозы внутри кода, на вердикт не влияет.

Breaking (0.3.0): `--fail-above` принимает долю MD/SLOC, а не проценты
slop ratio; JSON-ключ `verdict.ratio` переименован в
`verdict.md_sloc_ratio`; добавлены ключи `md_files`, `md_lines`,
`md_sloc_ratio`, `comment_lines`, `comment_sloc_ratio`.
```

- [x] **Step 3: CLAUDE.md — пункт в архитектуру**

В разделе «Архитектура» после пункта про SLOP добавить:

```markdown
- **MD/SLOC** = md-строки (только `.md`/`.markdown`) / SLOC, доля —
  вердикт и `--fail-above` считаются от неё (шкала 0.05/0.35/0.50/0.75/1.0,
  калибровка — спека 2026-09-26-md-sloc-ratio). `comment_sloc_ratio`
  (комментарии/SLOC) — информационная, на вердикт не влияет.
```

- [x] **Step 4: Версия 0.3.0**

`pyproject.toml` строка 7: `version = "0.2.0"` → `version = "0.3.0"`.
`src/slopcount/__init__.py` строка 1: `__version__ = "0.2.0"` → `"0.3.0"`.

- [x] **Step 5: Полный прогон и линтер**

```bash
.venv/bin/python -m pytest tests/ -q
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/slopcount . --verdict-only --lang en
```

Expected: все тесты PASS; ruff чист; самоскан печатает вердикт RECURSION
(MD/SLOC ≈ 1.96).

- [x] **Step 6: Commit**

```bash
git add README.md CLAUDE.md pyproject.toml src/slopcount/__init__.py
git commit -m "docs: MD/SLOC в README и CLAUDE.md; версия 0.3.0 (breaking: fail-above, verdict-ключ)"
```

---

## Само-ревью плана (выполнено при написании)

1. **Покрытие спеки**: count_sloc_and_comments (T1) → Report/aggregate (T2)
   → app-обвязка с фильтром .md/.markdown (T3) → шкала вердикта (T4) →
   fixtures (T5) → text-рендер + вердикт + i18n + msgfmt (T6) → JSON (T7) →
   CLI-гейт (T8) → README/CLAUDE.md/версия (T9). CSV не трогается — задачи
   нет, по спеке. Все крайние случаи покрыты тестами T2/T3.
2. **Плейсхолдеры**: отсутствуют — каждый шаг содержит код или команду.
3. **Консистентность имён**: `count_sloc_and_comments`, `md_files`,
   `md_lines`, `md_sloc_ratio`, `comment_lines`, `comment_sloc_ratio`,
   `_ratio4` — одинаковы во всех задачах; сигнатура `aggregate` из T2
   совпадает с вызовом в T3.
