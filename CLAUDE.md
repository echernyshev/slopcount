# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Что это

`slopcount` — сканирует проект, детектирует LLM-слоп и считает стоимость его *понимания* (comprehension,
SLOCOMO вместо COCOMO). Детекция и формулы честные, единицы — шутливые. Каждая улика
объяснима (`--evidence`).

Процессная документация: [CONTRIBUTING.md](CONTRIBUTING.md) — окружение
разработчика и полный набор проверок; [RELEASE.md](RELEASE.md) — выпуск версии
(тег `v*` → автопубликация в PyPI).


## Команды

```bash
.venv/bin/python -m pytest tests/ -q            # все тесты (~6 с: e2e гоняет настоящий scc)
.venv/bin/python -m pytest tests/test_slocomo.py -q          # один файл
.venv/bin/python -m pytest tests/test_e2e.py::test_name -q   # один тест
.venv/bin/slopcount .                           # самоскан
.venv/bin/slopcount . --scc-path /path/to/scc   # явный бинарник scc
.venv/bin/slopcount tests/fixtures/slop_project --evidence   # на эталонном слопе
.venv/bin/ruff check .                          # линтер (конфиг в pyproject.toml)
.venv/bin/ruff format --check .                 # проверить форматирование
.venv/bin/ruff format .                         # отформатировать
```



**После правки `.po` обязательно перекомпилировать `.mo`** — тест
`test_i18n.py` проверяет побайтовое совпадение (drift guard):

```bash
msgfmt --check -o src/slopcount/locale/ru/LC_MESSAGES/slopcount.mo \
  src/slopcount/locale/ru/LC_MESSAGES/slopcount.po
```

### CI и релизы

- `ci.yml` (push/PR, обе ветки): job **tests** — ruff + pytest, scc 4.1.0
  ставится пином с проверкой sha256 (хеш из таблицы `scc.py`); job **build** —
  `python -m build` + `twine check` + ассерты, что wheel содержит локаль
  (`slopcount.mo`) и все каталоги `rules/*.toml`.
- `release.yml` (только теги `v*`): сборка → `twine check` → ассерты wheel →
  сверка тега с версией `pyproject.toml` → публикация в PyPI через trusted
  publishing (OIDC, окружение `pypi`, без токенов). Тесты в релизе не гоняются —
  main должен быть зелёным до тега; последовательность и нюансы — RELEASE.md.
- Версия живёт в двух местах (`pyproject.toml` + `src/slopcount/__init__.py`)
  и меняется синхронно.
- **README.md (en) и README.ru.md — зеркальная пара**: фактические изменения
  (флаги, формулы, дефолты, примеры) вносятся в оба файла.
- sdist не включает `.claude`/`.serena` —
  `[tool.hatch.build.targets.sdist] exclude` в `pyproject.toml`.

## Архитектура

Конвейер: `scc (один subprocess: манифест per-file + COCOMO/LOCOMO) →
классификация kind/language → volume (VolumeStats: языки/SLOC/комментарии/md) →
детекторы → Evidence[] → aggregate_slop (SlopStats) → comprehension (SLOCOMO +
разбивки costs.py) → render (3 секции)`. Оркестратор — `app.py:run()`; `cli.py` —
тонкая typer-обёртка.

- **`scc.py`** — единственная точка работы с бинарником scc. Резолв:
  `--scc-path` > `SLOPCOUNT_SCC_BIN` > PATH (версия ≥ 4.1.0) >
  кеш `~/.cache/slopcount/scc/<ver>/` > скачивание официального релиза
  (sha256 по зашитой таблице, атомарная укладка в кеш). Один subprocess
  `--format json2 --by-file --cognitive --locomo` из нейтрального пустого cwd
  + `--no-config` (гасит авто-детект `.sccconfig`/`SCC_CONFIG_PATH` — чужой
  конфиг искажает COCOMO/LOCOMO на порядки); `--personcost/--overhead`
  транслируются в `--avg-wage/--overhead`; `SKIP_DIRS` → `--exclude-dir`.
  В отчёт идёт фактическая версия бинарника, а не пин.
- **`rules/languages.toml`** — все 366 display-имён scc 4.1.0 с явной
  классификацией kind: code (251) / markdown (2) / prose (1) / data (112);
  `[extractors]` (31 имя → id для extractors.py). Пользовательский `--rules`
  TOML переопределяет точечно секцией `[languages]` (мердж поверх builtin,
  оверрайд стирает extractor-id, неизвестное имя — предупреждение). Имя,
  которого нет в каталоге (будущая версия scc) → молча `("data", None)`.
- **Матрица kind → судьба файла** (спека §5.3): `data` не читается вообще —
  только факт существования; SLOC/комментарии/complexity/cognitive — только
  kind=code; числитель MD/SLOC — только `.md`/`.markdown`; COCOMO/LOCOMO scc
  считает по полному дереву (включая data) — «написать/перегенерировать всё
  дерево» против «понять слоп» у SLOCOMO.
- **`evidence.py`** — ядро модели данных: `Evidence`, `ScannedFile`,
  `read_text` и `Report` (+ `scc_version`/`complexity`/`cognitive_total`/
  `files_total`/`cocomo`/`locomo`) и `aggregate_slop()`. Пять категорий
  (`prose/docs/style/agency/history`) не смешиваются. **AGENCY не входит в
  SLOP и Slop Ratio** — это констатация «в проекте живут агенты», не
  обвинение. Все ratios — доли; SLOC=0 при SLOP>0 даёт ratio=inf — это
  предусмотрено.
- **Три секции отчёта** (спека 2026-09-27-comprehension-redesign): Project
  Volume / Comprehension Effort & Cost / Detected Slop; три шкалы `scales.py`
  (doc/comment/slop, калибровка §7 спеки: doc 0.05/0.35/0.50/0.75/1.0+RECURSION,
  slop CLEAN<0.005) вместо вердикта; `--evidence` вместо `--details` (все
  улики + сниппеты строк, кеш lru_cache); `--fail-above`/`--verdict-only`
  удалены — CI-гейтинг поверх `--json`.
- **SLOP** = уникальные (file, line) с уликами по prose/docs/style/history
  + `round(строки × 0.8)` за каждый «заражённый» md-файл (гигант >500
  строк или плотность веса > 0.1 на строку); **MD/SLOC** = md-строки (только `.md`/`.markdown`) / SLOC —
  информационная вместе с comment/SLOC.
- **Детекторы подключаются вручную в `app.py`** (реестра из спеки §7 нет;
  `detectors/__init__.py` содержит только общий `EMOJI_RE`). Новый детектор =
  новый модуль + явный вызов в `run()` + включение/невключение в SLOP-набор
  категорий в `aggregate_slop()`.
- **`metrics/`** — `slocomo.py`: ComprehensionStats — чтение доков
  (238 wpm × 2.3) + комментарии (строки × 6 слов) + код (200 SLOC/ч) +
  cognitive×0.5 мин (весь проект); `person_months = reading_hours/152 ×
  (1+slop_ratio)`, всё per person + team_costs (Фибоначчи 1..21);
  токены/окна/GPU — из LOCOMO (in+out). `metrics/costs.py`: разбивки
  стоимостей в единой структуре корзин docs / source_code{total, code,
  comments} / data — COCOMO независимым пересчётом 2.4·K^1.05
  (+drift-guard против estimatedCost scc), LOCOMO атрибуцией по долям
  Code-строк, SLOCOMO точной суммой. Комментарии scc в COCOMO/LOCOMO не
  считает (подстрока «комментарии» — прочерк), data SLOCOMO не читает.
- **`extractors.py`** — разбор коммент-блоков для phrase- и style-детекторов
  (нумерация улик, `is_docstring`, содержимое блоков). Инвариант:
  `CommentBlock` занимает ровно `len(lines)` физических строк начиная с
  `start_line` (пустые строки внутри блока сохраняются). Известные
  приближения (незакрытый docstring, `/* */` не с начала строки)
  задокументированы в докстринге — не «чинить» молча.
- **Обход и gitignore** — семантика scc: настоящие gitignore-правила (с
  отрицаниями), детект языка по shebang/имени файла, бинарные файлы в
  манифест не попадают. `read_text` (NUL-байт в первых 1024, строгий UTF-8)
  остаётся страховкой от нечитаемых файлов → счётчик skip.

### i18n (gettext, критичные нюансы)

- **Английский — язык исходников**: каждый msgid уже английский текст,
  обёрнут в `_()`; en работает без каталога (NullTranslations-фолбэк).
- `i18n.setup()` обязан быть вызван до любого `_()` — это глобальное
  состояние; conftest.py сбрасывает в en autouse-фикстурой (детекторы и
  каталоги правил тоже локализуются при загрузке).
- Плюрализация только через `ngettext` (ru: 1 чашка / 2 чашки / 5 чашек),
  интерполяция только `%`-стилем — msgfmt проверяет плейсхолдеры.
  Числа — `fmt_int`/`fmt_float` (разделители en `,.` / ru ` ,`).
- **Ключи JSON/CSV не локализуются никогда** — стабильны для CI между языками.
- Каталоги фраз *детекции* (`rules/phrases_en.toml`, `phrases_ru.toml`)
  ортогональны локали UI: грузятся всегда оба, можно сканировать английский
  слоп с русским интерфейсом. Описания правил проходят `_()` при загрузке
  (локализация улик в `--evidence`/`--csv`).
- Битый пользовательский `--rules` TOML → `RuntimeError` → exit 2; битый
  встроенный — fail fast.

### Опциональные режимы (lazy import, extras)

- **`--perplexity`**: transformers/torch импортируются только при флаге;
  нет extras → `RuntimeError` → exit 2 с подсказкой. Модель — gpt2
  (переопределяется `SLOPCOUNT_PPLX_MODEL`), скачивается
  `python -m slopcount.download_model`. Замер **контекстный** (GPTZero-стиль):
  один проход по файлу, пер-токенный NLL, группировка по предложениям через
  offset mapping; **первое предложение отбрасывается** (нет левого контекста),
  порог — **медиана < 40**. Burstiness убран: на gpt2 классы не разделяет.
  Файлы длиннее окна модели меряются по префиксу; предупреждение токенизатора
  об overlong глушится хирургическим фильтром логгера.
