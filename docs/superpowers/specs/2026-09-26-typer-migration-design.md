# Дизайн: перевод CLI slopcount на typer

- Дата: 2026-09-26
- Версия пакета: 0.1.0 → 0.2.0 (breaking-изменение CLI-поверхности)
- Статус: согласован с автором

## 1. Контекст и цель

`src/slopcount/cli.py` — тонкая argparse-обёртка (~96 строк): `build_parser()` +
`main(argv) -> int`. Цель — переписать её на typer, сохранив контракт
(флаги, дефолты, коды выхода 0/1/2, программный API `main(argv) -> int`).
Метод перехода — **big bang** (один проход, без параллельного argparse-CLI и
без золотого моста), выбранный автором осознанно; страховка — существующий
тестовый набор `run_cli` + новые контрактные тесты (§7).

Решение автора по совместимости: **меняем поверхность** на чистый typer-канон —
без argv-шимов; два осознанных breaking-изменения задокументированы (§5).

## 2. Результаты исследования typer (зафиксировано)

Проверено по живому typer **0.27.2** (последняя на 2026-09, PyPI) в .venv проекта:

- Требования: Python >=3.10 (у проекта >=3.11 — ок); зависимости —
  `rich>=13.8`, `shellingham>=1.3`, `annotated-doc`, `colorama` (Windows).
- Click с версии 0.26 **вендорен внутрь** (`typer._click`) и не ставится
  отдельным пакетом. Внутрь vendored-click не лезем.
- Программный вызов `app(argv, standalone_mode=False)` работает, но ошибки
  usage вылетают исключениями. Поэтому используем standalone-режим + ловлю
  `SystemExit` в `main()` — так click сам печатает usage-ошибки в stderr и
  выходит кодом 2 (как argparse), без ручного форматирования.
- `typer.Exit(code)` — единственный механизм терминальных исходов.
- `--version` — eager-callback (паттерн из документации typer).
- **`is_flag`/`flag_value` депрекированы и не работают** (DeprecationWarning в
  `typer/models.py`): argparse-семантика `--history [N]` (голый флаг → 500)
  через typer невыразима. Эмпирически: голый `--history` в конце →
  «requires an argument», перед другим флагом → BadParameter. Отсюда
  breaking-решение по `--history` (§5).
- Префиксных сокращений (`--deta`) в click/typer нет и не планируется.
- Форма `--history=500` работает и в argparse, и в typer.
- Единственная команда в `typer.Typer()` вызывается без имени подкоманды
  (проверено эмпирически) — структура «одна команда» сохраняется.

## 3. Объём изменений

| Файл | Изменение |
|---|---|
| `src/slopcount/cli.py` | полный rewrite на typer (~110 строк), логика 1:1 |
| `pyproject.toml` | `[project] dependencies = ["typer>=0.27,<0.28"]`; version = 0.2.0 |
| `tests/test_cli.py` | +7 контрактных тестов (§7); существующие не меняются |
| `README.md` | заметка об изменении CLI-поверхности (§5) |

**Не трогаем:** `app.py` (Options/run), детекторы, render, i18n, golden-файлы,
conftest.py, entry point `slopcount = "slopcount.cli:main"`, команды из CLAUDE.md.

## 4. Структура нового `cli.py`

```python
app = typer.Typer()  # add_completion по умолчанию (True) — оставляем


def _version(value: bool) -> None:
    if value:
        typer.echo(f"slopcount {__version__}")
        raise typer.Exit()


@app.command()  # единственная команда → без подкоманд
def scan(
    paths: list[str] | None = typer.Argument(None),
    details: bool = typer.Option(False, "--details"),
    json_out: bool = typer.Option(False, "--json"),
    csv_out: bool = typer.Option(False, "--csv"),
    history: int | None = typer.Option(None, "--history"),
    perplexity: bool = typer.Option(False, "--perplexity"),
    rules: list[Path] | None = typer.Option(None, "--rules"),
    lang: Literal["en", "ru"] | None = typer.Option(None, "--lang"),
    personcost: float = typer.Option(4690.50, "--personcost"),
    overhead: float = typer.Option(2.4, "--overhead"),
    coffee_price: float = typer.Option(4.0, "--coffee-price"),
    no_therapy: bool = typer.Option(False, "--no-therapy"),
    fail_above: float | None = typer.Option(None, "--fail-above"),
    verdict_only: bool = typer.Option(False, "--verdict-only"),
    wide: bool = typer.Option(False, "--wide"),
    version: bool | None = typer.Option(None, "--version", callback=_version, is_eager=True),
) -> None:
    i18n.setup(lang)
    # тело = текущая main(): paths or ["."], проверки корня,
    # RuntimeError → stderr + Exit(2), рендер-ветки, fail-above → Exit(1)


def main(argv: list[str] | None = None) -> int:
    try:
        app(argv)
    except SystemExit as e:
        return int(e.code or 0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Решения:

- **Команда — `scan`, не `main`**: модульный `main(argv) -> int` остаётся
  entry point'ом и API для тестов (`pyproject` не меняется).
- **Все терминальные исходы — `raise typer.Exit(code)`**; никогда не
  полагаемся на возвращаемое значение команды. Обёртка ловит `SystemExit` —
  та же схема, что в текущей argparse-версии.
- **Bool-флаги с явным `"--имя"`** — иначе typer генерирует пару
  `--x/--no-x` (появились бы несуществующие `--no-details` и т.п.). Для
  `--no-therapy` явный decl даёт один флаг (без `--no-no-therapy`).
- **`paths: list[str]`**, не `list[Path]` — `Options.paths: list[str]`
  не меняется; пусто → `["."]` в теле команды.
- **`rules: list[Path]`** — typer мультиплит повторные `--rules` (аналог
  argparse `action="append"`), в `Options` уходит `rules or []`.
- **`--lang` через `Literal["en", "ru"]`** — невалидное значение →
  usage-ошибка, exit 2 (эквивалент argparse `choices`).
- help-тексты флагов — статические английские строки (как сейчас: argparse
  help не локализовался; i18n включается после парсинга).

Тело команды переносит из `main()` без изменений: проверку корня
(не существует / это файл → локализованное сообщение в stderr, exit 2),
`try/except RuntimeError` (битый `--rules`, `--perplexity` без extras →
stderr, exit 2), ветки рендера (json > csv > verdict-only >
text+slocomo+verdict[+details]), порог `--fail-above` (exit 1).

## 5. Поверхность CLI — изменения (единственный breaking)

1. **`--history` всегда требует число**: `--history 500` или `--history=500`.
   Голый `--history` → usage-ошибка, exit 2 (раньше молча означал 500).
2. **Префиксные сокращения не работают**: `--deta` больше не синоним
   `--details` (раньше — argparse `allow_abbrev`).

Побочные (не breaking): `--help` в rich-формате с панелью опций; добавились
`--install-completion` / `--show-completion`. Формат stderr usage-ошибок
текстуально другой, коды и поток — те же. Ctrl+C завершает работу молча
с кодом 130 (раньше — traceback; код тот же, typer ловит KeyboardInterrupt
в core.py → Exit(130)).

Уточнения по итогам реализации (ревью): `-h` **сохранён** как алиас `--help`
через `context_settings={"help_option_names": ["-h", "--help"]}` — осознанное
отступление от «чистого typer-канона» ради паритета с argparse.

Всё остальное идентично: имена и дефолты флагов, накопление `--rules`,
`slopcount` без аргументов сканирует `.`, формат вывода `slopcount {version}`
для `--version`.

## 6. Контракт кодов выхода (без изменений)

| Код | Когда |
|---|---|
| 0 | успех, `--version`, `--help` |
| 1 | `--fail-above` превышен |
| 2 | usage-ошибки (неизвестный флаг, битое значение, **теперь и голый `--history`**, невалидный `--lang`), путь не найден / это файл, битый `--rules` TOML, `--perplexity` без extras |

Usage-ошибки click печатает в stderr сам и завершается кодом 2.

Вне таблицы: Ctrl+C → молчаливый exit 130 (typer перехватывает
KeyboardInterrupt; в argparse-версии печатался traceback, код был тот же).

## 7. Тесты

Существующие проходят без правок: `run_cli`/`test_cli` зовут `main(argv)` с
тем же контрактом; `test_version_flag` ловит `SystemExit` опционально
(новый `main` возвращает 0 без исключения — тест по-прежнему зелёный).

Новые в `tests/test_cli.py`:

1. `--history` без значения → код 2, stderr упоминает `--history`
   (click напишет «Option '--history' requires an argument»);
2. неизвестный флаг (`--nope`) → 2;
3. `--lang xx` → 2;
4. `--help` → 0, stdout содержит `--details`, `--history`, `--fail-above`;
5. `--rules` дважды → оба файла парсятся (накопление; один битый → 2);
6. smoke на непокрытые флаги: `--personcost`/`--overhead`/`--coffee-price`/`--wide`
   → код 0, вывод присутствует;
7. `monkeypatch.chdir(tmp_path)` + `main([])` → 0 — дефолт `paths or ["."]`
   сканирует текущий каталог.

## 8. Риски и их принятие

- **Формат stderr/help меняется** (rich) — принято: тесты на текст stderr не
  завязаны, коды и потоки сохранены.
- **+3 транзитивные зависимости** (rich, shellingham, annotated-doc) — принято
  автором; пин внутри минорки `>=0.27,<0.28` ограничивает дрейф.
- **Vendored click** — внутренность typer; обращение к `typer._click` в коде
  проекта запрещено (кроме чтения для понимания поведения).
- **Big bang без золотого моста** — принят автором; компенсация: широкий
  существующий e2e-набор + контрактные тесты §7.

## 9. Вне области

Рефакторинг `app.py`/детекторов/render, изменение форматов вывода, подкоманды
(например `slopcount scan`), локализация help, env-переменные для опций,
конфиг-файлы. Любое из этого — отдельными спеками.

## 10. Критерии готовности

- `pytest tests/ -q` зелёный (включая новые §7);
- `ruff check .` и `ruff format --check .` чистые;
- ручная проверка: `.venv/bin/slopcount --help`, `.venv/bin/slopcount
  tests/fixtures/slop_project --details`, `.venv/bin/slopcount --version`,
  `.venv/bin/slopcount tests/fixtures/slop_project --history` → код 2;
- `pyproject.toml` содержит пин typer и версию 0.2.0.
