# slopcount — core

Пародия на sloccount: сканирует проект, детектирует LLM-слоп, считает стоимость
осознания (SLOCOMO). Детекция/формулы честные, единицы шутливые.

## Source map (всё под `src/slopcount/`)

- `app.py:run()` — оркестратор конвейера `scanner → detectors → Evidence[] → aggregate → SLOCOMO → render`. Детекторы подключаются ВРУЧНУЮ здесь (реестра из спеки §7 нет).
- `cli.py` — тонкая argparse-обёртка, только парсинг/вывод.
- `evidence.py` — ядро данных: `Evidence(file, line, category, weight, description)` frozen dataclass + `aggregate()`.
- `scanner.py` — обход файлов: упрощённый `.gitignore` (без `!`-отрицаний — осознанно), SKIP_DIRS, бинарность по NUL-байту в первых 1024.
- `extractors.py` — коммент-блоки; инвариант: `CommentBlock` = ровно `len(lines)` физических строк от `start_line`. Держит `count_sloc` и нумерацию улик PhraseDetector.
- `detectors/` — по модулю на категорию: `phrase.py` (prose), `docs_bloat.py` (docs), `code_style.py` (style), `git_history.py` (history), `env_markers.py`, `perplexity.py` (lazy). `__init__.py` — только общий `EMOJI_RE`.
- `metrics/` — `sloc.py`, `slocomo.py` (формула), `cognitive.py` (treesitter/exact vs индентационная аппроксимация).
- `render/` — `text.py`, `json_out.py`, `csv_out.py`.
- `rules/*.toml` — каталоги фраз (`phrases_en.toml`/`phrases_ru.toml`) и `env_markers.toml`; грузятся всегда оба языка, ортогонально локали UI.
- `verdicts.py` — итоговые вердикты.
- `i18n.py` — gettext-сетап, `fmt_int`/`fmt_float`.

## Ключевые инварианты

- Пять категорий `prose/docs/style/agency/history` не смешиваются.
- **AGENCY не входит в SLOP и Slop Ratio** — «в проекте живут агенты», не обвинение.
- SLOP = уникальные (file, line) по prose/docs/style/history + `round(строки × 0.8)` за каждый «заражённый» md (плотность веса > 0.1/строку). SLOC=0 при SLOP>0 → ratio=inf — предусмотрено.
- Новый детектор = модуль + явный вызов в `run()` + решение о включении в SLOP-набор в `aggregate()`.

Подробности: стек — `mem:tech_stack`; команды — `mem:suggested_commands`; стиль/i18n — `mem:conventions`; критерии завершения — `mem:task_completion`.
