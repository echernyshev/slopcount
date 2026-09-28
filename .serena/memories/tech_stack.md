# Tech stack

- Python **>=3.11** (жёстко, `requires-python`), пакет `slopcount`.
- Сборка **hatchling**; wheel = `src/slopcount` (src-layout).
- **Ноль рантайм-зависимостей**. Extras:
  - `dev`: pytest>=8, ruff>=0.14
  - `perplexity`: transformers>=4.40, torch>=2.2 (lazy import только при `--perplexity`; gpt2, модель переопределяется `SLOPCOUNT_PPLX_MODEL`, скачивается `python -m slopcount.download_model`)
  - `treesitter`: tree-sitter>=0.22, tree-sitter-python>=0.23 (точный Cognitive Complexity только для python; иначе индентационная аппроксимация + `approximate=True`)
- Линтер/форматтер — **ruff** (конфиг в `pyproject.toml`, line-length 100, target py311). `tests/fixtures` исключён из ruff — эталонный слоп намеренно плохой.
- i18n — stdlib gettext; каталоги `src/slopcount/locale/ru/LC_MESSAGES/`; компиляция внешним `msgfmt`.
- Тесты — pytest, все в `tests/` (~2 с), фикстуры-проекты в `tests/fixtures/{slop_project,human_project}`.
