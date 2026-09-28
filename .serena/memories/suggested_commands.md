# Suggested commands

Всё через `.venv/bin/` (виртуалка в корне проекта):

```bash
.venv/bin/python -m pytest tests/ -q                    # все тесты (~2 с)
.venv/bin/python -m pytest tests/test_slocomo.py -q     # один файл
.venv/bin/python -m pytest tests/test_e2e.py::test_name -q  # один тест
.venv/bin/slopcount .                                   # самоскан
.venv/bin/slopcount tests/fixtures/slop_project --details  # эталонный слоп
.venv/bin/ruff check .              # линтер
.venv/bin/ruff format --check .     # проверить формат
.venv/bin/ruff format .             # отформатировать
```

После правки `.po` обязательно перекомпилировать `.mo` (тест `test_i18n.py` —
побайтовый drift guard):

```bash
msgfmt --check -o src/slopcount/locale/ru/LC_MESSAGES/slopcount.mo \
  src/slopcount/locale/ru/LC_MESSAGES/slopcount.po
```

Скачивание модели для `--perplexity`:
```bash
.venv/bin/python -m slopcount.download_model
```
