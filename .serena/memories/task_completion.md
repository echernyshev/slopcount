# Task completion

Задача считается завершённой, когда пройдены все проверки:

```bash
.venv/bin/python -m pytest tests/ -q        # все тесты зелёные
.venv/bin/ruff check .                      # линтер чист
.venv/bin/ruff format --check .             # формат чист
```

Если трогался `src/slopcount/locale/ru/LC_MESSAGES/slopcount.po` — перекомпилировать `.mo`
и убедиться в побайтовом совпадении (см. `mem:suggested_commands`, drift guard в `test_i18n.py`).

Полезный smoke: `.venv/bin/slopcount tests/fixtures/slop_project --details` —
детекция на эталонном слопе должна давать осмысленные улики.
