# Выпуск версии

Релиз = тег `v*` на `main`. Публикация полностью автоматизирована:
`.github/workflows/release.yml` по тегу собирает sdist+wheel, гонит
`twine check`, проверяет содержимое wheel, сверяет тег с версией в
`pyproject.toml` и публикует в PyPI через trusted publishing (OIDC,
без токенов).

## Шаги

1. **main зелёный**: ci.yml прошёл, локальные проверки из
   [CONTRIBUTING.md](CONTRIBUTING.md) чистые.
2. **Бамп версии в двух местах, синхронно**:
   - `pyproject.toml` → `version = "0.2.0"`
   - `src/slopcount/__init__.py` → `__version__ = "0.2.0"`

   Релизный workflow сверяет тег с pyproject и падает при расхождении.
3. **README en/ru**: если менялось что-то пользовательское (флаги, формулы,
   примеры вывода) — обновить обе зеркальные версии.
4. **Коммит и пуш** в `main`.
5. **Тег и пуш тега**:
   ```bash
   git tag -a v0.2.0 -m "slopcount 0.2.0"
   git push origin v0.2.0
   ```
6. **Наблюдать**: GitHub → Actions → `release` (build ~15 с, publish ~20 с).
   Публикация не гоняет тесты — они должны быть зелёными до тега (шаг 1).
7. **Проверить публикацию**:
   ```bash
   python3 -m venv /tmp/relcheck && /tmp/relcheck/bin/pip install --quiet slopcount==0.2.0
   /tmp/relcheck/bin/slopcount --version   # slopcount 0.2.0
   rm -rf /tmp/relcheck
   ```

## Если publish упал

- Пере-запустить **только publish job** («Re-run failed jobs»), не
  «Re-run all»: v4-артефакты immutable, повторный build упадёт на
  конфликте имён артефакта `dist`.
- **Ретег той же версии невозможен** — PyPI immutable. Если версия уже
  опубликовалась с проблемой, следующий выпуск — патч-версия
  (`0.2.1`), тег `v0.2.0` не передвигается.

## Одноразовая настройка (уже выполнена, для справки)

- GitHub: Settings → Environments → создано окружение `pypi`.
- PyPI: аккаунт с 2FA → Account settings → Publishing → pending publisher:
  project `slopcount`, owner `echernyshev`, repo `slopcount`,
  workflow `release.yml`, environment `pypi`.
