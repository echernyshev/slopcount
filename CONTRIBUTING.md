# Contributing

PR приветствуются. Основная ветка — `main`; релизы выходят тегами `v*`
(см. [RELEASE.md](RELEASE.md)).

## Окружение

Нужен Python ≥ 3.11. Бинарник `scc` ставится сам при первом запуске
(4.1.0, sha256-проверка, кеш `~/.cache/slopcount/`); свой — через
`--scc-path` или `SLOPCOUNT_SCC_BIN`.

```bash
git clone git@github.com:echernyshev/slopcount.git
cd slopcount
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/slopcount --version     # проверка: печатает текущую версию
```

## Проверки перед коммитом

Линтер и форматтер (конфиг в `pyproject.toml`, line-length 100):

```bash
.venv/bin/ruff check .
.venv/bin/ruff format --check .   # чинит: .venv/bin/ruff format .
```

Тесты (~6 с; e2e гоняет настоящий scc; `1 skipped` — guarded-тест
perplexity-extras, это норма):

```bash
.venv/bin/python -m pytest tests/ -q
.venv/bin/python -m pytest tests/test_slocomo.py -q          # один файл
.venv/bin/python -m pytest tests/test_e2e.py::test_name -q   # один тест
```

Сборка — то же, что делает CI build-job (см. ниже):

```bash
.venv/bin/pip install build twine
.venv/bin/python -m build
.venv/bin/twine check dist/*
unzip -l dist/*.whl | grep -cE 'locale/ru/LC_MESSAGES/slopcount\.mo|rules/'  # ≥ 5
```

## CI (`.github/workflows/ci.yml`)

На каждый push/PR — два job:

- **tests**: ruff + pytest; scc 4.1.0 ставится пином с проверкой sha256
  (хеш — из таблицы в `src/slopcount/scc.py`, единственный источник правды);
- **build**: `python -m build` + `twine check` + ассерты, что wheel содержит
  локаль (`slopcount.mo`) и все каталоги правил (`rules/*.toml`).

Теги `v*` CI не гоняет — их обрабатывает только релизный workflow.

## Нюансы кодовой базы

- **Версия живёт в двух местах** — `pyproject.toml` и
  `src/slopcount/__init__.py` (`__version__`) — и меняется синхронно;
  релизный workflow сверяет тег с версией и падает при расхождении.
- **README.md (en) и README.ru.md — зеркальная пара**: любое фактическое
  изменение (флаг, формула, дефолт, пример) вносится в оба файла.
- **i18n**: после правки `.po` обязательно перекомпилировать `.mo` —
  `test_i18n` проверяет побайтовое совпадение:
  ```bash
  msgfmt --check -o src/slopcount/locale/ru/LC_MESSAGES/slopcount.mo \
    src/slopcount/locale/ru/LC_MESSAGES/slopcount.po
  ```
  msgid — английский текст; плюрализация только `ngettext`; интерполяция
  только `%`-стилем; ключи JSON/CSV не локализуются никогда.
- **Новый детектор** = модуль в `src/slopcount/detectors/` + явный вызов в
  `app.py:run()` + решение о его категориях в `aggregate_slop()`
  (`evidence.py`). Реестра-автодискавери нет — подключение руками.
- **Спеки и планы** крупных изменений живут в `docs/superpowers/`
  (specs — «что и почему», plans — пошаговые планы выполнения).
- **Комментарии и докстринги — русские**, это сложившаяся конвенция проекта;
  идентификаторы и msgid — английские.
