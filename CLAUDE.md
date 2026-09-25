# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Что это

`slopcount` — сканирует проект, детектирует LLM-слоп и считает стоимость его *осознания* (SLOCOMO вместо
COCOMO). Детекция и формулы честные, единицы — шутливые. Каждая улика
объяснима (`--details`).


## Команды

```bash
.venv/bin/python -m pytest tests/ -q            # все тесты (~2 с)
.venv/bin/python -m pytest tests/test_slocomo.py -q          # один файл
.venv/bin/python -m pytest tests/test_e2e.py::test_name -q   # один тест
.venv/bin/slopcount .                           # самоскан
.venv/bin/slopcount tests/fixtures/slop_project --details    # на эталонном слопе
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

## Архитектура

Конвейер: `scanner → detectors → Evidence[] → aggregate → SLOCOMO → render`.
Оркестратор — `app.py:run()`; `cli.py` — тонкая argparse-обёртка.

- **`evidence.py`** — ядро модели данных: `Evidence(file, line, category,
  weight, description)` (frozen dataclass) и `aggregate()`. Пять категорий
  (`prose/docs/style/agency/history`) не смешиваются. **AGENCY не входит в
  SLOP и Slop Ratio** — это констатация «в проекте живут агенты», не обвинение.
- **SLOP** = уникальные (file, line) с уликами по prose/docs/style/history
  + `round(строки × 0.8)` за каждый «заражённый» md-файл (плотность веса
  > 0.1 на строку). SLOC=0 при SLOP>0 даёт ratio=inf — это предусмотрено.
- **Детекторы подключаются вручную в `app.py`** (реестра из спеки §7 нет;
  `detectors/__init__.py` содержит только общий `EMOJI_RE`). Новый детектор =
  новый модуль + явный вызов в `run()` + включение/невключение в SLOP-набор
  категорий в `aggregate()`.
- **`scanner.py`** — упрощённый `.gitignore` (без отрицаний `!`, без полной
  git-семантики — осознанно), `SKIP_DIRS`, бинарность определяется по NUL-байту
  в первых 1024 (`read_text` → None → счётчик skip).
- **`extractors.py`** — инвариант: `CommentBlock` занимает ровно
  `len(lines)` физических строк начиная с `start_line` (пустые строки внутри
  блока сохраняются). На инварианте держатся `count_sloc` и нумерация улик
  `PhraseDetector`. Известные приближения (незакрытый docstring, `/* */` не
  с начала строки) задокументированы в докстринге — не «чинить» молча.

### i18n (gettext, критичные нюансы)

- **Английский — язык исходников**: каждый msgid уже английский текст,
  обёрнут в `_()`; en работает без каталога (NullTranslations-фолбэк).
- `i18n.setup()` обязан быть вызван до любого `_()` — это глобальное
  состояние; conftest.py сбрасывает в en autouse-фикстурой (детекторы и
  каталоги правил тоже локализуются при загрузке).
- Плюрализация только через `ngettext` (ru: 1 чашка / 2 чашки / 5 чашек),
  интерполяция только `%`-стилем — msgfmt проверяет плейсхолдеры.
  Числа — `fmt_int`/`fmt_float` (разделители en `,.` / ru ` ,`).
- **Ключи JSON/CSV не локализуются никогда** — стабильны для CI между языками.
- Каталоги фраз *детекции* (`rules/phrases_en.toml`, `phrases_ru.toml`)
  ортогональны локали UI: грузятся всегда оба, можно сканировать английский
  слоп с русским интерфейсом. Описания правил проходят `_()` при загрузке
  (локализация улик в `--details`/`--csv`).
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
- **`[treesitter]`**: точный Cognitive Complexity **только для python**
  (`cognitive_complexity_tspython`); любой не-python файл или отсутствие
  extras → индентационная аппроксимация и `approximate=True` во всём отчёте
  (смешанный режим считается приближённым). `exact_available()` под
  `lru_cache` — доступность extras не меняется за запуск.


  




