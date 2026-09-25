# slopcount Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Построить шуточную CLI-утилиту `slopcount`, детектирующую нейрослоп в проекте и оценивающую стоимость его осознания (SLOCOMO), по спеке `docs/superpowers/specs/2026-09-25-slopcount-design.md`.

**Architecture:** Конвейер «скрипт-дирижёр»: scanner обходит файлы → независимые детекторы возвращают объяснимые улики `Evidence` → агрегатор считает SLOP/SLOC → SLOCOMO конвертирует в человеко-месяцы и шутливые ресурсы → рендереры (text/json/csv) выводят пародию на sloccount. Ядро — только stdlib (правила в TOML через `tomllib`), опциональные extras: `[perplexity]`, `[treesitter]`. Локализация — GNU gettext (en — msgid по умолчанию, ru — каталог).

**Tech Stack:** Python 3.11+ (stdlib only в ядре), pytest, hatchling, gettext/msgfmt, TOML-правила.

**Вехи:** [M1] MVP (Tasks 1–10) · [M2] Полные детекторы (11–15) · [M3] SLOCOMO (16–18) · [M4] CI + i18n (19–21) · [M5] Extras (22–23) · [M6] Полировка (24–25)

---

## Общие договорённости (для всех задач)

- Окружение: `python3.11 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"` (создаётся в Task 1).
- Запуск тестов всегда: `python -m pytest <файл> -v` из корня репо.
- Все строки интерфейса — английские msgid, обёрнутые в `_()` / `ngettext()` из `slopcount.i18n`. Русский текст живёт только в `.po`-каталоге.
- Формат чисел — только через `fmt_int`/`fmt_float` из `slopcount.i18n`: детерминированный, зависит от языка UI, а не от системной локали (отклонение от спеки ради стабильных golden-тестов; правило то же: `1,234.56` en / `1 234,56` ru).
- Коммиты после каждой задачи; в конце — атрибуция `Co-Authored-By: Claude <noreply@anthropic.com>` (см. системные инструкции сессии).
- Все пути в задачах — от корня репо `/stg/git/slopcount`.

## File Structure (итоговая карта)

```
pyproject.toml                      # Task 1, 22, 23
.gitignore                          # Task 1
src/slopcount/__init__.py           # Task 1 (версия)
src/slopcount/cli.py                # Task 1 (--version), 10 (полный), 19, 20
src/slopcount/i18n.py               # Task 9, 21
src/slopcount/scanner.py            # Task 3
src/slopcount/extractors.py         # Task 4
src/slopcount/evidence.py           # Task 2, 15
src/slopcount/app.py                # Task 10, растёт в 11-15, 17-18, 22
src/slopcount/verdicts.py           # Task 8
src/slopcount/rules.py              # Task 6 (загрузчик TOML-правил)
src/slopcount/rules/phrases_en.toml # Task 6
src/slopcount/rules/phrases_ru.toml # Task 6
src/slopcount/rules/env_markers.toml# Task 13
src/slopcount/detectors/__init__.py # Task 7
src/slopcount/detectors/phrase.py   # Task 7
src/slopcount/detectors/docs_bloat.py   # Task 11
src/slopcount/detectors/code_style.py   # Task 12
src/slopcount/detectors/env_markers.py  # Task 13
src/slopcount/detectors/git_history.py  # Task 14
src/slopcount/detectors/perplexity.py   # Task 22
src/slopcount/download_model.py         # Task 22
src/slopcount/metrics/__init__.py      # Task 5
src/slopcount/metrics/sloc.py          # Task 5
src/slopcount/metrics/cognitive.py     # Task 16 (approx), 23 (treesitter)
src/slopcount/metrics/slocomo.py       # Task 17
src/slopcount/render/__init__.py       # Task 10
src/slopcount/render/text.py           # Task 10, 18
src/slopcount/render/json_out.py       # Task 19
src/slopcount/render/csv_out.py        # Task 19
src/slopcount/locale/ru/LC_MESSAGES/slopcount.po  # Task 21 (+ .mo рядом)
tests/test_cli.py                     # Task 1, 20
tests/test_evidence.py                # Task 2, 15
tests/test_scanner.py                 # Task 3
tests/test_extractors.py              # Task 4
tests/test_sloc.py                    # Task 5
tests/test_rules.py                   # Task 6
tests/test_phrase.py                  # Task 7
tests/test_verdicts.py                # Task 8
tests/test_i18n.py                    # Task 9, 21
tests/test_e2e.py                     # Task 10, 11-14, 18, 20, 24
tests/test_docs_bloat.py              # Task 11
tests/test_code_style.py              # Task 12
tests/test_env_markers.py             # Task 13
tests/test_git_history.py             # Task 14
tests/test_cognitive.py               # Task 16, 23
tests/test_slocomo.py                 # Task 17
tests/test_render.py                  # Task 19
tests/test_perplexity.py              # Task 22
tests/fixtures/slop_project/...       # Task 10, пополняется в 11-14
tests/fixtures/human_project/...      # Task 24
README.md                             # Task 25
```

---

### Task 1 [M1]: Скелет проекта и CLI-каркас

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `src/slopcount/__init__.py`, `src/slopcount/cli.py`, `tests/test_cli.py`

- [x] **Step 1: Создать pyproject.toml**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "slopcount"
version = "0.1.0"
description = "Count the AI slop in your project and the cost of comprehending it. A loving sloccount parody."
readme = "README.md"
requires-python = ">=3.11"
license = "MIT"
authors = [{ name = "Egor Chernyshev" }]
classifiers = [
    "Programming Language :: Python :: 3.11",
    "Environment :: Console",
    "Topic :: Software Development",
]

[project.scripts]
slopcount = "slopcount.cli:main"

[project.optional-dependencies]
dev = ["pytest>=8"]
perplexity = ["transformers>=4.40", "torch>=2.2"]
treesitter = ["tree-sitter>=0.21", "tree-sitter-python>=0.21"]

[tool.hatch.build.targets.wheel]
packages = ["src/slopcount"]
```

`.gitignore`:

```
__pycache__/
*.pyc
.venv/
.pytest_cache/
dist/
*.egg-info/
```

`src/slopcount/__init__.py`:

```python
__version__ = "0.1.0"
```

- [x] **Step 2: Написать failing-тест CLI**

`tests/test_cli.py`:

```python
from slopcount.cli import main


def test_version_flag(capsys):
    from slopcount import __version__
    try:
        main(["--version"])
    except SystemExit as e:
        assert e.code == 0
    out = capsys.readouterr().out
    assert __version__ in out
```

- [x] **Step 3: Убедиться, что тест падает**

Run: `pip install -e ".[dev]" && python -m pytest tests/test_cli.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'slopcount.cli'`

- [x] **Step 4: Реализовать минимальный cli.py**

`src/slopcount/cli.py`:

```python
import argparse

from slopcount import __version__


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="slopcount",
        description="Count the AI slop in a project and the cost of comprehending it.",
    )
    p.add_argument("--version", action="version", version=f"slopcount {__version__}")
    return p


def main(argv=None) -> int:
    build_parser().parse_args(argv)
    return 0
```

- [x] **Step 5: Прогнать тест и закоммитить**

Run: `python -m pytest tests/test_cli.py -v` → PASS

```bash
git add pyproject.toml .gitignore src tests tests/test_cli.py
git commit -m "feat: project skeleton with versioned CLI entry point"
```

---

### Task 2 [M1]: Улики, категории, агрегатор

**Files:**
- Create: `src/slopcount/evidence.py`, `tests/test_evidence.py`

- [x] **Step 1: Failing-тест**

`tests/test_evidence.py`:

```python
from slopcount.evidence import Category, CategoryTotals, Evidence, Report, aggregate


def _ev(file, line, cat, weight):
    return Evidence(file=file, line=line, category=cat, weight=weight, description="d")


def test_aggregate_counts_unique_slop_lines_per_category():
    evs = [
        _ev("a.py", 1, Category.PROSE, 5),
        _ev("a.py", 1, Category.PROSE, 2),   # та же строка — не удваивает slop_lines
        _ev("a.py", 9, Category.PROSE, 5),
        _ev("b.py", 3, Category.STYLE, 1),
    ]
    report = aggregate(evs, sloc=100)
    assert report.categories[Category.PROSE].files == 1
    assert report.categories[Category.PROSE].slop_lines == 2
    assert report.categories[Category.PROSE].weight == 12
    assert report.categories[Category.STYLE].files == 1


def test_aggregate_slop_and_ratio_with_infected_md():
    evs = [_ev("README.md", 1, Category.DOCS, 5)]
    report = aggregate(evs, sloc=100, infected=[("SPEC.md", 40)])
    # 1 улика + round(40 * 0.8)
    assert report.slop == 33
    assert abs(report.slop_ratio - 33.0) < 1e-9


def test_cognitivity_grades():
    assert CategoryTotals(files=1, slop_lines=10, weight=40).cognitivity == "high"
    assert CategoryTotals(files=1, slop_lines=10, weight=20).cognitivity == "medium"
    assert CategoryTotals(files=1, slop_lines=10, weight=5).cognitivity == "low"
```

- [x] **Step 2: Run** `python -m pytest tests/test_evidence.py -v`
Expected: FAIL — `No module named 'slopcount.evidence'`

- [x] **Step 3: Реализация** `src/slopcount/evidence.py`:

```python
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum


class Category(str, Enum):
    PROSE = "prose"
    DOCS = "docs"
    STYLE = "style"
    AGENCY = "agency"
    HISTORY = "history"


@dataclass(frozen=True)
class Evidence:
    file: str          # путь относительно корня скана или "git:<sha8>" для коммитов
    line: int          # 1-based; 0 = файл-уровень
    category: Category
    weight: int
    description: str


@dataclass
class CategoryTotals:
    files: int = 0
    slop_lines: int = 0
    weight: int = 0

    @property
    def cognitivity(self) -> str:
        if self.slop_lines == 0:
            return "low"
        density = self.weight / self.slop_lines
        if density >= 3:
            return "high"
        if density >= 1.5:
            return "medium"
        return "low"


@dataclass
class Report:
    root: str
    sloc: int = 0
    skip_count: int = 0
    categories: dict[Category, CategoryTotals] = field(
        default_factory=lambda: {c: CategoryTotals() for c in Category}
    )
    slop: int = 0
    slop_ratio: float = 0.0
    infected_md_lines: int = 0
    history_commits: int | None = None
    details: list[Evidence] = field(default_factory=list)
    agency: list[Evidence] = field(default_factory=list)
    slocomo: "SlocomoResult | None" = None  # forward ref, модуль metrics.slocomo


def aggregate(
    evidences: list[Evidence],
    *,
    sloc: int,
    infected: list[tuple[str, int]] = (),
    history_commits: int | None = None,
    skip_count: int = 0,
    root: str = ".",
) -> Report:
    lines_per_cat: dict[Category, set[tuple[str, int]]] = defaultdict(set)
    files_per_cat: dict[Category, set[str]] = defaultdict(set)
    weight_per_cat: dict[Category, int] = defaultdict(int)
    for e in evidences:
        lines_per_cat[e.category].add((e.file, e.line))
        files_per_cat[e.category].add(e.file)
        weight_per_cat[e.category] += e.weight

    report = Report(root=root, sloc=sloc, history_commits=history_commits,
                    skip_count=skip_count, details=list(evidences),
                    agency=[e for e in evidences if e.category is Category.AGENCY])
    report.infected_md_lines = sum(round(n * 0.8) for _, n in infected)
    for cat in Category:
        totals = report.categories[cat]
        totals.files = len(files_per_cat[cat])
        totals.slop_lines = len(lines_per_cat[cat])
        totals.weight = weight_per_cat[cat]

    # SLOP: уникальные строки с уликами (agency не входит) + заражённые md-строки
    slop_lines = set()
    for cat in (Category.PROSE, Category.DOCS, Category.STYLE, Category.HISTORY):
        slop_lines |= lines_per_cat[cat]
    report.slop = len(slop_lines) + report.infected_md_lines
    if sloc == 0:
        report.slop_ratio = float("inf") if report.slop > 0 else 0.0
    else:
        report.slop_ratio = report.slop / sloc * 100
    return report
```

- [x] **Step 4: Run** `python -m pytest tests/test_evidence.py -v` → PASS
- [x] **Step 5: Commit**

```bash
git add src/slopcount/evidence.py tests/test_evidence.py
git commit -m "feat: evidence dataclass, categories and aggregation"
```

---

### Task 3 [M1]: Scanner — обход, gitignore, классификация

**Files:**
- Create: `src/slopcount/scanner.py`, `tests/test_scanner.py`

- [x] **Step 1: Failing-тест**

`tests/test_scanner.py`:

```python
from pathlib import Path

from slopcount.scanner import Gitignore, read_text, scan


def make(root: Path):
    (root / "src").mkdir()
    (root / "src" / "app.py").write_text("x = 1\n")
    (root / "main.c").write_text("int main(){}\n")
    (root / "README.md").write_text("# hi\n")
    (root / "notes.txt").write_text("hi\n")
    (root / "data.bin").write_bytes(b"\x00\x01\x02")
    (root / "node_modules").mkdir()
    (root / "node_modules" / "junk.js").write_text("var x;\n")
    (root / ".git").mkdir()
    (root / ".git" / "config").write_text("x\n")


def test_scan_classifies_and_skips(tmp_path):
    make(tmp_path)
    files = {f.path: f for f in scan(tmp_path)}
    assert set(files) == {"src/app.py", "main.c", "README.md", "notes.txt", "data.bin"}
    assert files["src/app.py"].kind == "code"
    assert files["src/app.py"].language == "python"
    assert files["main.c"].language == "c"
    assert files["README.md"].kind == "markdown"
    assert files["notes.txt"].kind == "prose"


def test_gitignore_excludes(tmp_path):
    make(tmp_path)
    (tmp_path / ".gitignore").write_text("*.bin\nsrc/\n")
    files = {f.path for f in scan(tmp_path)}
    assert "data.bin" not in files and "src/app.py" not in files
    assert "README.md" in files


def test_read_text_none_for_binary(tmp_path):
    make(tmp_path)
    assert read_text(tmp_path / "data.bin") is None
    assert read_text(tmp_path / "README.md") == "# hi\n"
```

- [x] **Step 2: Run** `python -m pytest tests/test_scanner.py -v`
Expected: FAIL — `No module named 'slopcount.scanner'`

- [x] **Step 3: Реализация** `src/slopcount/scanner.py`:

```python
from __future__ import annotations

import fnmatch
from dataclasses import dataclass
from pathlib import Path

SKIP_DIRS = {
    ".git", ".hg", ".svn", "node_modules", ".venv", "venv", "env",
    "__pycache__", "dist", "build", "target", ".tox", ".mypy_cache",
    ".pytest_cache", ".ruff_cache", ".idea", ".vscode", ".eggs", ".serena",
}

CODE_EXTS = {
    ".py": "python", ".js": "javascript", ".mjs": "javascript",
    ".cjs": "javascript", ".ts": "typescript", ".tsx": "typescript",
    ".jsx": "javascript", ".go": "go", ".rs": "rust", ".c": "c", ".h": "c",
    ".cpp": "cpp", ".cc": "cpp", ".hpp": "cpp", ".java": "java",
    ".rb": "ruby", ".sh": "sh", ".bash": "sh", ".zsh": "sh", ".php": "php",
    ".cs": "csharp", ".swift": "swift", ".kt": "kotlin", ".kts": "kotlin",
    ".scala": "scala",
}
PROSE_EXTS = {".md": "markdown", ".markdown": "markdown", ".rst": "markdown",
              ".txt": "prose"}


@dataclass(frozen=True)
class ScannedFile:
    path: str            # posix-путь относительно корня
    language: str | None
    kind: str            # "code" | "markdown" | "prose" | "other"
    size: int


class Gitignore:
    """Упрощённый .gitignore: пустые строки/#комментарии игнорируются,
    паттерны без '/' матчатся по имени, с '/' — по префиксу пути,
    поддерживаются glob-суффиксы fnmatch. Полной git-семантики нет — осознанно."""

    def __init__(self, root: Path):
        self.patterns: list[str] = []
        gi = root / ".gitignore"
        if gi.is_file():
            for raw in gi.read_text(encoding="utf-8", errors="replace").splitlines():
                line = raw.strip()
                if line and not line.startswith("!") and not line.startswith("#"):
                    self.patterns.append(line.rstrip("/"))

    def matches(self, relpath: str) -> bool:
        parts = Path(relpath).parts
        for pat in self.patterns:
            if "/" in pat:
                if fnmatch.fnmatch(relpath, f"*{pat}") or fnmatch.fnmatch(relpath, pat):
                    return True
            else:
                if any(fnmatch.fnmatch(p, pat) for p in parts):
                    return True
        return False


def scan(root: Path) -> list[ScannedFile]:
    ignore = Gitignore(root)
    out: list[ScannedFile] = []
    for dirpath, dirnames, filenames in os_walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            full = Path(dirpath) / name
            rel = full.relative_to(root).as_posix()
            if ignore.matches(rel):
                continue
            ext = full.suffix.lower()
            if ext in CODE_EXTS:
                kind, lang = "code", CODE_EXTS[ext]
            elif ext in PROSE_EXTS:
                kind, lang = PROSE_EXTS[ext], None
            else:
                kind, lang = "other", None
            out.append(ScannedFile(rel, lang, kind, full.stat().st_size))
    return sorted(out, key=lambda f: f.path)


def os_walk(root: Path):
    import os
    return os.walk(root)


def read_text(path: Path) -> str | None:
    """None для бинарных/нечитаемых файлов (счётчик skip)."""
    try:
        raw = path.read_bytes()
        if b"\0" in raw[:1024]:
            return None
        return raw.decode("utf-8")
    except (OSError, UnicodeDecodeError):
        return None
```

- [x] **Step 4: Run** `python -m pytest tests/test_scanner.py -v` → PASS
- [x] **Step 5: Commit**

```bash
git add src/slopcount/scanner.py tests/test_scanner.py
git commit -m "feat: file scanner with gitignore support and classification"
```

---

### Task 4 [M1]: Extractors — комментарии и докстринги

**Files:**
- Create: `src/slopcount/extractors.py`, `tests/test_extractors.py`

- [x] **Step 1: Failing-тест**

`tests/test_extractors.py`:

```python
from slopcount.extractors import extract_comments


PY = '''\
def f():
    """Does the thing.

    Great question! Let's delve into it.
    """
    x = 1  # Initialize the counter
# top-level comment
'''


def test_python_comments_and_docstrings():
    blocks = extract_comments(PY, "python")
    doc = [b for b in blocks if b.is_docstring]
    assert len(doc) == 1
    assert doc[0].start_line == 2
    assert any("Great question!" in line for b in doc for line in b.lines)
    inline = [(b.start_line, b.lines[0]) for b in blocks if not b.is_docstring]
    # физические номера строк файла (докстринг занимает строки 2-5)
    assert (6, "Initialize the counter") in inline
    assert (7, "top-level comment") in inline


C_LIKE = '''\
// setup the engine
int x = 1;
/* block
   of wisdom */
int y = 2;  // trailing note
'''


def test_c_style_comments():
    blocks = extract_comments(C_LIKE, "c")
    texts = [line for b in blocks for line in b.lines]
    assert "setup the engine" in texts
    assert "block" in texts and "of wisdom" in texts
    assert "trailing note" in texts


def test_unknown_language_returns_empty():
    assert extract_comments("whatever", "brainfuck") == []
```

- [x] **Step 2: Run** `python -m pytest tests/test_extractors.py -v` → FAIL (модуля нет)
- [x] **Step 3: Реализация** `src/slopcount/extractors.py`:

```python
from __future__ import annotations

import re
from dataclasses import dataclass

HASH_LANGS = {"python", "ruby", "sh"}
SLASH_LANGS = {"javascript", "typescript", "go", "rust", "c", "cpp",
               "java", "php", "csharp", "swift", "kotlin", "scala"}


@dataclass(frozen=True)
class CommentBlock:
    start_line: int
    lines: list[str]
    is_docstring: bool = False


def _clean(marker_len: int, text: str) -> str:
    s = text.strip()
    for tok in ("///", "//", "#", "/*", "*/", "*"):
        if s.startswith(tok):
            return s[len(tok):].strip()
    return s


def extract_comments(text: str, language: str) -> list[CommentBlock]:
    """Приближение: без полноценного лексера строк. Строковые литералы с
    маркерами внутри — редкий шум, принято осознанно (задокументировано)."""
    if language == "python":
        return _python(text)
    if language in HASH_LANGS:
        return _line_comments(text, "#")
    if language in SLASH_LANGS:
        return _slash(text)
    return []


def _line_comments(text: str, marker: str) -> list[CommentBlock]:
    out = []
    for i, line in enumerate(text.split("\n"), 1):
        if marker in line:
            out.append(CommentBlock(i, [_clean(1, line.split(marker, 1)[1].strip())]))
    return out


def _slash(text: str) -> list[CommentBlock]:
    out: list[CommentBlock] = []
    block: list[str] = []
    start = 0
    for i, line in enumerate(text.split("\n"), 1):
        stripped = line.strip()
        if block:
            if "*/" in stripped:
                block.append(stripped.split("*/", 1)[0].lstrip("*").strip())
                out.append(CommentBlock(start, [b for b in block if b]))
                block = []
            else:
                block.append(stripped.lstrip("*").strip())
            continue
        if stripped.startswith("/*"):
            start = i
            body = stripped[2:]
            if "*/" in body:
                out.append(CommentBlock(i, [body.split("*/", 1)[0].strip()]))
            else:
                block = [body.strip()]
        elif "//" in line:
            out.append(CommentBlock(i, [_clean(2, line.split("//", 1)[1].strip())]))
    return out


def _python(text: str) -> list[CommentBlock]:
    out: list[CommentBlock] = []
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if stripped.startswith(("#",)):
            out.append(CommentBlock(i + 1, [stripped.lstrip("#").strip()]))
            i += 1
            continue
        m = re.match(r'(?:[rbfu]*)(?:"""|\'\'\')(.*)$', stripped)
        if m:
            quote = '"""' if stripped.lstrip('"\'').startswith('"""') else "'''"
            quote = quote if quote in stripped else "'''"
            body = [m.group(1)]
            if m.group(1).rstrip().endswith(quote) and len(m.group(1).strip()) >= 3:
                out.append(CommentBlock(i + 1, [m.group(1).replace(quote, "").strip()], True))
                i += 1
                continue
            j = i + 1
            while j < len(lines):
                if quote in lines[j]:
                    body.append(lines[j].split(quote, 1)[0].strip())
                    break
                body.append(lines[j].strip())
                j += 1
            out.append(CommentBlock(i + 1, [b for b in body if b], True))
            i = j + 1
            continue
        if "#" in line:
            out.append(CommentBlock(i + 1, [line.split("#", 1)[1].strip()]))
        i += 1
    return out
```

- [x] **Step 4: Run** `python -m pytest tests/test_extractors.py -v` → PASS
- [x] **Step 5: Commit**

```bash
git add src/slopcount/extractors.py tests/test_extractors.py
git commit -m "feat: comment and docstring extraction per language family"
```

---

### Task 5 [M1]: Честный SLOC

**Files:**
- Create: `src/slopcount/metrics/__init__.py` (пустой), `src/slopcount/metrics/sloc.py`, `tests/test_sloc.py`

- [x] **Step 1: Failing-тест**

`tests/test_sloc.py`:

```python
from slopcount.metrics.sloc import count_sloc

SRC = '''\
def f():
    """docstring line
    another docstring line
    """
    # comment
    x = 1

    y = 2  # trailing comment: whole line excluded (no columns)
'''


def test_sloc_excludes_comments_blanks_docstrings():
    assert count_sloc(SRC, "python") == 2


def test_sloc_c_language():
    assert count_sloc("// c\nint x;\n\n/* multi\nline */\nint y;\n", "c") == 2
```

- [x] **Step 2: Run** `python -m pytest tests/test_sloc.py -v` → FAIL
- [x] **Step 3: Реализация** `src/slopcount/metrics/sloc.py`:

```python
from __future__ import annotations

from slopcount.extractors import extract_comments


def count_sloc(text: str, language: str) -> int:
    """Физический SLOC: непустые строки, не являющиеся комментариями
    целиком (докстринги — комментарии). Ограничение сканера: строка «код +
    трейлинг-комментарий» тоже исключается — колонок у нас нет."""
    lines = text.split("\n")
    comment_lines: set[int] = set()
    for block in extract_comments(text, language):
        # инвариант: блок занимает ровно len(lines) физических строк,
        # начиная со start_line (пустые строки НЕ фильтруются)
        comment_lines.update(range(block.start_line, block.start_line + len(block.lines)))
    n = 0
    for i, line in enumerate(lines, 1):
        if line.strip() and i not in comment_lines:
            n += 1
    return n
```

Примечание: точность подсчёта границ докстрингов — приближение; тесты фиксируют поведение.

- [x] **Step 4: Run** `python -m pytest tests/test_sloc.py tests/test_extractors.py -v` → PASS (регресс extractors не сломан)
- [x] **Step 5: Commit**

```bash
git add src/slopcount/metrics tests/test_sloc.py
git commit -m "feat: honest physical SLOC counter"
```

---

### Task 6 [M1]: TOML-каталоги фраз и загрузчик

**Files:**
- Create: `src/slopcount/rules.py`, `src/slopcount/rules/phrases_en.toml`, `src/slopcount/rules/phrases_ru.toml`, `tests/test_rules.py`

- [x] **Step 1: Каталоги** `src/slopcount/rules/phrases_en.toml`:

```toml
[[rule]]
pattern = 'Great question!'
weight = 5
description = "Classic LLM enthusiasm"

[[rule]]
pattern = '\bCertainly!'
weight = 5
description = "Eager assistant energy"

[[rule]]
pattern = 'As an AI language model'
weight = 5
description = "Self-identification"

[[rule]]
pattern = "It's not .{0,40}, it's"
weight = 3
description = "The 'not X but Y' rhetorical flip"

[[rule]]
pattern = "Here's a comprehensive"
weight = 3
description = "Comprehensive-guide opener"

[[rule]]
pattern = "let'?s delve (?:deep(?:er)? )?into"
weight = 2
description = "Delving, as promised"

[[rule]]
pattern = "It'?s important to note"
weight = 2
description = "Important note, noted"

[[rule]]
pattern = "In conclusion[,.]"
weight = 2
description = "Essay-style conclusion"

[[rule]]
pattern = "dive (?:deep|right) into"
weight = 2
description = "Diving deep"

[[rule]]
pattern = "seamlessly"
weight = 2
description = "Seamlessness worship"

[[rule]]
pattern = "robust solution"
weight = 2
description = "Robust solution boilerplate"
```

`src/slopcount/rules/phrases_ru.toml`:

```toml
[[rule]]
pattern = 'Отличный вопрос!'
weight = 5
description = "Classic LLM enthusiasm (ru)"

[[rule]]
pattern = '\bКонечно!'
weight = 5
description = "Eager assistant energy (ru)"

[[rule]]
pattern = 'Как ИИ,? я'
weight = 5
description = "Self-identification (ru)"

[[rule]]
pattern = 'Давайте рассмотрим'
weight = 3
description = "Let-us-consider opener (ru)"

[[rule]]
pattern = 'Важно отметить'
weight = 2
description = "Important note, noted (ru)"

[[rule]]
pattern = 'В заключение'
weight = 2
description = "Essay-style conclusion (ru)"

[[rule]]
pattern = 'Комплексное решение'
weight = 2
description = "Comprehensive solution boilerplate (ru)"
```

- [x] **Step 2: Failing-тест** `tests/test_rules.py`:

```python
from pathlib import Path

from slopcount.rules import load_rules


def test_builtin_rules_loaded_and_compiled():
    rules = load_rules()
    assert len(rules) >= 15
    hit = [r for r in rules if r.pattern.search("Great question! Let's see.")]
    assert hit and hit[0].weight == 5


def test_case_insensitive_and_user_extra(tmp_path):
    extra = tmp_path / "mine.toml"
    extra.write_text('[[rule]]\npattern = "ну давай уже"\nweight = 4\ndescription = "x"\n')
    rules = load_rules([extra])
    assert any(r.weight == 4 for r in rules if r.pattern.search("Ну давай уже"))
```

- [x] **Step 3: Run** `python -m pytest tests/test_rules.py -v` → FAIL
- [x] **Step 4: Реализация** `src/slopcount/rules.py`:

```python
from __future__ import annotations

import re
from dataclasses import dataclass
from importlib import resources
from pathlib import Path


@dataclass(frozen=True)
class PhraseRule:
    pattern: re.Pattern
    weight: int
    description: str


def load_rules(extra_paths: list[Path] | None = None) -> list[PhraseRule]:
    import sys
    import tomllib

    rules: list[PhraseRule] = []
    names = ["phrases_en.toml", "phrases_ru.toml"]
    base = resources.files("slopcount").joinpath("rules")
    import os
    paths = [Path(os.fspath(base / n)) for n in names] + list(extra_paths or [])
    for p in paths:
        if not p.is_file():
            print(f"slopcount: rules file not found, skipped: {p}", file=sys.stderr)
            continue
        data = tomllib.loads(p.read_text(encoding="utf-8"))
        for r in data.get("rule", []):
            rules.append(PhraseRule(
                pattern=re.compile(r["pattern"], re.IGNORECASE),
                weight=int(r.get("weight", 1)),
                description=r.get("description", ""),
            ))
    return rules
```

- [x] **Step 5: Run** `python -m pytest tests/test_rules.py -v` → PASS; commit:

```bash
git add src/slopcount/rules.py src/slopcount/rules tests/test_rules.py
git commit -m "feat: TOML phrase rule catalogs and loader"
```

---

### Task 7 [M1]: PhraseDetector

**Files:**
- Create: `src/slopcount/detectors/__init__.py` (пустой), `src/slopcount/detectors/phrase.py`, `tests/test_phrase.py`

- [x] **Step 1: Failing-тест** `tests/test_phrase.py`:

```python
from slopcount.detectors.phrase import PhraseDetector
from slopcount.evidence import Category
from slopcount.rules import load_rules
from slopcount.scanner import ScannedFile


def test_hits_in_python_comments():
    det = PhraseDetector(load_rules())
    sf = ScannedFile("a.py", "python", "code", 10)
    src = 'def f():\n    # Great question! But certainly! here\n    return 1\n'
    evs = det.detect(sf, src)
    assert len(evs) == 2
    assert all(e.category is Category.PROSE for e in evs)
    assert all(e.line == 2 for e in evs)
    assert {e.weight for e in evs} == {5}


def test_hits_in_markdown_lines():
    det = PhraseDetector(load_rules())
    sf = ScannedFile("README.md", None, "markdown", 10)
    evs = det.detect(sf, "intro\n\nIt's important to note that this rocks.\n")
    assert len(evs) == 1 and evs[0].line == 3 and evs[0].weight == 2


def test_no_hits_in_code_lines_without_comments():
    det = PhraseDetector(load_rules())
    sf = ScannedFile("a.py", "python", "code", 10)
    assert det.detect(sf, "msg = 'Great question!'\n") == []
```

- [x] **Step 2: Run** `python -m pytest tests/test_phrase.py -v` → FAIL
- [x] **Step 3: Реализация** `src/slopcount/detectors/phrase.py`:

```python
from __future__ import annotations

from slopcount.evidence import Category, Evidence
from slopcount.extractors import extract_comments
from slopcount.rules import PhraseRule
from slopcount.scanner import ScannedFile


class PhraseDetector:
    category = Category.PROSE

    def __init__(self, rules: list[PhraseRule]):
        self.rules = rules

    def detect(self, sf: ScannedFile, text: str) -> list[Evidence]:
        if sf.kind == "code":
            zones = [
                (b.start_line + k, line)
                for b in extract_comments(text, sf.language or "")
                for k, line in enumerate(b.lines)
            ]
        else:  # markdown / prose
            zones = list(enumerate(text.split("\n"), 1))
        out: list[Evidence] = []
        for line_no, line in zones:
            for r in self.rules:
                if r.pattern.search(line):
                    out.append(Evidence(sf.path, line_no, Category.PROSE,
                                        r.weight, r.description))
        return out
```

- [x] **Step 4: Run** `python -m pytest tests/test_phrase.py -v` → PASS
- [x] **Step 5: Commit**

```bash
git add src/slopcount/detectors tests/test_phrase.py
git commit -m "feat: phrase detector over comments and prose"
```

---

### Task 8 [M1]: Вердикты

**Files:**
- Create: `src/slopcount/verdicts.py`, `tests/test_verdicts.py`

- [x] **Step 1: Failing-тест** `tests/test_verdicts.py`:

```python
from slopcount.verdicts import progress_bar, verdict_for


def test_scale_boundaries():
    assert verdict_for(0).code == "HUMAN"
    assert verdict_for(10).code == "NEURO_CLOUD"
    assert verdict_for(24.9).code == "NEURO_CLOUD"
    assert verdict_for(25).code == "ESTABLISHED_SLOP"
    assert verdict_for(50).code == "AGENT_SELF_SERVICE"
    assert verdict_for(75).code == "AGENT_OCCUPATION"
    assert verdict_for(100.1).code == "RECURSION"
    assert verdict_for(float("inf")).code == "RECURSION"


def test_texts_are_english_msgids():
    assert "slop" in verdict_for(30).text.lower()


def test_progress_bar():
    assert progress_bar(50.0, width=4) == "[██░░] 50.0%"
```

- [x] **Step 2: Run** `python -m pytest tests/test_verdicts.py -v` → FAIL
- [x] **Step 3: Реализация** `src/slopcount/verdicts.py`:

```python
from __future__ import annotations

from dataclasses import dataclass


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
    return "[" + "█" * filled + "░" * (width - filled) + f"] {pct:.1f}%"
```

- [x] **Step 4: Run** `python -m pytest tests/test_verdicts.py -v` → PASS
- [x] **Step 5: Commit**

```bash
git add src/slopcount/verdicts.py tests/test_verdicts.py
git commit -m "feat: verdict scale and progress bar"
```

---

### Task 9 [M1]: i18n-каркас (gettext)

**Files:**
- Create: `src/slopcount/i18n.py`, `tests/test_i18n.py`

- [x] **Step 1: Failing-тест** `tests/test_i18n.py`:

```python
from slopcount.i18n import _, fmt_float, fmt_int, ngettext, setup


def test_default_is_english_identity():
    setup(None)
    assert _("Totals") == "Totals"          # каталога ru не выбрано — msgid
    assert fmt_int(12411) == "12,411"
    assert fmt_float(14.76) == "14.76"


def test_lang_argument_forces_language():
    setup("en")                              # en — всегда msgid
    assert fmt_int(1234567) == "1,234,567"
    setup("ru")
    assert fmt_int(1234567) == "1\u202f234\u202f567"
    assert fmt_float(14.76) == "14,76"


def test_ngettext_english_forms():
    setup("en")
    assert ngettext("%d cup", "%d cups", 1) % 1 == "1 cup"
    assert ngettext("%d cup", "%d cups", 5) % 5 == "5 cups"
```

Примечание: если ru-каталог ещё не скомпилирован (Task 21), `_()` при `setup("ru")` возвращает msgid — это корректный identity-фолбэк, тест на русский текст `_()` появится в Task 21.

- [x] **Step 2: Run** `python -m pytest tests/test_i18n.py -v` → FAIL
- [x] **Step 3: Реализация** `src/slopcount/i18n.py`:

```python
from __future__ import annotations

import gettext
import os
from importlib import resources

DOMAIN = "slopcount"

_translations = gettext.NullTranslations()
_lang = "en"

_THOUSANDS = {"en": ",", "ru": "\u202f"}   # неразрывный узкий пробел
_DECIMAL = {"en": ".", "ru": ","}


def detect_lang() -> str:
    """--lang > LANGUAGE > LC_ALL > LC_MESSAGES > LANG > en (первый токен)."""
    for var in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        val = os.environ.get(var, "")
        token = val.split(":", 1)[0].strip()
        if token and token not in ("C", "POSIX"):
            return token.split(".", 1)[0].split("_", 1)[0]
    return "en"


def setup(lang: str | None = None) -> None:
    """Вызывать ДО любой работы с _(). lang — значение --lang или None."""
    global _translations, _lang
    _lang = lang if lang else detect_lang()
    localedir = os.fspath(resources.files(DOMAIN).joinpath("locale"))
    try:
        _translations = gettext.translation(
            DOMAIN, localedir=localedir, languages=[_lang])
    except (FileNotFoundError, OSError):
        _translations = gettext.NullTranslations()


def _(msgid: str) -> str:
    return _translations.gettext(msgid)


def ngettext(singular: str, plural: str, n: int) -> str:
    return _translations.ngettext(singular, plural, n)


def current_lang() -> str:
    return _lang


def fmt_int(n: int) -> str:
    sep = _THOUSANDS.get(_lang, ",")
    grouped = f"{abs(n):,}".replace(",", "\x00")
    return ("-" if n < 0 else "") + grouped.replace("\x00", sep)


def fmt_float(x: float, ndigits: int = 2) -> str:
    s = f"{x:,.{ndigits}f}"
    if _lang == "ru":
        s = s.replace(",", "\x00").replace(".", ",").replace("\x00", "\u202f")
    return s
```

- [x] **Step 4: Run** `python -m pytest tests/test_i18n.py -v` → PASS
- [x] **Step 5: Commit**

```bash
git add src/slopcount/i18n.py tests/test_i18n.py
git commit -m "feat: gettext i18n scaffolding with deterministic number formatting"
```

---

### Task 10 [M1]: Текстовый рендерер + app-конвейер + CLI (MVP)

**Files:**
- Create: `src/slopcount/app.py`, `src/slopcount/render/__init__.py` (пустой), `src/slopcount/render/text.py`, `tests/fixtures/slop_project/README.md`, `tests/fixtures/slop_project/src/greeter.py`
- Modify: `src/slopcount/cli.py` (полная замена), `tests/test_cli.py` (дополнить)
- Test: `tests/test_e2e.py`

- [x] **Step 1: Fixture «слопный» проект**

`tests/fixtures/slop_project/README.md`:

```markdown
# Awesome Project 🚀

Great question! This README explains everything seamlessly.

## 🎯 Quick Start

It's important to note that this project is a robust solution.
```

`tests/fixtures/slop_project/src/greeter.py`:

```python
def greet(name):
    """Greets the user with a friendly greeting.

    Great question! Let's delve into how greetings work.
    """
    return f"Hello, {name}!"
```

- [x] **Step 2: Failing e2e-тест** `tests/test_e2e.py`:

```python
import io
import sys
from contextlib import redirect_stdout
from pathlib import Path

from slopcount.cli import main

FIXTURES = Path(__file__).parent / "fixtures"
SLOP = FIXTURES / "slop_project"


def run_cli(argv):
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = main(argv)
    return code, buf.getvalue()


def test_mvp_run_on_slop_fixture():
    code, out = run_cli([str(SLOP), "--lang", "en"])
    assert code == 0
    assert "Total Physical Source Lines of Code (SLOC)" in out
    assert "Total Suspicious Lines Of Prose (SLOP)" in out
    assert "Slop Ratio (SLOP/SLOC)" in out
    assert "VERDICT:" in out
    assert "Prose (comments/docstrings)" in out


def test_exit_zero_and_version_still_works():
    assert run_cli(["--version"])[0] == 0
```

- [x] **Step 3: Run** `python -m pytest tests/test_e2e.py -v` → FAIL (cli не знает путей)

- [x] **Step 4: Реализация**

`src/slopcount/app.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from slopcount.detectors.phrase import PhraseDetector
from slopcount.evidence import Evidence, Report, aggregate
from slopcount.metrics.sloc import count_sloc
from slopcount.rules import load_rules
from slopcount.scanner import ScannedFile, read_text, scan


@dataclass
class Options:
    paths: list[str] = field(default_factory=lambda: ["."])
    details: bool = False
    json_out: bool = False
    csv_out: bool = False
    history: int | None = None
    perplexity: bool = False
    rules: list[Path] = field(default_factory=list)
    lang: str | None = None
    personcost: float = 4690.50
    overhead: float = 2.4
    coffee_price: float = 4.0
    no_therapy: bool = False
    fail_above: float | None = None
    verdict_only: bool = False
    wide: bool = False


def flagged_words(text: str, evidences: list[Evidence]) -> int:
    lines = text.split("\n")
    uniq = {e.line for e in evidences if e.line > 0 and e.line <= len(lines)}
    return sum(len(lines[l - 1].split()) for l in uniq)


def run(opts: Options) -> Report:
    root = Path(opts.paths[0])
    phrase = PhraseDetector(load_rules(opts.rules))
    evidences: list[Evidence] = []
    sloc = 0
    skip = 0
    for sf in scan(root):
        if sf.kind not in ("code", "markdown", "prose"):
            continue
        text = read_text(root / sf.path)
        if text is None:
            skip += 1
            continue
        if sf.kind == "code":
            sloc += count_sloc(text, sf.language or "")
        evidences.extend(phrase.detect(sf, text))
    return aggregate(evidences, sloc=sloc, skip_count=skip, root=str(root))
```

`src/slopcount/render/text.py`:

```python
from __future__ import annotations

from slopcount import i18n
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
    w = i18n.current_lang
    out = []
    out.append(_("Totals grouped by slop origin (dominant slop source first):"))
    out.append("-" * 79)
    out.append(f"{_('Origin'):<28}{'files':>10}{'slop lines':>14}"
               f"{'slop %':>10}  {'cognitivity':<10}")
    out.append("-" * 79)
    ordered = sorted(
        [c for c in Category if c is not Category.AGENCY],
        key=lambda c: report.categories[c].slop_lines, reverse=True)
    label = _ROW_LABELS[Category.HISTORY]
    for cat in ordered:
        t = report.categories[cat]
        name = label if cat is Category.HISTORY else _(_ROW_LABELS[cat])
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
    return (f"{_('VERDICT:')} {progress_bar(report.slop_ratio)}  {_(v.text)}")
```

`src/slopcount/cli.py` (полная замена):

```python
from __future__ import annotations

import argparse
import sys

from slopcount import __version__, i18n
from slopcount.app import Options, run
from slopcount.render.text import render_text, render_verdict


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="slopcount",
        description="Count the AI slop in a project and the cost of comprehending it.")
    p.add_argument("--version", action="version", version=f"slopcount {__version__}")
    p.add_argument("paths", nargs="*", default=["."])
    p.add_argument("--details", action="store_true")
    p.add_argument("--json", dest="json_out", action="store_true")
    p.add_argument("--csv", dest="csv_out", action="store_true")
    p.add_argument("--history", nargs="?", const=500, type=int, default=None)
    p.add_argument("--perplexity", action="store_true")
    p.add_argument("--rules", action="append", type=Path_arg, default=[])
    p.add_argument("--lang", choices=["en", "ru"], default=None)
    p.add_argument("--personcost", type=float, default=4690.50)
    p.add_argument("--overhead", type=float, default=2.4)
    p.add_argument("--coffee-price", type=float, default=4.0)
    p.add_argument("--no-therapy", action="store_true")
    p.add_argument("--fail-above", type=float, default=None)
    p.add_argument("--verdict-only", action="store_true")
    p.add_argument("--wide", action="store_true")
    return p


def Path_arg(s: str):
    from pathlib import Path
    return Path(s)


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    i18n.setup(args.lang)
    opts = Options(
        paths=args.paths or ["."], details=args.details, json_out=args.json_out,
        csv_out=args.csv_out, history=args.history, perplexity=args.perplexity,
        rules=args.rules, lang=args.lang, personcost=args.personcost,
        overhead=args.overhead, coffee_price=args.coffee_price,
        no_therapy=args.no_therapy, fail_above=args.fail_above,
        verdict_only=args.verdict_only, wide=args.wide)
    report = run(opts)
    print(render_text(report))
    print(render_verdict(report))
    return 0
```

- [x] **Step 5: Run** `python -m pytest tests/test_e2e.py tests/test_cli.py -v` → PASS
- [x] **Step 6: Ручная проверка и коммит**

Run: `python -m slopcount.cli tests/fixtures/slop_project --lang en` (или `slopcount tests/...`)
Expected: таблица с SLOC/SLOP/VERDICT.

```bash
git add src/slopcount/app.py src/slopcount/render src/slopcount/cli.py tests
git commit -m "feat: MVP pipeline — scan, phrase detection, SLOC, text render, verdicts"
```

---

### Task 11 [M2]: docs_bloat_detector

**Files:**
- Create: `src/slopcount/detectors/docs_bloat.py`, `tests/test_docs_bloat.py`
- Modify: `src/slopcount/app.py` (вклинить детектор)

- [x] **Step 1: Failing-тест** `tests/test_docs_bloat.py`:

```python
from slopcount.detectors.docs_bloat import DocsBloatDetector
from slopcount.evidence import Category
from slopcount.scanner import ScannedFile


def make_sf(path, n_lines):
    return ScannedFile(path, None, "markdown", 0), "\n".join(f"line {i}" for i in range(n_lines)) + "\n"


def test_spec_giant_flagged():
    det = DocsBloatDetector()
    sf, text = make_sf("SPEC.md", 600)
    res = det.detect(sf, text)
    assert any(e.weight == 5 and "spec giant" in e.description for e in res.evidences)
    assert res.evidences[0].category is Category.DOCS


def test_infected_file_reported_when_density_high():
    det = DocsBloatDetector()
    text = "## 🚀 Header one\n## 🎯 Header two\nplain\nplain\n"
    sf = ScannedFile("README.md", None, "markdown", 0)
    res = det.detect(sf, text)
    assert res.infected == [("README.md", 4)]


def test_small_clean_file_not_infected():
    det = DocsBloatDetector()
    sf, text = make_sf("notes.md", 3)
    res = det.detect(sf, text)
    assert res.infected == [] and res.evidences == []


def test_repo_bloat_evidence():
    from slopcount.detectors.docs_bloat import repo_bloat_evidence
    files = [ScannedFile("big.md", None, "markdown", 300 * 1024)]
    ev = repo_bloat_evidence(files, sloc=1000)
    assert ev and ev.weight == 4 and "docs bloat" in ev.description
    assert repo_bloat_evidence(files, sloc=10_000) is None  # 30 КБ/КЛОК — норм
```

- [x] **Step 2: Run** `python -m pytest tests/test_docs_bloat.py -v` → FAIL
- [x] **Step 3: Реализация** `src/slopcount/detectors/docs_bloat.py`:

```python
from __future__ import annotations

import re
from dataclasses import dataclass

from slopcount.evidence import Category, Evidence
from slopcount.scanner import ScannedFile

_EMOJI_HEADER = re.compile(r"^#{1,6}\s.*[\U0001F300-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF]")
_EMOJI = re.compile(r"[\U0001F300-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\u2705\u2728]")


@dataclass(frozen=True)
class DocsBloatResult:
    evidences: list[Evidence]
    infected: list[tuple[str, int]]   # (путь, всего строк файла)


class DocsBloatDetector:
    category = Category.DOCS

    def detect(self, sf: ScannedFile, text: str) -> DocsBloatResult:
        lines = text.splitlines()
        ev: list[Evidence] = []
        weight = 0
        if len(lines) > 500:
            ev.append(Evidence(sf.path, 0, Category.DOCS, 5,
                               f"spec giant: {len(lines)} lines"))
            weight += 5
        for i, line in enumerate(lines, 1):
            if _EMOJI_HEADER.match(line):
                ev.append(Evidence(sf.path, i, Category.DOCS, 2,
                                   "emoji-decorated section header"))
                weight += 2
        infected: list[tuple[str, int]] = []
        if lines and weight / len(lines) > 0.1:
            infected.append((sf.path, len(lines)))
        return DocsBloatResult(ev, infected)


def repo_bloat_evidence(files: list[ScannedFile], sloc: int) -> Evidence | None:
    """Spec-to-Code Ratio из спеки §4.2: >100 КБ markdown на KLOC — тревога."""
    docs_bytes = sum(f.size for f in files if f.kind == "markdown")
    if sloc == 0:
        return None
    kb_per_kloc = docs_bytes / 1024 / (sloc / 1000)
    if kb_per_kloc > 100:
        return Evidence("<repo>", 0, Category.DOCS, 4,
                        f"docs bloat: {kb_per_kloc:.0f} KB of markdown per KLOC")
    return None
```

- [x] **Step 4: Run** `python -m pytest tests/test_docs_bloat.py -v` → PASS

- [x] **Step 5: Вклинить в app.run** — заменить цикл обработки markdown:

```python
        if sf.kind == "markdown":
            bloat = docs_bloat.detect(sf, text)
            evidences.extend(bloat.evidences)
            infected.extend(bloat.infected)
```

и инициализаторы перед циклом: `docs_bloat = DocsBloatDetector()`, `infected: list[tuple[str, int]] = []`; после цикла добавить repo-level улику: `rb = repo_bloat_evidence(files, sloc); if rb: evidences.append(rb)`; в финальном `aggregate(...)` передать `infected=infected`. Импорт: `from slopcount.detectors.docs_bloat import DocsBloatDetector, repo_bloat_evidence` (переменную `files = scan(root)` сохранить).

Дополнить e2e-тест (с фиксированными числами фикстуры — не безусловными ярлыками):

```python
def test_docs_category_in_output():
    import re
    code, out = run_cli([str(SLOP), "--lang", "en"])
    m = re.search(r"Markdown specs\s+\d+\s+(\d+)", out)
    assert m and int(m.group(1)) == 2          # DOCS slop lines from fixture
    assert "= 11" in out                       # total SLOP incl. 6 infected lines
```

ПРАВИЛО для Tasks 12–14: e2e-тесты вьюинга детекторов утверждают числа фикстуры, а не безусловно печатаемые ярлыки.

- [x] **Step 6: Run all** `python -m pytest -v` → PASS; commit:

```bash
git add src/slopcount/detectors/docs_bloat.py src/slopcount/app.py tests
git commit -m "feat: docs bloat detector with md infection tracking"
```

---

### Task 12 [M2]: code_style_detector

**Files:**
- Create: `src/slopcount/detectors/code_style.py`, `tests/test_code_style.py`
- Modify: `src/slopcount/app.py`

- [x] **Step 1: Failing-тест** `tests/test_code_style.py`:

```python
from slopcount.detectors.code_style import CodeStyleDetector
from slopcount.evidence import Category
from slopcount.scanner import ScannedFile

SF = ScannedFile("m.py", "python", "code", 0)


def test_trivial_docstring_flagged():
    det = CodeStyleDetector()
    evs = det.detect(SF, "def add(a, b):\n    '''Adds two numbers and returns the result.'''\n    return a + b\n")
    assert any(e.description == "trivial docstring on obvious function" for e in evs)
    assert all(e.category is Category.STYLE for e in evs)


def test_docstring_longer_than_body():
    det = CodeStyleDetector()
    src = "def f():\n    '''Line1\n    Line2\n    Line3\n    Line4\n    Line5\n    '''\n    return 1\n"
    evs = det.detect(SF, src)
    assert any("docstring longer than" in e.description for e in evs)


def test_catch_all_density():
    det = CodeStyleDetector()
    src = "\n".join(
        f"try:\n    f{d}()\nexcept Exception:\n    pass" for d in range(6)
    ) + "\nx = 1\n" * 40
    evs = det.detect(SF, src)
    assert sum(e.weight for e in evs if "catch-all" in e.description) >= 6


def test_emoji_in_comment():
    det = CodeStyleDetector()
    evs = det.detect(SF, "# 🎉 shipped it\nx = 1\n")
    assert any("emoji in code comment" in e.description for e in evs)


def test_clean_human_code_not_flagged():
    det = CodeStyleDetector()
    src = "/* parse args */\nint n = argc;\nfor (;;) {}\n"
    assert det.detect(ScannedFile("m.c", "c", "code", 0), src) == []


def test_docstring_perfection_flagged():
    det = CodeStyleDetector()
    funcs = []
    for i in range(6):
        funcs.append(
            f"def f{i}(x):\n    '''Does f{i}.\n\n    Args:\n        x: value\n\n    Returns:\n        result\n    '''\n    return x + {i}\n")
    evs = det.detect(SF, "".join(funcs))
    assert any("textbook-perfect docstrings" in e.description for e in evs)


def test_monotone_comments_flagged():
    det = CodeStyleDetector()
    body = "\n".join(f"def f{i}():\n    return {i}\n" for i in range(6))
    comments = "\n".join("# performs the computation step now" for _ in range(12))
    evs = det.detect(SF, comments + "\n" + body)
    assert any("monotone comment length" in e.description for e in evs)
```

- [x] **Step 2: Run** `python -m pytest tests/test_code_style.py -v` → FAIL
- [x] **Step 3: Реализация** `src/slopcount/detectors/code_style.py`:

```python
from __future__ import annotations

import re
from collections.abc import Callable

from slopcount.evidence import Category, Evidence
from slopcount.extractors import extract_comments
from slopcount.scanner import ScannedFile

_EMOJI = re.compile(r"[\U0001F300-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF]")
_TRIVIAL_DOC = re.compile(
    r"^(Adds?|Returns?|Gets?|Sets?|Creates?|Initiali[sz]es?|Updates?|Checks?)\b", re.I)
_CATCH_ALL = re.compile(
    r"except\s+(Exception|BaseException)|catch\s*\(\s*(e|err|error|Exception)")
_DEF = re.compile(r"^\s*(?:async\s+)?def\s+(\w+)|^\s*\w[\w\s\*&:<>,]*\s+\w+\s*\([^;]*\)\s*\{?\s*$")


class CodeStyleDetector:
    category = Category.STYLE

    def detect(self, sf: ScannedFile, text: str) -> list[Evidence]:
        checks: list[Callable[[ScannedFile, str], list[Evidence]]] = [
            self._docstrings, self._catch_all, self._emoji_comments,
            self._docstring_perfection, self._monotone_comments]
        out: list[Evidence] = []
        for check in checks:
            out.extend(check(sf, text))
        return out

    def _docstrings(self, sf, text) -> list[Evidence]:
        evs = []
        blocks = [b for b in extract_comments(text, sf.language or "") if b.is_docstring]
        code_lines = len([l for l in text.split("\n") if l.strip()])
        for b in blocks:
            n = len(b.lines)
            first = b.lines[0] if b.lines else ""
            if n <= 2 and _TRIVIAL_DOC.match(first):
                evs.append(Evidence(sf.path, b.start_line, Category.STYLE, 2,
                                    "trivial docstring on obvious function"))
            if code_lines and n / max(code_lines, 1) > 0.5 and n >= 5:
                evs.append(Evidence(sf.path, b.start_line, Category.STYLE, 2,
                                    f"docstring longer than body ({n} lines)"))
        return evs

    def _catch_all(self, sf, text) -> list[Evidence]:
        evs = []
        total = 0
        for i, line in enumerate(text.split("\n"), 1):
            if _CATCH_ALL.search(line):
                total += 1
                evs.append(Evidence(sf.path, i, Category.STYLE, 1,
                                    "catch-all exception swallowing"))
        if total >= 5:
            evs.append(Evidence(sf.path, 0, Category.STYLE, 2,
                                f"defensive catch-all density ({total})"))
        return evs

    def _emoji_comments(self, sf, text) -> list[Evidence]:
        evs = []
        for b in extract_comments(text, sf.language or ""):
            for k, line in enumerate(b.lines):
                if _EMOJI.search(line):
                    evs.append(Evidence(sf.path, b.start_line + k, Category.STYLE, 2,
                                        "emoji in code comment"))
        return evs

    _GOOGLE = re.compile(r"\b(Args|Parameters|Returns|Raises)\s*:", re.I)
    _DEF_LINE = re.compile(r"^\s*(?:async\s+)?def\s+\w+")

    def _docstring_perfection(self, sf, text) -> list[Evidence]:
        lines = text.split("\n")
        defs = [i for i, l in enumerate(lines, 1) if self._DEF_LINE.match(l)]
        if len(defs) < 5:
            return []
        doc_starts = {b.start_line for b in extract_comments(text, sf.language or "")
                      if b.is_docstring}
        perfect = sum(
            1 for d in defs
            if any(ds == d + 1 for ds in doc_starts)
            and any(self._GOOGLE.search(l) for l in lines[d:d + 15]))
        if perfect / len(defs) >= 0.8:
            return [Evidence(sf.path, 0, Category.STYLE, 2,
                             f"textbook-perfect docstrings on {perfect}/{len(defs)} functions")]
        return []

    def _monotone_comments(self, sf, text) -> list[Evidence]:
        lens = [len(line) for b in extract_comments(text, sf.language or "")
                for line in b.lines if line]
        if len(lens) < 10:
            return []
        mean = sum(lens) / len(lens)
        var = sum((x - mean) ** 2 for x in lens) / len(lens)
        if var < 25:
            return [Evidence(sf.path, 0, Category.STYLE, 2,
                             f"monotone comment length (var={var:.1f}) — machine cadence")]
        return []
```

- [x] **Step 4: Run** `python -m pytest tests/test_code_style.py -v` → PASS; вклинить в `app.run` по аналогии с Task 11 (для `sf.kind == "code"`: `evidences.extend(style_detector.detect(sf, text))`); прогнать `python -m pytest -v` → PASS
- [x] **Step 5: Commit**

```bash
git add src/slopcount/detectors/code_style.py src/slopcount/app.py tests
git commit -m "feat: code style stylometry detector"
```

---

### Task 13 [M2]: env_marker_detector

**Files:**
- Create: `src/slopcount/rules/env_markers.toml`, `src/slopcount/detectors/env_markers.py`, `tests/test_env_markers.py`
- Modify: `src/slopcount/app.py`

- [x] **Step 1: Каталог** `src/slopcount/rules/env_markers.toml`:

```toml
[[marker]]
path = ".claude"
weight = 3
description = "Claude Code lives here"

[[marker]]
path = "CLAUDE.md"
weight = 3
description = "CLAUDE.md agent instructions"

[[marker]]
path = "AGENTS.md"
weight = 3
description = "AGENTS.md agent instructions"

[[marker]]
path = ".cursor*"
weight = 3
description = "Cursor editor residue"

[[marker]]
path = ".aider*"
weight = 3
description = "aider residue"

[[marker]]
path = ".github/copilot-instructions.md"
weight = 3
description = "Copilot instructions"

[[marker]]
path = "GEMINI.md"
weight = 3
description = "Gemini agent instructions"

[[marker]]
path = ".windsurf*"
weight = 3
description = "Windsurf residue"

[[header]]
pattern = "Generated by (Claude|ChatGPT|Copilot|Gemini|Cursor|an AI)"
weight = 5
description = "generated-by header"
```

- [x] **Step 2: Failing-тест** `tests/test_env_markers.py`:

```python
from pathlib import Path

from slopcount.detectors.env_markers import EnvMarkerDetector
from slopcount.evidence import Category
from slopcount.scanner import read_text, scan


def test_presence_and_headers(tmp_path):
    (tmp_path / "CLAUDE.md").write_text("Be nice.\n")
    (tmp_path / ".claude").mkdir()
    (tmp_path / "gen.py").write_text("# Generated by Claude Code\nx = 1\n")
    det = EnvMarkerDetector()
    evs = det.detect(tmp_path, scan(tmp_path), lambda p: read_text(p))
    files = {e.file for e in evs}
    assert "CLAUDE.md" in files and ".claude" in files and "gen.py" in files
    gen = [e for e in evs if e.file == "gen.py"][0]
    assert gen.weight == 5 and gen.category is Category.AGENCY
```

- [x] **Step 3: Run** → FAIL; **Step 4: Реализация** `src/slopcount/detectors/env_markers.py`:

```python
from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass
from importlib import resources
from pathlib import Path

from slopcount.evidence import Category, Evidence
from slopcount.scanner import ScannedFile


@dataclass(frozen=True)
class _Header:
    pattern: re.Pattern
    weight: int
    description: str


def _load():
    import tomllib
    base = resources.files("slopcount").joinpath("rules/env_markers.toml")
    data = tomllib.loads(Path(str(base)).read_text(encoding="utf-8"))
    paths = [(m["path"], m["weight"], m["description"]) for m in data.get("marker", [])]
    headers = [_Header(re.compile(h["pattern"]), h["weight"], h["description"])
               for h in data.get("header", [])]
    return paths, headers


class EnvMarkerDetector:
    category = Category.AGENCY

    def __init__(self):
        self.paths, self.headers = _load()

    def detect(self, root: Path, scanned: list[ScannedFile], reader) -> list[Evidence]:
        evs: list[Evidence] = []
        names = [sf.path for sf in scanned] + _all_entries(root)
        for pat, weight, desc in self.paths:
            for name in names:
                if fnmatch.fnmatch(name, pat) or fnmatch.fnmatch(Path(name).name, pat):
                    evs.append(Evidence(name, 0, Category.AGENCY, weight, desc))
                    break
        for sf in scanned:
            if sf.kind == "other":
                continue
            text = reader(root / sf.path)
            if not text:
                continue
            for line in text.splitlines()[:5]:
                for h in self.headers:
                    if h.pattern.search(line):
                        evs.append(Evidence(sf.path, 1, Category.AGENCY,
                                            h.weight, h.description))
        return evs


def _all_entries(root: Path) -> list[str]:
    out = []
    for p in root.iterdir():
        out.append(p.name)
    return out
```

Вклинить в `app.run`: после файлового цикла `evidences.extend(EnvMarkerDetector().detect(root, files, read_text))` (сохранить `files = scan(root)` в переменную). `aggregate` уже относит AGENCY в `report.agency`.

- [x] **Step 5: Run all** → PASS; commit:

```bash
git add src/slopcount/rules/env_markers.toml src/slopcount/detectors/env_markers.py src/slopcount/app.py tests
git commit -m "feat: agent environment marker detector"
```

---

### Task 14 [M2]: git_history_detector

**Files:**
- Create: `src/slopcount/detectors/git_history.py`, `tests/test_git_history.py`
- Modify: `src/slopcount/app.py`, `tests/test_e2e.py`

- [ ] **Step 1: Failing-тест** `tests/test_git_history.py` (создаёт настоящий git-репо в tmp):

```python
import subprocess

import pytest

from slopcount.detectors.git_history import GitUnavailable, detect


def git(tmp_path, *args):
    subprocess.run(["git", "-C", str(tmp_path), *args], check=True,
                   capture_output=True, env={"GIT_AUTHOR_NAME": "T", "GIT_AUTHOR_EMAIL": "t@t",
                   "GIT_COMMITTER_NAME": "T", "GIT_COMMITTER_EMAIL": "t@t",
                   "GIT_AUTHOR_DATE": "2026-01-01T04:00:00",
                   "GIT_COMMITTER_DATE": "2026-01-01T04:00:00",
                   "PATH": "/usr/bin:/bin:/usr/local/bin", "HOME": str(tmp_path)})


@pytest.fixture
def repo(tmp_path):
    git(tmp_path, "init", "-q")
    (tmp_path / "a.txt").write_text("hello\n")
    git(tmp_path, "add", ".")
    git(tmp_path, "-c", "user.name=T", "-c", "user.email=t@t", "commit", "-q",
        "-m", "feat: add hello\n\nCo-Authored-By: Claude <noreply@anthropic.com>")
    return tmp_path


def test_detects_coauthor_and_night(repo):
    evs, n = detect(repo, 500)
    assert n == 1
    assert any("Co-Authored-By" in e.description for e in evs)
    assert any("night commit" in e.description for e in evs)


def test_not_a_repo_raises(tmp_path):
    with pytest.raises(GitUnavailable):
        detect(tmp_path, 500)
```

- [ ] **Step 2: Run** → FAIL
- [ ] **Step 3: Реализация** `src/slopcount/detectors/git_history.py`:

```python
from __future__ import annotations

import re
import subprocess
from datetime import datetime
from pathlib import Path

from slopcount.evidence import Category, Evidence

_REC = re.compile(r"^(\d+)\t(\d+)\t(.+)$")
_COAUTHOR = re.compile(r"Co-Authored-By:.*(?:Claude|Copilot|GPT|Gemini|aider)", re.I)
_GENERATED = re.compile(r"^Generated with (?:Claude Code|Cursor|Copilot|Gemini)", re.I | re.M)
_AIDER = re.compile(r"^(aider|🤖):?", re.I)
_EMOJI = re.compile(r"[\U0001F300-\U0001FAFF]")
_CONVENTIONAL = re.compile(
    r"^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)(\(.+\))?: .+")


class GitUnavailable(Exception):
    pass


def detect(root: Path, limit: int) -> tuple[list[Evidence], int]:
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "log", f"-{limit}", "--no-color",
             "--pretty=format:%x1e%H%x00%aI%x00%B", "--numstat"],
            capture_output=True, text=True, check=True, timeout=60).stdout
    except subprocess.CalledProcessError as exc:
        # пустой репозиторий: rc 1 от rev-parse --verify -q HEAD — это ок
        probe = subprocess.run(["git", "-C", str(root), "rev-parse", "--verify", "-q", "HEAD"],
                               capture_output=True)
        if probe.returncode == 1:
            return [], 0
        raise GitUnavailable(str(exc)) from exc
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        raise GitUnavailable(str(exc)) from exc

    evidences: list[Evidence] = []
    subjects: list[str] = []
    commits = [r for r in out.split("\x1e") if r.strip()]
    for record in commits:
        chunk = record.strip().split("\x00", 2)
        if len(chunk) < 3:
            continue
        sha, aiso, body = chunk[0].strip(), chunk[1], chunk[2]
        ref = f"git:{sha[:8]}"
        lines = body.splitlines()
        subject = lines[0].strip() if lines else ""
        subjects.append(subject)
        for i, line in enumerate(lines, 1):
            if _COAUTHOR.search(line):
                evidences.append(Evidence(ref, i, Category.HISTORY, 5,
                                          "Co-Authored-By an AI"))
        if _GENERATED.search(body):
            evidences.append(Evidence(ref, 1, Category.HISTORY, 5,
                                      "'Generated with' trailer"))
        if _AIDER.match(subject):
            evidences.append(Evidence(ref, 1, Category.HISTORY, 3, "aider prefix"))
        if _EMOJI.search(subject):
            evidences.append(Evidence(ref, 1, Category.HISTORY, 2,
                                      "emoji in commit subject"))
        hour = _hour(aiso)
        if hour is not None and hour <= 5:
            evidences.append(Evidence(ref, 1, Category.HISTORY, 1,
                                      f"night commit ({hour:02d}:00)"))
        changed = sum(int(m.group(1) or 0) + int(m.group(2) or 0)
                      for line in lines if (m := _REC.match(line.strip())))
        if changed > 2000:
            evidences.append(Evidence(ref, 0, Category.HISTORY, 3,
                                      f"machine velocity ({changed} lines)"))
    if len(subjects) >= 20 and all(_CONVENTIONAL.match(s) for s in subjects):
        evidences.append(Evidence("git:", 0, Category.HISTORY, 3,
                                  "100% conventional commits (humans get tired)"))
    return evidences, len(commits)


def _hour(aiso: str) -> int | None:
    try:
        return datetime.fromisoformat(aiso).hour
    except ValueError:
        return None
```

Вклинить в `app.run` (после env-маркеров):

```python
    if opts.history:
        from slopcount.detectors.git_history import GitUnavailable, detect as git_detect
        try:
            hist_evs, commits = git_detect(root, opts.history)
            evidences.extend(hist_evs)
            history_commits = commits
        except GitUnavailable:
            print("slopcount: git history unavailable; skipping archaeology",
                  file=sys.stderr)
```

с инициализатором `history_commits: int | None = None` и передачей в `aggregate(..., history_commits=history_commits)`; импорт `sys` наверху `app.py`.

Дополнить e2e (в `tests/test_e2e.py`; fixture-репозиторий без git → история недоступна, проверяем warn-free путь):

```python
def test_history_flag_on_git_repo(tmp_path):
    import subprocess
    env = {"PATH": "/usr/bin:/bin"}
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "x.md").write_text("# 🚀 doc\n")
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "-c", "user.name=T", "-c",
                    "user.email=t@t", "commit", "-q", "-m", "feat: x"],
                   check=True, env=env)
    code, out = run_cli([str(tmp_path), "--history", "10", "--lang", "en"])
    assert code == 0 and "Git history" in out
```

- [ ] **Step 4: Run all** `python -m pytest -v` → PASS
- [ ] **Step 5: Commit**

```bash
git add src/slopcount/detectors/git_history.py src/slopcount/app.py tests
git commit -m "feat: git history archaeology detector"
```

---

### Task 15 [M2]: SLOP-подсчёт финализирован (интеграция агрегации)

Агрегатор уже поддерживает `infected` (Task 2) и получает его с Task 11. Этот таск — интеграционный тест, фиксирующий сквозную формулу.

**Files:**
- Modify: `tests/test_evidence.py` (добавить кейс), `tests/test_e2e.py`

- [ ] **Step 1: Тест формулы на агрегаторе**

```python
def test_aggregate_full_slop_formula():
    evs = [
        _ev("a.py", 1, Category.PROSE, 5),
        _ev("a.py", 1, Category.STYLE, 2),      # разные категории на одной строке
        _ev("b.md", 4, Category.DOCS, 2),
        _ev("git:ab12cd34", 2, Category.HISTORY, 5),
        _ev(".claude", 0, Category.AGENCY, 3),  # не входит в SLOP
    ]
    report = aggregate(evs, sloc=50, infected=[("big.md", 100)])
    # уникальных строк с уликами: (a.py,1), (b.md,4), (git:...,2) = 3; md: round(100*.8)=80
    assert report.slop == 83
    assert abs(report.slop_ratio - 166.0) < 1e-9
```

- [ ] **Step 2: Run** `python -m pytest tests/test_evidence.py -v` → PASS (агрегатор уже корректен; тест — страховка от регресса)
- [ ] **Step 3: E2E-проверка RECURSION-вердикта**

```python
def test_recursion_verdict_on_pure_slop(tmp_path):
    (tmp_path / "ONLY_SLOP.md").write_text("Great question! " * 200)
    code, out = run_cli([str(tmp_path), "--lang", "en"])
    assert "Recursion" in out
```

- [ ] **Step 4: Run all** → PASS
- [ ] **Step 5: Commit**

```bash
git add tests
git commit -m "test: pin down full SLOP formula and recursion verdict"
```

---

### Task 16 [M3]: Когнитивная сложность (аппроксимация) и Halstead

**Files:**
- Create: `src/slopcount/metrics/cognitive.py`, `tests/test_cognitive.py`

- [ ] **Step 1: Failing-тест** `tests/test_cognitive.py`:

```python
from slopcount.metrics.cognitive import approx_cognitive_complexity, halstead_seconds


def test_flat_control_flow_scores_low():
    src = "if a:\n    pass\nif b:\n    pass\n"
    assert approx_cognitive_complexity(src, "python") == 2


def test_nesting_increases_score():
    flat = "if a:\n    pass\nif b:\n    pass\n"
    nested = "if a:\n    if b:\n        if c:\n            pass\n"
    assert approx_cognitive_complexity(nested, "python") > approx_cognitive_complexity(flat, "python")
    # 1 + (1+1) + (1+2) = 6
    assert approx_cognitive_complexity(nested, "python") == 6


def test_halstead_seconds_positive_and_monotone():
    small = halstead_seconds("x = 1\n")
    big = halstead_seconds("x = 1\ny = x + 2 * 3 - x / (1 + 2)\n")
    assert small > 0 and big > small
```

- [ ] **Step 2: Run** → FAIL
- [ ] **Step 3: Реализация** `src/slopcount/metrics/cognitive.py`:

```python
from __future__ import annotations

import math
import re

_NESTING = re.compile(
    r"\b(if|for|while|case|when|switch)\b|&&|\|\||\b(and|or)\b(?=\s)", re.I)
_FLAT = re.compile(r"\b(else|elif|catch|except)\b", re.I)


def _indent_unit(lines: list[str]) -> int:
    for line in lines:
        stripped = line.lstrip(" ")
        if stripped and len(line) != len(stripped):
            return len(line) - len(stripped)
    return 4


def approx_cognitive_complexity(text: str, language: str) -> int:
    """Аппроксимация Cognitive Complexity (Campbell 2018): каждое управляющее
    выражение +1 за уровень вложенности; else/catch/except — плоско +1.
    Помечается в выводе как 'approximate' (точный режим — treesitter, Task 23)."""
    lines = text.splitlines()
    unit = _indent_unit(lines)
    score = 0
    for line in lines:
        if not line.strip():
            continue
        nesting = (len(line) - len(line.lstrip(" "))) // unit
        score += len(_NESTING.findall(line)) * max(1, nesting)
        score += len(_FLAT.findall(line))
    return score


_IDENT = re.compile(r"[A-Za-z_]\w*")
_NUM = re.compile(r"\b\d+(?:\.\d+)?\b")
_MULTI_OPS = ["==", "!=", "<=", ">=", "->", "::", "+=", "-=", "*=", "/=",
              "**", "//", "&&", "||"]
_OPS_KEYWORDS = {"if", "for", "while", "return", "def", "class", "import",
                 "from", "function", "func", "fn", "switch", "case", "try"}


def halstead_seconds(text: str) -> float:
    """Halstead: V=N*log2(n), D=(n1/2)*(N2/n2), время = V*D/18 (секунды)."""
    rest = text
    n1: set[str] = set()
    N1 = 0
    for op in _MULTI_OPS:
        N1 += rest.count(op)
        if op in rest:
            n1.add(op)
        rest = rest.replace(op, " ")
    for tok in _IDENT.findall(rest):
        if tok.lower() in _OPS_KEYWORDS:
            n1.add(tok)
            N1 += 1
    ops_single = set("+-*/%=<>!&|^~")
    for ch in rest:
        if ch in ops_single:
            n1.add(ch)
            N1 += 1
    operands = _NUM.findall(rest) + [
        t for t in _IDENT.findall(rest) if t.lower() not in _OPS_KEYWORDS]
    n2 = set(operands)
    N2 = len(operands)
    n = len(n1) + len(n2)
    N = N1 + N2
    if n < 2 or N2 == 0 or len(n2) == 0 or len(n1) == 0:
        return 0.0
    V = N * math.log2(n)
    D = (len(n1) / 2) * (N2 / len(n2))
    return V * D / 18
```

- [ ] **Step 4: Run** `python -m pytest tests/test_cognitive.py -v` → PASS
- [ ] **Step 5: Commit**

```bash
git add src/slopcount/metrics/cognitive.py tests/test_cognitive.py
git commit -m "feat: approximate cognitive complexity and Halstead seconds"
```

---

### Task 17 [M3]: SLOCOMO

**Files:**
- Create: `src/slopcount/metrics/slocomo.py`, `tests/test_slocomo.py`
- Modify: `src/slopcount/app.py`, `src/slopcount/render/text.py`, `src/slopcount/evidence.py`

- [ ] **Step 1: Failing-тест** `tests/test_slocomo.py`:

```python
from slopcount.app import Options
from slopcount.metrics.slocomo import compute


def test_cocomo_parody_numbers():
    res = compute(slop=10_000, prose_words=23_800, cognitive_points=100,
                  halstead_secs=0.0, opts=Options())
    # KSLOP=10 → pm = 2.4*10**1.05 = 26.86...
    assert abs(res.person_months - 2.4 * 10 ** 1.05) < 1e-6
    assert abs(res.schedule_months - 2.5 * res.person_months ** 0.38) < 1e-6
    assert abs(res.therapists - res.person_months / res.schedule_months) < 1e-6
    assert abs(res.cost - res.person_months * 4690.50 * 2.4) < 1e-6
    # чтение: 23800 слов / 238 wpm / 60 * 2.3 = 3.83 часа; когниция: 100*0.5/60
    assert abs(res.reading_hours - (23_800 / 238 / 60 * 2.3 + 100 * 0.5 / 60)) < 1e-6
    assert res.coffee_cups == 4  # ceil(3.83+0.83=4.67/... ) — фиксируется формулой


def test_joke_conversions():
    res = compute(slop=1000, prose_words=20_000, cognitive_points=0,
                  halstead_secs=0.0, opts=Options())
    tokens = 20_000 * 1.3
    assert abs(res.context_windows_200k - tokens / 200_000) < 1e-9
    assert abs(res.gpu_hours - tokens / 100 / 3600) < 1e-9
    assert res.therapy_sessions == 2  # ceil(pm*2), pm маленький → 1*2=2? см. формулу


def test_no_therapy_flag():
    res = compute(slop=1000, prose_words=100, cognitive_points=0,
                  halstead_secs=0.0, opts=Options(no_therapy=True))
    assert res.therapy_sessions == 0 and res.therapy_cost == 0.0
```

Числа в тестах могут «поплыть» при реализации — исполнитель сверяет с формулами ниже и правит ожидания так, чтобы формулы оставались верными (тест фиксирует формулу, а не магию).

- [ ] **Step 2: Run** → FAIL
- [ ] **Step 3: Реализация** `src/slopcount/metrics/slocomo.py`:

```python
from __future__ import annotations

import math
from dataclasses import dataclass

from slopcount.app import Options

WPM = 238            # Brysbaert 2019
REREAD = 2.3         # коэффициент перечитывания от недоверия (шутка, помечена)
COG_MINUTES = 0.5    # 1 балл Cognitive Complexity ≈ полминуты
TOKENS_PER_WORD = 1.3
THERAPY_PRICE = 150.0


@dataclass(frozen=True)
class SlocomoResult:
    slop: int
    reading_hours: float
    person_months: float
    person_years: float
    schedule_months: float
    therapists: float
    cost: float
    context_windows_200k: float
    context_windows_1m: float
    gpu_hours: float
    coffee_cups: int
    coffee_cost: float
    therapy_sessions: int
    therapy_cost: float
    approximate: bool = True   # cognitive approximation mode


def compute(*, slop: int, prose_words: int, cognitive_points: int,
            halstead_secs: float, opts: Options,
            approximate: bool = True) -> SlocomoResult:
    reading = (prose_words / WPM / 60 * REREAD
               + cognitive_points * COG_MINUTES / 60
               + halstead_secs / 3600)
    kslop = slop / 1000
    pm = 2.4 * kslop ** 1.05
    months = 2.5 * pm ** 0.38
    tokens = prose_words * TOKENS_PER_WORD
    coffee = math.ceil(reading / 4)
    sessions = 0 if opts.no_therapy else max(1, math.ceil(pm * 2))
    return SlocomoResult(
        slop=slop, reading_hours=reading, person_months=pm, person_years=pm / 12,
        schedule_months=months, therapists=(pm / months) if months else 0.0,
        cost=pm * opts.personcost * opts.overhead,
        context_windows_200k=tokens / 200_000, context_windows_1m=tokens / 1_000_000,
        gpu_hours=tokens / 100 / 3600, coffee_cups=coffee,
        coffee_cost=coffee * opts.coffee_price,
        therapy_sessions=sessions,
        therapy_cost=sessions * THERAPY_PRICE,
        approximate=approximate)
```

- [ ] **Step 4: Run** `python -m pytest tests/test_slocomo.py -v` → PASS (при необходимости уточнить ожидания кофе/терапии по формуле — формулы неприкосновенны)

- [ ] **Step 5: Подключить к конвейеру**

В `app.run` накапливать входы: для файлов с ≥1 STYLE-уликой добавлять `approx_cognitive_complexity(text, lang)` и `halstead_seconds(text)`; `prose_words` — `flagged_words(...)` (уже есть) + для заражённых md `int(total_words * 0.8)`. В конце:

```python
    from slopcount.metrics.slocomo import compute as slocomo_compute
    report.slocomo = slocomo_compute(
        slop=report.slop, prose_words=prose_words, cognitive_points=cog_points,
        halstead_secs=hal_secs, opts=opts)
```

В `render/text.py` добавить блок SLOCOMO между Slop Ratio и VERDICT:

```python
def render_slocomo(report: Report) -> str:
    r = report.slocomo
    if r is None:
        return ""
    mode = " (approximate)" if r.approximate else ""
    lines = [
        "-" * 79,
        f"{_('Cognitive Awareness Effort, Person-Years (Person-Months)'):<46}"
        f" = {fmt_float(r.person_years)} ({fmt_float(r.person_months)}){mode}",
        _("(SLOCOMO model, Person-Months = 2.4 * (KSLOP**1.05))"),
        f"{_('Schedule of Despair, Years (Months)'):<46}"
        f" = {fmt_float(r.schedule_months / 12)} ({fmt_float(r.schedule_months)})",
        _("(SLOCOMO model, Months = 2.5 * (person-months**0.38))"),
        f"{_('Estimated Average Number of Therapists (Effort/Schedule)'):<46}"
        f" = {fmt_float(r.therapists)}",
        f"{_('Total Estimated Cost to Comprehend'):<46} = $ {fmt_float(r.cost)}",
        f"{_('Context Windows Consumed'):<46}"
        f" = {fmt_float(r.context_windows_200k)} × 200K / {fmt_float(r.context_windows_1m)} × 1M",
        f"{_('GPU-hours of Regret'):<46} = {fmt_float(r.gpu_hours)}",
        f"{_('Coffee Required'):<46}"
        f" = {fmt_int(r.coffee_cups)} ($ {fmt_float(r.coffee_cost)})",
    ]
    if r.therapy_sessions:
        lines.append(
            f"{_('Therapy Recommended'):<46}"
            f" = {fmt_int(r.therapy_sessions)} ($ {fmt_float(r.therapy_cost)})")
    return "\n".join(lines)
```

И вызвать из `render_text` перед verdict; в `cli.main` ничего не менять. Дополнить e2e:

```python
def test_slocomo_block_present():
    code, out = run_cli([str(SLOP), "--lang", "en"])
    assert "Cognitive Awareness Effort" in out
    assert "Total Estimated Cost to Comprehend" in out
    assert "GPU-hours of Regret" in out
```

- [ ] **Step 6: Run all** → PASS; commit:

```bash
git add src/slopcount/metrics/slocomo.py src/slopcount/app.py src/slopcount/render/text.py tests
git commit -m "feat: SLOCOMO cost-to-comprehend model with joke conversions"
```

---

### Task 18 [M3]: --details

**Files:**
- Modify: `src/slopcount/render/text.py`, `src/slopcount/cli.py`, `tests/test_e2e.py`

- [ ] **Step 1: Failing-тест**

```python
def test_details_lists_evidence():
    code, out = run_cli([str(SLOP), "--details", "--lang", "en"])
    assert "DETAILS" in out
    assert "greeter.py" in out
    assert "[prose]" in out and "+5" in out
```

- [ ] **Step 2: Run** → FAIL
- [ ] **Step 3: Реализация** — в `render/text.py`:

```python
def render_details(report: Report, limit: int = 50) -> str:
    out = [_("DETAILS (top evidence, most severe first):")]
    evs = sorted(report.details, key=lambda e: -e.weight)[:limit]
    for e in evs:
        out.append(f"{e.file}:{e.line}  [{e.category.value}]  {e.description} → +{e.weight}")
    return "\n".join(out)
```

В `cli.main` после `render_verdict`:

```python
    if args.details:
        print(render_details(report))
```

- [ ] **Step 4: Run all** → PASS
- **Step 5: Commit**

```bash
git add src/slopcount/render/text.py src/slopcount/cli.py tests
git commit -m "feat: --details evidence listing"
```

---

### Task 19 [M4]: JSON и CSV рендереры

**Files:**
- Create: `src/slopcount/render/json_out.py`, `src/slopcount/render/csv_out.py`, `tests/test_render.py`

- [ ] **Step 1: Failing-тест** `tests/test_render.py`:

```python
import csv
import io
import json

from tests.test_e2e import SLOP, run_cli


def test_json_output_stable_keys():
    code, out = run_cli([str(SLOP), "--json", "--lang", "en"])
    data = json.loads(out)
    assert {"sloc", "slop", "slop_ratio", "categories", "slocomo", "verdict"} <= set(data)
    assert set(data["categories"]) == {"prose", "docs", "style", "agency", "history"}
    assert data["verdict"]["code"] in {"HUMAN", "NEURO_CLOUD", "ESTABLISHED_SLOP",
                                       "AGENT_SELF_SERVICE", "AGENT_OCCUPATION", "RECURSION"}
    json.dumps(data)  # сериализуемо


def test_csv_rows():
    code, out = run_cli([str(SLOP), "--csv", "--lang", "en"])
    rows = list(csv.reader(io.StringIO(out)))
    assert rows[0] == ["file", "line", "category", "weight", "description"]
    assert any(r[3] == "5" for r in rows[1:])


def test_text_renderer_golden():
    """Golden-file тест из спеки §9. Первый запуск/обновление эталона:
    GOLDEN=1 python -m pytest tests/test_render.py -v"""
    from pathlib import Path
    code, out = run_cli([str(SLOP), "--lang", "en"])
    golden = Path(__file__).parent / "golden" / "slop_project_en.txt"
    import os
    if golden.exists():
        assert out == golden.read_text()
    elif os.environ.get("GOLDEN"):
        golden.parent.mkdir(exist_ok=True)
        golden.write_text(out)
    else:
        raise AssertionError("golden file missing; regenerate with GOLDEN=1")
```

- [ ] **Step 2: Run** → FAIL
- [ ] **Step 3: Реализация**

`src/slopcount/render/json_out.py`:

```python
from __future__ import annotations

import json

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
            "gpu_hours": round(report.slocomo.gpu_hours, 4),
            "coffee_cups": report.slocomo.coffee_cups,
            "approximate": report.slocomo.approximate,
        }
    v = verdict_for(report.slop_ratio)
    return json.dumps({
        "sloc": report.sloc,
        "slop": report.slop,
        "slop_ratio": round(report.slop_ratio, 2) if report.slop_ratio != float("inf") else None,
        "skipped_files": report.skip_count,
        "infected_md_lines": report.infected_md_lines,
        "history_commits": report.history_commits,
        "categories": {
            c.value: {"files": report.categories[c].files,
                      "slop_lines": report.categories[c].slop_lines,
                      "weight": report.categories[c].weight,
                      "cognitivity": report.categories[c].cognitivity}
            for c in Category},
        "evidence_count": len(report.details),
        "slocomo": sc,
        "verdict": {"code": v.code, "ratio": round(report.slop_ratio, 2)
                    if report.slop_ratio != float("inf") else None},
    }, indent=2)
```

`src/slopcount/render/csv_out.py`:

```python
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
```

В `cli.main` диспетчеризация вывода (заменить пару print-строк):

```python
    if args.json_out:
        print(render_json(report))
    elif args.csv_out:
        print(render_csv(report), end="")
    elif args.verdict_only:
        print(render_verdict(report))
    else:
        print(render_text(report))
        print(render_slocomo(report))
        print(render_verdict(report))
        if args.details:
            print(render_details(report))
```

- [ ] **Step 4: Run all** → PASS
- **Step 5: Commit**

```bash
git add src/slopcount/render tests
git commit -m "feat: JSON and CSV renderers with stable CI keys"
```

---

### Task 20 [M4]: --fail-above, --verdict-only, exit-коды

**Files:**
- Modify: `src/slopcount/cli.py`, `tests/test_cli.py`

- [ ] **Step 1: Failing-тесты**

```python
from tests.test_e2e import SLOP, run_cli


def test_fail_above_triggers_exit_1():
    code, out = run_cli([str(SLOP), "--fail-above", "5", "--verdict-only", "--lang", "en"])
    assert code == 1 and out.startswith("VERDICT:")


def test_fail_below_ok():
    code, _ = run_cli([str(SLOP), "--fail-above", "100", "--lang", "en"])
    assert code == 0


def test_runtime_error_exit_2(tmp_path):
    code, _ = run_cli([str(tmp_path / "nope"), "--lang", "en"])
    assert code == 2
```

- [ ] **Step 2: Run** → FAIL
- **Step 3: Реализация** — обернуть `main` в обработку:

```python
def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    i18n.setup(args.lang)
    opts = _opts_from(args)
    from pathlib import Path
    if not Path(opts.paths[0]).exists():
        print(f"slopcount: path not found: {opts.paths[0]}", file=sys.stderr)
        return 2
    report = run(opts)
    ...  # диспетчеризация вывода из Task 19
    if opts.fail_above is not None and report.slop_ratio > opts.fail_above:
        return 1
    return 0
```

- [ ] **Step 4: Run all** → PASS
- **Step 5: Commit**

```bash
git add src/slopcount/cli.py tests
git commit -m "feat: CI mode -- fail-above exit codes and verdict-only"
```

---

### Task 21 [M4]: Русская локализация

**Files:**
- Create: `src/slopcount/locale/ru/LC_MESSAGES/slopcount.po` (+ скомпилированный `.mo`)
- Modify: `pyproject.toml` (включить `.mo`/`.po` в пакет), `tests/test_i18n.py`

- [ ] **Step 1: Каталог** `src/slopcount/locale/ru/LC_MESSAGES/slopcount.po`:

```po
msgid ""
msgstr ""
"Project-Id-Version: slopcount 0.1.0\n"
"Language: ru\n"
"MIME-Version: 1.0\n"
"Content-Type: text/plain; charset=UTF-8\n"
"Content-Transfer-Encoding: 8bit\n"
"Plural-Forms: nplurals=3; plural=(n%10==1 && n%100!=11 ? 0 : n%10>=2 && "
"n%10<=4 && (n%100<10 || n%100>=20) ? 1 : 2);\n"

msgid "Totals grouped by slop origin (dominant slop source first):"
msgstr "Итоги по источникам слопа (доминирующий источник первым):"

msgid "Origin"
msgstr "Источник"

msgid "files"
msgstr "файлы"

msgid "slop lines"
msgstr "строки слопа"

msgid "slop %"
msgstr "слоп %"

msgid "cognitivity"
msgstr "когнитивность"

msgid "Markdown specs"
msgstr "Markdown-спеки"

msgid "Prose (comments/docstrings)"
msgstr "Проза (комментарии/докстринги)"

msgid "Code style"
msgstr "Стиль кода"

msgid "Git history"
msgstr "Git-история"

msgid "Environment markers"
msgstr "Маркеры окружения"

msgid "Total Physical Source Lines of Code (SLOC)"
msgstr "Всего физических строк кода (SLOC)"

msgid "Total Suspicious Lines Of Prose (SLOP)"
msgstr "Всего подозрительных строк прозы (SLOP)"

msgid "Slop Ratio (SLOP/SLOC)"
msgstr "Доля слопа (SLOP/SLOC)"

msgid "Cognitive Awareness Effort, Person-Years (Person-Months)"
msgstr "Усилие осознания, человеко-годы (человеко-месяцы)"

msgid "(SLOCOMO model, Person-Months = 2.4 * (KSLOP**1.05))"
msgstr "(Модель SLOCOMO, человеко-месяцы = 2.4 * (KSLOP**1.05))"

msgid "Schedule of Despair, Years (Months)"
msgstr "График отчаяния, годы (месяцы)"

msgid "(SLOCOMO model, Months = 2.5 * (person-months**0.38))"
msgstr "(Модель SLOCOMO, месяцы = 2.5 * (человеко-месяцы**0.38))"

msgid "Estimated Average Number of Therapists (Effort/Schedule)"
msgstr "Оценочное среднее число терапевтов (Усилие/График)"

msgid "Total Estimated Cost to Comprehend"
msgstr "Полная оценочная стоимость осознания"

msgid "Context Windows Consumed"
msgstr "Поглощено контекстных окон"

msgid "GPU-hours of Regret"
msgstr "GPU-часы сожаления"

msgid "Coffee Required"
msgstr "Требуется кофе"

msgid "Therapy Recommended"
msgstr "Рекомендована терапия"

msgid "VERDICT:"
msgstr "ВЕРДИКТ:"

msgid "DETAILS (top evidence, most severe first):"
msgstr "ДЕТАЛИ (главные улики, серьёзные первыми):"

msgid "Almost human. Suspiciously clean. Where are you hiding the slop?"
msgstr "Почти человек. Подозрительно чисто. Где вы прячете слоп?"

msgid "A light neuro-haze: the slop has arrived, but so far it does the dishes"
msgstr "Лёгкое нейро-облако: слоп уже завезли, но пока моет посуду"

msgid "The slop has settled in for good. More documentation than meaning"
msgstr "Слоп прочно прописался. Документации больше, чем смысла"

msgid "Repository on LLM self-service. Humans visit on weekends"
msgstr "Репозиторий на самообслуживании LLM. Люди здесь по выходным"

msgid "Agent occupation. Resistance is futile"
msgstr "Агентская оккупация. Сопротивление бесполезно"

msgid "You ran slopcount inside slop. Recursion"
msgstr "Вы запустили slopcount внутри слопа. Рекурсия"

msgid "%d cup"
msgid_plural "%d cups"
msgstr[0] "%d чашка"
msgstr[1] "%d чашки"
msgstr[2] "%d чашек"

msgid "%d session"
msgid_plural "%d sessions"
msgstr[0] "%d сессия"
msgstr[1] "%d сессии"
msgstr[2] "%d сессий"

msgid "slopcount: git history unavailable; skipping archaeology"
msgstr "slopcount: git-история недоступна; археологию пропускаем"

msgid "slopcount: path not found: {path}"
msgstr "slopcount: путь не найден: {path}"
```

- [ ] **Step 2: Компиляция и упаковка**

```bash
mkdir -p src/slopcount/locale/ru/LC_MESSAGES
msgfmt --check -o src/slopcount/locale/ru/LC_MESSAGES/slopcount.mo \
  src/slopcount/locale/ru/LC_MESSAGES/slopcount.po
```

В `pyproject.toml` добавить:

```toml
[tool.hatch.build.targets.wheel.force-include]
"src/slopcount/locale" = "slopcount/locale"
```

(hatchling и так пакует всё под `src/slopcount`; строка — страховка.)

- [ ] **Step 3: Failing-тесты** — добавить в `tests/test_i18n.py`:

```python
import shutil

import pytest


@pytest.mark.skipif(shutil.which("msgfmt") is None
                    and not __import__("pathlib").Path(
                        "src/slopcount/locale/ru/LC_MESSAGES/slopcount.mo").exists(),
                    reason="no compiled ru catalog")
def test_russian_translation_active():
    setup("ru")
    assert _("Slop Ratio (SLOP/SLOC)") == "Доля слопа (SLOP/SLOC)"


def test_russian_plurals():
    setup("ru")
    assert ngettext("%d cup", "%d cups", 1) % 1 == "1 чашка"
    assert ngettext("%d cup", "%d cups", 3) % 3 == "3 чашки"
    assert ngettext("%d cup", "%d cups", 5) % 5 == "5 чашек"
    assert ngettext("%d cup", "%d cups", 21) % 21 == "21 чашка"
```

- [ ] **Step 4: Run** `python -m pytest tests/test_i18n.py -v` → PASS; e2e на ru:

```python
def test_ru_output():
    code, out = run_cli([str(SLOP), "--lang", "ru"])
    assert "ВЕРДИКТ:" in out and "Доля слопа" in out
```

- [ ] **Step 5: Run all** `python -m pytest -v` → PASS; commit:

```bash
git add src/slopcount/locale pyproject.toml tests
git commit -m "feat: Russian locale with plural forms and localized render"
```

---

### Task 22 [M5]: extras [perplexity]

**Files:**
- Create: `src/slopcount/detectors/perplexity.py`, `src/slopcount/download_model.py`, `tests/test_perplexity.py`
- Modify: `src/slopcount/app.py`, `src/slopcount/cli.py`

- [ ] **Step 1: Failing-тест** (мок модели, transformers не нужен):

```python
import math

import pytest

from slopcount.detectors.perplexity import PerplexityDetector, available
from slopcount.evidence import Category
from slopcount.scanner import ScannedFile


class FakeTok:
    def __call__(self, text, return_tensors=None):
        return {"input_ids": [[1, 2, 3]]}


class FakeModel:
    def __call__(self, input_ids=None):
        class L:  # равномерные логиты → перплексия = vocab_size
            logits = [[[0.0] * 50 for _ in range(3)]]
        return L()


def test_available_false_without_extras():
    assert available() in (True, False)  # не падает на голом окружении


def test_smooth_text_flagged_with_fake_model():
    det = PerplexityDetector.__new__(PerplexityDetector)
    det._tok, det._model, det._max_ppl, det._max_burst = FakeTok(), FakeModel(), 35.0, 0.3
    det._ppls = lambda s: [math.log(50)] * len(s)
    sf = ScannedFile("doc.md", None, "markdown", 0)
    evs = det.detect(sf, "One smooth sentence. Another smooth sentence here now.")
    assert evs and all(e.category is Category.PROSE for e in evs)
    assert all(e.description.startswith("suspiciously smooth prose") for e in evs)
```

- [ ] **Step 2: Run** → FAIL
- **Step 3: Реализация** `src/slopcount/detectors/perplexity.py`:

```python
from __future__ import annotations

import math
from typing import Any

from slopcount.evidence import Category, Evidence
from slopcount.scanner import ScannedFile


def available() -> bool:
    try:
        import transformers  # noqa: F401
        import torch  # noqa: F401
        return True
    except ImportError:
        return False


class PerplexityDetector:
    """GPTZero-стиль: низкая средняя перплексия + низкий burstiness = слоп.
    Требует extras: pipx install 'slopcount[perplexity]'."""
    category = Category.PROSE

    def __init__(self, model_name: str = "gpt2"):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        self._torch = torch
        self._tok = AutoTokenizer.from_pretrained(model_name)
        self._model = AutoModelForCausalLM.from_pretrained(model_name)
        self._model.eval()
        self._max_ppl = 35.0
        self._max_burst = 0.3

    def _ppls(self, sentence: str) -> float:
        ids = self._tok(sentence, return_tensors="pt").input_ids
        with self._torch.no_grad():
            logits = self._model(ids).logits
        logp = self._torch.log_softmax(logits[:, :-1], dim=-1)
        tgt = ids[:, 1:]
        nll = self._torch.gather(logp, 2, tgt.unsqueeze(-1)).mean().item()
        return math.exp(nll)

    def detect(self, sf: ScannedFile, text: str) -> list[Evidence]:
        sentences = [s.strip() for s in text.replace("\n", " ").split(". ") if len(s.strip()) > 30]
        if len(sentences) < 3:
            return []
        ppls = [self._ppls(s) for s in sentences]
        mean = sum(ppls) / len(ppls)
        var = sum((p - mean) ** 2 for p in ppls) / len(ppls)
        burst = math.sqrt(var) / mean if mean else 0.0
        if mean >= self._max_ppl or burst >= self._max_burst:
            return []
        approx_line = 1
        return [Evidence(sf.path, approx_line, Category.PROSE, 2,
                         f"suspiciously smooth prose (ppl≈{mean:.0f}, burst≈{burst:.2f})")]
```

`src/slopcount/download_model.py`:

```python
def main() -> None:
    print("Downloading gpt2 (~500 MB) for --perplexity ...")
    from transformers import AutoModelForCausalLM, AutoTokenizer
    AutoTokenizer.from_pretrained("gpt2")
    AutoModelForCausalLM.from_pretrained("gpt2")
    print("Done. Re-run slopcount with --perplexity.")


if __name__ == "__main__":
    main()
```

В `app.run` (лениво, при `opts.perplexity`):

```python
    pplx = None
    if opts.perplexity:
        if not perplexity_available():
            raise SystemExit(
                "slopcount: --perplexity requires extras; "
                "pipx install 'slopcount[perplexity]' and "
                "python -m slopcount.download_model (exit 2)")
        pplx = PerplexityDetector()
```

и в цикле `evidences.extend(pplx.detect(sf, text))` для markdown/prose. В `cli.py` ловить `SystemExit` от `run` → `return 2`.

- [ ] **Step 4: Run** `python -m pytest tests/test_perplexity.py -v` → PASS (тест не требует extras)
- **Step 5: Commit**

```bash
git add src/slopcount/detectors/perplexity.py src/slopcount/download_model.py src/slopcount/app.py src/slopcount/cli.py tests
git commit -m "feat: optional perplexity detector behind [perplexity] extras"
```

---

### Task 23 [M5]: extras [treesitter] — точная когнитивная сложность

**Files:**
- Modify: `src/slopcount/metrics/cognitive.py`, `tests/test_cognitive.py`, `src/slopcount/app.py`

- [ ] **Step 1: Failing-тест** (пропускается без extras):

```python
import pytest

ts = pytest.importorskip("tree_sitter", reason="no [treesitter] extra")


def test_exact_mode_lowers_approximation_flag():
    from slopcount.metrics.cognitive import exact_available
    # smoke: функция существует и не падает; полный прогон только с extras
    assert exact_available() in (True, False)
```

- [ ] **Step 2: Run** → SKIP (без extras) / FAIL
- **Step 3: Реализация** — добавить в `cognitive.py`:

```python
def exact_available() -> bool:
    try:
        import tree_sitter  # noqa: F401
        import tree_sitter_python  # noqa: F401
        return True
    except ImportError:
        return False


_CONTROL_NODES = {"if_statement", "for_statement", "while_statement",
                  "switch_expression", "catch_clause", "conditional_expression",
                  "boolean_operator"}


def cognitive_complexity_tspython(text: str) -> int:
    import tree_sitter
    import tree_sitter_python as tsp

    lang = tree_sitter.Language(tsp.language())
    parser = tree_sitter.Parser(lang)
    tree = parser.parse(text.encode())

    score = 0

    def walk(node, nesting: int) -> None:
        nonlocal score
        for child in node.children:
            if child.type in _CONTROL_NODES:
                score += 1 + nesting
                walk(child, nesting + 1)
            elif child.type in {"else_clause", "elif_clause"}:
                score += 1
                walk(child, nesting)
            else:
                walk(child, nesting)

    walk(tree.root_node, 0)
    return score
```

В `app.py` при сборе `cog_points`: если `exact_available()` и язык python → `cognitive_complexity_tspython(text)`, иначе `approx_cognitive_complexity(...)`; в `slocomo.compute` передавать `approximate=not exact_available()` (только python-файлы точные; смешанный режим — `approximate=True` если хоть один файл посчитан приближённо).

- [ ] **Step 4: Run** `python -m pytest tests/test_cognitive.py -v` → PASS/SKIP
- **Step 5: Commit**

```bash
git add src/slopcount/metrics/cognitive.py src/slopcount/app.py tests
git commit -m "feat: exact treesitter cognitive complexity mode"
```

---

### Task 24 [M6]: Контроль чистоты и производительность

**Files:**
- Create: `tests/fixtures/human_project/src/args.c`, `tests/fixtures/human_project/src/util.py`, `tests/fixtures/human_project/README.md`
- Modify: `tests/test_e2e.py`

- [ ] **Step 1: «Человеческий» fixture**

`tests/fixtures/human_project/src/args.c` (стиль: terse-комментарии, никакой прозы):

```c
/* arg parsing, quick and dirty */
#include <stdio.h>

int main(int argc, char **argv)
{
	int i;
	for (i = 1; i < argc; i++) {
		if (argv[i][0] == '-')
			continue;
		puts(argv[i]);
	}
	return 0;
}
```

`tests/fixtures/human_project/src/util.py`:

```python
def clamp(v, lo, hi):
    if v < lo:
        return lo
    if v > hi:
        return hi
    return v
```

`tests/fixtures/human_project/README.md`:

```markdown
# util

small helpers, no warranty
```

- [ ] **Step 1b: Прогресс на stderr при tty (спека §8)** — в цикл `app.run`
  добавить (после `for sf in scan(root)`; счётчик `n` инкрементируется на
  каждый обработанный файл):

```python
        n += 1
        if sys.stderr.isatty() and n % 200 == 0:
            print(f"\rscanned {n}/{len(files)} files...", end="", file=sys.stderr)
```

и в конце цикла один `print(file=sys.stderr)` для перевода строки. В pytest
stderr не tty — вывода нет, детерминизм e2e не страдает.

- [ ] **Step 2: Failing-тесты** — в `tests/test_e2e.py`:

```python
import time

HUMAN = FIXTURES / "human_project"


def test_human_fixture_stays_clean():
    code, out = run_cli([str(HUMAN), "--lang", "en"])
    assert "Slop Ratio (SLOP/SLOC)" in out
    # фиксируем: человеческий код не параноится —ratio < 10%
    import re
    m = re.search(r"Slop Ratio \(SLOP/SLOC\)\s*=\s*([\d.]+)%", out)
    assert m and float(m.group(1)) < 10.0


def test_perf_smoke_2k_files(tmp_path):
    deep = tmp_path / "pkg"
    deep.mkdir()
    for i in range(2000):
        (deep / f"m{i}.py").write_text(f"def f{i}():\n    return {i}\n")
    t0 = time.monotonic()
    code, _ = run_cli([str(tmp_path), "--lang", "en"])
    assert code == 0 and time.monotonic() - t0 < 15
```

- [ ] **Step 3: Run** `python -m pytest tests/test_e2e.py -v`
Expected: PASS. Если чистота сломана (>10%) — это регресс детекторов: чинить детекторы, а не порог.

- [ ] **Step 4: Run all** `python -m pytest -v` → PASS
- **Step 5: Commit**

```bash
git add tests
git commit -m "test: human-code purity fixture and perf smoke"
```

---

### Task 25 [M6]: README и полировка упаковки

**Files:**
- Modify: `README.md`, `pyproject.toml`

- [ ] **Step 1: README.md** (полная замена):

```markdown
# slopcount

> SLOC — это то, за что ты заплатил. SLOP — это то, что ты теперь обязан прочитать.

`slopcount` сканирует проект, находит LLM-нейрослоп и считает, сколько будет
стоить его **осознать** — честная пародия на классический `sloccount`
Дэвида Уилера, где COCOMO оценивал стоимость *написания* кода.

    $ slopcount .
    Totals grouped by slop origin (dominant slop source first):
    -------------------------------------------------------------------------------
    Origin                        files        sloplines    slop%    cognitivity
    ...
    Total Suspicious Lines Of Prose (SLOP)                   = 8,146
    Slop Ratio (SLOP/SLOC)                                   = 65.6%
    Total Estimated Cost to Comprehend                       = $ 166,105
    Coffee Required           = 412 cups ($ 1,648)
    VERDICT: [██████████░░░░░░░░░░] 65.6%  Repository on LLM self-service...

## Установка

    pipx install slopcount

## Философия

Генерация бесплатна — осознание дорого. Детекторы работают честно (регексы,
когнитивная сложность Кэмпбелла, скорость чтения Brysbaert), единицы — шуточные
(терапия, кофе, GPU-часы сожаления). Каждая улика объяснима: `--details`
покажет файл, строку, правило и вес.

Мы бы написали это на Perl, как оригинал — LLM не умеют Perl, инструмент был бы
гарантированно slop-free. Но мы слабы.

## CI-режим (шутка, которую можно поставить в пайплайн)

    slopcount . --json --fail-above 40 || echo "too much slop"

## Локализация

Вывод — en (default) / ru: `slopcount --lang ru .`

## Опциональная мощь

    pipx install 'slopcount[perplexity]'   # локальная GPT-2: гладкость прозы
    python -m slopcount.download_model
    slopcount . --perplexity

    pipx install 'slopcount[treesitter]'   # точная когнитивная сложность

## Лицензия

MIT
```

- [ ] **Step 2: pyproject-полировка** — добавить в `[project]`:

```toml
keywords = ["sloc", "sloccount", "ai", "llm", "slop", "parody", "cognitive-complexity"]
[project.urls]
Homepage = "https://github.com/echernyshev/slopcount"
```

- [ ] **Step 3: Финальная проверка**

Run: `python -m pytest -v` → всё PASS. Run: `slopcount . --lang ru` (на самом репо) → выводится отчёт; `slopcount . --json | python -m json.tool` → валидный JSON.

- [ ] **Step 4: Commit**

```bash
git add README.md pyproject.toml
git commit -m "docs: README with philosophy and usage"
```

---

## Self-Review (выполнен при написании плана)

1. **Покрытие спеки:** детекторы 4.1–4.6 (Tasks 7, 11–14, 22), SLOP/агрегация §5.1 (Tasks 2, 15), когнитивный вес §5.2 (Tasks 16–17), SLOCOMO §5.3–5.4 (Task 17), вывод §6.1 (Task 10, 17), вердикты §6.2 (Task 8), CLI §6.3 (Tasks 10, 19, 20, 22), i18n §6.4 (Tasks 9, 21), структура §7 (File Structure), ошибки §8 (Task 20 + GitUnavailable/reader-skip + прогресс на stderr в Task 24), тесты §9 (Tasks 1–25; golden-file рендерера — Task 19; чистота human-fixture — Task 24), порядок реализации §10 = порядок задач. Найденные при ревью пробелы устранены в самом плане: repo-level Spec-to-Code Ratio (Task 11), Google-докстринги и монотонность комментариев (Task 12), прогресс на stderr (Task 24), golden-тест (Task 19).
2. **Плейсхолдеры:** недопустимых «TBD/TODO» нет; единственные осознанные инструкции-подсказки — в Task 17/24 (сверить тестовые константы с формулами; чинить детекторы, а не порог) — это рабочие указания, а не дыры.
3. **Типы/имена:** `Evidence(file, line, category, weight, description)`, `Category.{PROSE,DOCS,STYLE,AGENCY,HISTORY}`, `aggregate(..., infected=...)`, `ScannedFile(path, language, kind, size)`, `CommentBlock(start_line, lines, is_docstring)`, `PhraseRule(pattern, weight, description)`, `DocsBloatResult(evidences, infected)`, `SlocomoResult(...)`, `Options(...)` — использованы единообразно во всех задачах.

