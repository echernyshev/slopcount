# Переход CLI slopcount на typer — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Переписать `src/slopcount/cli.py` с argparse на typer 0.27 одним проходом (big bang), сохранив контракт: имена флагов, дефолты, коды выхода 0/1/2, программный API `main(argv) -> int`.

**Architecture:** Единственная команда `scan` в `typer.Typer()` (без подкоманд); модульная обёртка `main(argv)` вызывает `app(argv)` и переводит `SystemExit` в int — та же схема, что была с argparse. Всё вне `cli.py` (app.py, детекторы, render, i18n) не трогается.

**Tech Stack:** Python 3.11+, typer 0.27.2 (уже стоит в .venv, click вендорен внутрь), pytest, ruff.

**Спецификация:** `docs/superpowers/specs/2026-09-26-typer-migration-design.md` — прочтите §5 (изменения поверхности), §6 (коды выхода), §7 (тесты), §10 (критерии готовности).

---

## Контекст для инженера (нулевое знание кодовой базы предполагается)

- Все команды — через venv проекта: `.venv/bin/python -m pytest ...`, `.venv/bin/ruff ...`, `.venv/bin/slopcount ...`.
- Полный набор тестов: `.venv/bin/python -m pytest tests/ -q` (~2 с). Линтер: `.venv/bin/ruff check .`, формат: `.venv/bin/ruff format --check .` (line-length = 100).
- Пакет установлен в .venv **editable** — правки `src/` подхватываются без переустановки.
- `tests/conftest.py` autouse-фикстурой сбрасывает локаль в en перед каждым тестом — писать `--lang` в тестах не обязательно, но существующие тесты пишут.
- `tests/test_e2e.py` содержит хелпер `run_cli(argv)`: вызывает `slopcount.cli.main(argv)`, перенаправляя **только stdout**, возвращает `(код, stdout)`. Для stderr используйте `capsys`.
- Важная семантика текущего argparse-CLI (проверена): голый `--history` в конце argv → глубина 500 и код 0; после перехода на typer это станет usage-ошибкой с кодом 2 — это **задуманное** breaking-изменение, тест из Task 2 кодирует новое поведение.
- `--wide` — мёртвый флаг (принимается, ни на что не влияет). НЕ чинить — вне области спеки.
- Тест `test_i18n.py` проверяет побайтовое совпадение .po/.mo — эти файлы мы не трогаем.

## Структура файлов

| Файл | Действие | Ответственность |
|---|---|---|
| `tests/test_cli.py` | Modify (дополнить) | контрактные тесты CLI |
| `src/slopcount/cli.py` | Rewrite | typer-обёртка над `app.run()` |
| `pyproject.toml` | Modify | зависимость typer, версия 0.2.0 |
| `src/slopcount/__init__.py` | Modify (1 строка) | `__version__ = "0.2.0"` |
| `README.md` | Modify | заметка о совместимости CLI |

---

### Task 1: Регрессионные контракт-тесты (на argparse все зелёные)

Затягиваем сетку безопасности ДО переписывания: тесты, фиксирующие поведение, одинаковое для argparse и typer. Они должны пройти сразу — если хоть один падает, STOP и разберитесь, прежде чем продолжать.

**Files:**
- Modify: `tests/test_cli.py` (дополнить в конец файла)

- [ ] **Step 1: Добавить тесты в конец `tests/test_cli.py`**

```python
def test_unknown_flag_exit_2(tmp_path):
    code, _ = run_cli([str(tmp_path), "--nope", "--lang", "en"])
    assert code == 2


def test_bad_lang_exit_2(tmp_path):
    code, _ = run_cli([str(tmp_path), "--lang", "xx"])
    assert code == 2


def test_help_exit_0():
    code, out = run_cli(["--help"])
    assert code == 0
    for flag in ("--details", "--history", "--fail-above"):
        assert flag in out


def test_rules_repeated_accumulates(tmp_path):
    r1 = tmp_path / "r1.toml"
    r1.write_text('[[rule]]\npattern = "zqfirst"\nweight = 9\ndescription = "zz-marker-one"\n')
    r2 = tmp_path / "r2.toml"
    r2.write_text('[[rule]]\npattern = "zqsecond"\nweight = 9\ndescription = "zz-marker-two"\n')
    (tmp_path / "a.md").write_text("zqfirst zqsecond\n")
    code, out = run_cli(
        [str(tmp_path), "--details", "--lang", "en", "--rules", str(r1), "--rules", str(r2)]
    )
    assert code == 0
    assert "zz-marker-one" in out and "zz-marker-two" in out


def test_pricing_and_wide_flags_accepted(tmp_path):
    (tmp_path / "a.py").write_text("x = 1\n")
    code, out = run_cli(
        [
            str(tmp_path),
            "--lang",
            "en",
            "--personcost",
            "1000",
            "--overhead",
            "1.0",
            "--coffee-price",
            "2.5",
            "--wide",
        ]
    )
    assert code == 0
    assert "SLOC" in out


def test_no_args_scans_cwd(tmp_path, monkeypatch):
    (tmp_path / "a.py").write_text("x = 1\n")
    monkeypatch.chdir(tmp_path)
    assert main([]) == 0
```

- [ ] **Step 2: Прогнать файл тестов**

Run: `.venv/bin/python -m pytest tests/test_cli.py -q`
Expected: все PASS (старые + новые). Если новый тест упал — разберитесь (например, `--rules`-тест: описания правил действительно попадают в `--details`), не продолжайте с падением.

- [ ] **Step 3: Прогнать полный набор для уверенности**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: все PASS.

- [ ] **Step 4: Commit**

```bash
git add tests/test_cli.py
git commit -m "test: контрактные тесты CLI перед переходом на typer"
```

---

### Task 2: Breaking-тест + переписывание `cli.py` на typer

Сначала красный тест нового поведения `--history`, затем полный rewrite. Существующие тесты (`test_e2e.py`, `test_cli.py`) — главный критерий: они не меняются и должны остаться зелёными.

**Files:**
- Modify: `tests/test_cli.py` (добавить 1 тест)
- Rewrite: `src/slopcount/cli.py`
- Modify: `pyproject.toml` (версия + зависимость)
- Modify: `src/slopcount/__init__.py` (версия)

- [ ] **Step 1: Добавить красный тест в конец `tests/test_cli.py`**

```python
def test_history_bare_requires_value(tmp_path, capsys):
    (tmp_path / "a.py").write_text("x = 1\n")
    code = main([str(tmp_path), "--history"])
    assert code == 2
    assert "--history" in capsys.readouterr().err
```

- [ ] **Step 2: Прогнать — убедиться, что падает ровно он**

Run: `.venv/bin/python -m pytest tests/test_cli.py::test_history_bare_requires_value -q`
Expected: FAIL — argparse молча принимает голый `--history` (означает 500), сканирует tmp_path и возвращает 0, assertion `assert 0 == 2` падает.

- [ ] **Step 3: Полностью заменить содержимое `src/slopcount/cli.py`**

```python
from __future__ import annotations

import sys
from pathlib import Path
from typing import Literal

import typer

from slopcount import __version__, i18n
from slopcount.app import Options, run
from slopcount.i18n import _
from slopcount.render.csv_out import render_csv
from slopcount.render.json_out import render_json
from slopcount.render.text import (
    render_details,
    render_slocomo,
    render_text,
    render_verdict,
)

app = typer.Typer()


def _version(value: bool) -> None:
    if value:
        typer.echo(f"slopcount {__version__}")
        raise typer.Exit()


@app.command()
def scan(
    paths: list[str] | None = typer.Argument(None, help="Directory to scan (default: .)"),
    details: bool = typer.Option(False, "--details", help="List every evidence line"),
    json_out: bool = typer.Option(False, "--json", help="Print JSON report"),
    csv_out: bool = typer.Option(False, "--csv", help="Print CSV report"),
    history: int | None = typer.Option(None, "--history", help="Git history depth to scan"),
    perplexity: bool = typer.Option(False, "--perplexity", help="Perplexity detector (extras)"),
    rules: list[Path] | None = typer.Option(None, "--rules", help="Extra rules TOML (repeatable)"),
    lang: Literal["en", "ru"] | None = typer.Option(None, "--lang", help="Interface language"),
    personcost: float = typer.Option(4690.50, "--personcost", help="Monthly person cost, USD"),
    overhead: float = typer.Option(2.4, "--overhead", help="COCOMO overhead multiplier"),
    coffee_price: float = typer.Option(4.0, "--coffee-price", help="Coffee cup price, USD"),
    no_therapy: bool = typer.Option(False, "--no-therapy", help="Skip the therapy estimate"),
    fail_above: float | None = typer.Option(
        None, "--fail-above", help="Exit 1 if slop ratio above"
    ),
    verdict_only: bool = typer.Option(False, "--verdict-only", help="Print the verdict line only"),
    wide: bool = typer.Option(False, "--wide", help="Wide table layout"),
    version: bool | None = typer.Option(
        None, "--version", callback=_version, is_eager=True, help="Show version and exit"
    ),
) -> None:
    """Count the AI slop in a project and the cost of comprehending it."""
    i18n.setup(lang)
    opts = Options(
        paths=paths or ["."],
        details=details,
        json_out=json_out,
        csv_out=csv_out,
        history=history,
        perplexity=perplexity,
        rules=rules or [],
        lang=lang,
        personcost=personcost,
        overhead=overhead,
        coffee_price=coffee_price,
        no_therapy=no_therapy,
        fail_above=fail_above,
        verdict_only=verdict_only,
        wide=wide,
    )
    root = Path(opts.paths[0])
    if not root.exists():
        print(_("slopcount: path not found: {path}").format(path=root), file=sys.stderr)
        raise typer.Exit(code=2)
    if root.is_file():
        print(
            _("slopcount: path is a file, directory expected: {path}").format(path=root),
            file=sys.stderr,
        )
        raise typer.Exit(code=2)
    try:
        report = run(opts)
    except RuntimeError as e:  # напр. --perplexity без extras: подсказка, exit 2
        print(e, file=sys.stderr)
        raise typer.Exit(code=2)
    if json_out:
        print(render_json(report))
    elif csv_out:
        print(render_csv(report), end="")
    elif verdict_only:
        print(render_verdict(report))
    else:
        print(render_text(report))
        print(render_slocomo(report))
        print(render_verdict(report))
        if details:
            print(render_details(report))
    if fail_above is not None and report.slop_ratio > fail_above:
        raise typer.Exit(code=1)


def main(argv: list[str] | None = None) -> int:
    try:
        app(argv)
    except SystemExit as e:  # typer/click: --version (0) / usage error (2) / Exit(N)
        return int(e.code or 0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: `pyproject.toml` — версия и зависимость**

Заменить строку 7:
```toml
version = "0.1.0"
```
на:
```toml
version = "0.2.0"
```
И после строки `authors = [{ name = "Egor Chernyshev" }]` добавить:
```toml
dependencies = ["typer>=0.27,<0.28"]
```

- [ ] **Step 5: `src/slopcount/__init__.py` — версия**

Заменить единственную строку на:
```python
__version__ = "0.2.0"
```

- [ ] **Step 6: Красный тест стал зелёным**

Run: `.venv/bin/python -m pytest tests/test_cli.py::test_history_bare_requires_value -q`
Expected: PASS. Если падает с непонятной rich-трассировкой — проверьте, что `main` вызывает `app(argv)` (standalone-режим по умолчанию), а не `app(argv, standalone_mode=False)`.

- [ ] **Step 7: Главный критерий — нетронутые тесты зелёные**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: все PASS. Особое внимание: `test_e2e.py` (run_cli-тесты), `test_cli.py::test_version_flag`, `test_i18n.py`.

- [ ] **Step 8: Линт и формат**

Run: `.venv/bin/ruff format src/slopcount/cli.py tests/test_cli.py && .venv/bin/ruff check .`
Expected: format applied / check — no errors. Повторно прогнать pytest после форматирования.

- [ ] **Step 9: Commit**

```bash
git add src/slopcount/cli.py src/slopcount/__init__.py pyproject.toml tests/test_cli.py
git commit -m "feat!: CLI на typer 0.27, --history требует число (0.2.0)"
```

---

### Task 3: README-заметка и финальная верификация

**Files:**
- Modify: `README.md` (вставить секцию перед `## Локализация`)

- [ ] **Step 1: Вставить секцию в README**

Перед строкой `## Локализация` вставить:

```markdown
## Совместимость CLI (0.2.0)

CLI переехал на typer. Коды выхода не изменились (0 — ок, 1 — превышен
`--fail-above`, 2 — ошибки), но поверхность чуть строже:

- `--history` теперь требует число: `--history 500` (раньше флаг без значения
  молча означал 500);
- префиксные сокращения (`--deta` вместо `--details`) больше не работают;
- `--help` стал нагляднее, появились `--install-completion`/`--show-completion`.

```

- [ ] **Step 2: Критерии готовности из спеки §10**

```bash
.venv/bin/python -m pytest tests/ -q          # все зелёные
.venv/bin/ruff check .                        # чисто
.venv/bin/ruff format --check .               # чисто
.venv/bin/slopcount --version                 # → slopcount 0.2.0
.venv/bin/slopcount --help                    # rich-help, флаги на месте
.venv/bin/slopcount tests/fixtures/slop_project --details | head -30   # отчёт
.venv/bin/slopcount tests/fixtures/slop_project --history; echo "exit=$?"  # usage-ошибка, exit=2
```

Expected: последняя команда печатает ошибку про `--history` и `exit=2`; остальные — успешны.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: заметка о совместимости CLI в README"
```

---

## Откат

Весь переход — ядро в двух коммитах (Task 2 `86b79df` + ревью-фиксы `bf143bf`), обвязка — Task 1/3. Откат ядра: `git revert bf143bf 86b79df` (в порядке убывания — одиночный revert `86b79df` конфликтует из-за фиксов поверх).
