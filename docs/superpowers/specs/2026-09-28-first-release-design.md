# Первый публичный релиз 0.1.0: README, PyPI, слияние в main

Дата: 2026-09-28. Ветка: `slopcount-design` (183 коммита поверх `main`,
в main — только «first commit»). Версия в pyproject сейчас 0.5.0 — история
0.1→0.5 жила только в ветке, снаружи не видна.

## 1. Контекст и цель

Инструмент функционально готов (пять редизайнов, ревью пройдены, шкалы
откалиброваны по эталонным репо). Настало время первого публичного релиза:

1. **README переписать полностью** — это не шуточное приложение, а
   инструмент с долей юмора. Из README убрать всю шуточность; описать
   концепцию и проблематику (зачем приложение существует); кратко и
   структурно расписать метрики с расшифровкой, как считаются; первым
   разделом — быстрый старт.
2. **Опубликовать в PyPI** — установка и запуск буквально в 1–2 команды.
3. **Слить ветку в main одним коммитом**, выпустить тег, опубликовать
   утилиту.

Имя `slopcount` на PyPI свободно (проверено 2026-09-28, 404 на
pypi.org/pypi/slopcount/json). Репозиторий GitHub публичный.

## 2. Решённые решения (утверждены в брейншторминге)

| Вопрос | Решение |
|---|---|
| Язык README | Английский `README.md` + зеркальный `README.ru.md`, взаимные ссылки в шапках |
| Версия релиза | **0.1.0** — первая нестабильная; версию в pyproject опускаем с 0.5.0 |
| Публикация | GitHub Actions + Trusted Publishing (OIDC, без токенов) |
| Пример вывода | Отрывок в тексте + полный отчёт в сворачиваемом `<details>` |
| Благодарности | Раздел Acknowledgements в конце со ссылкой на [scc](https://github.com/boyter/scc) |
| Подход | README + метаданные + релизный пайплайн + закрытие хвостов (sha256 scc в CI, build-job) |

## 3. README.md (en) — структура

```
# slopcount
SLOC is what you paid to write. SLOP is what you must now read.
(badges: PyPI version · python 3.11+ · CI · MIT)

## Quick Start          ← первый раздел
  pipx install slopcount   # или pip install slopcount
  slopcount .
  (первый запуск сам скачивает scc ~7 МБ в ~/.cache/slopcount;
   свой бинарник — --scc-path / SLOPCOUNT_SCC_BIN)
  Рядом: --evidence (улики: файл, строка, сниппет, правило), --json (CI)

## Why slopcount        ← концепция и проблематика, серьёзно
  Генерация стала почти бесплатной, понимание — нет. Агенты пишут всё
  большую долю кодовых баз; слоп (текучий уверенный низкоценностный текст)
  накапливается. sloccount/COCOMO отвечали «сколько стоило написать?» —
  вопрос устарел; актуальный — «сколько стоит понять?» (SLOCOMO).
  Абзац честности: детекция честная (регексы, cognitive complexity
  Кэмпбелла, скорость чтения Brysbaert), шутливые только единицы
  (кофе, терапия, GPU-часы сожаления). Каждая улика объяснима.

## The Report           ← метрики кратко и структурно
  Volume: SLOC / files / docs / comments (считает scc: 366 языков, 251 из них — код).
  Три доли со своими шкалами:
    SLOP/SLOC    CLEAN<0.005<TRACE<0.10<NOTICEABLE<0.30<HEAVY<1.0<INFESTED
    MD/SLOC      HUMAN<0.05<NEURO_CLOUD<0.35<…<RECURSION≥1.0
                 (ориентиры: django 0.0005, flask 0.015, requests 0.34)
    comment/SLOC ASCETIC<0.05<DOCUMENTED<0.30<CHATTY<…<COMMENT_DRIVEN
  Comprehension effort: доки (слова/238 wpm × 2.3) + код (200 SLOC/ч) +
    комментарии (~6 слов/строку) + cognitive × 0.5 мин.
  Cost ladder: COCOMO (написать) / LOCOMO (перегенерировать LLM-ом) /
    SLOCOMO (понять: часы × (1+slop) × ставка × overhead, команда 1–21
    Фибоначчи). В долларах написание обычно доминирует, перегенерация почти
    бесплатна; понимание меньше, но повторяется на каждого, кто приходит
    в проект.
  Detected slop: 5 категорий (prose/docs/style/history; agency-маркеры
    НЕ в счёт слопа).

## Example Output       ← отрывок (лестница + шкала с баром) + <details>
                         с полным отчётом по fixture-проекту из тестов

## Configuration        ← --lang en|ru, --rules TOML (переклассификация
                           языков), --scc-path, --perplexity extra

## CI Gate              ← jq-пример с нюансом inf→null (// 9)

## Acknowledgements     ← вся черновая работа делегирована scc Бена
                           Бойтера; поклон и благодарность + ссылка

## License              ← MIT
```

**Удаляется из текущего README:** Perl-шутка, «Врачу: исцелись сам»,
самоскан как витрина, история версий 0.2/0.4/0.5 (снаружи не существует),
подзаголовок «шутка, которую можно поставить в пайплайн» → «CI Gate».

**Тон:** нейтральный технический текст. Юмор живёт только в единицах
вывода инструмента (кофе/терапия) — их не сопровождаем шутливыми
комментариями. Тэглайн в шапке сохраняется: он точен, это не клоунада.

**README.ru.md:** полный зеркальный перевод;
`[English](README.md) | [Русский](README.ru.md)` в шапках обоих файлов.

## 4. Метаданные

`pyproject.toml`:
- `version = "0.1.0"`; `src/slopcount/__init__.py`: `__version__ = "0.1.0"`
  (тест версии читает динамически — не сломается)
- description: `Detect AI slop in a codebase and estimate the cost of
  comprehending it` (убрать «A loving sloccount parody»)
- keywords: убрать `parody`; итог: `sloc, sloccount, ai, llm, slop,
  code-quality, cocomo, cognitive-complexity`
- classifiers: добавить `Programming Language :: Python :: 3.12`, `3.13`,
  `Topic :: Software Development :: Quality Assurance`

## 5. release.yml (новый workflow)

```yaml
name: release
on:
  push:
    tags: ["v*"]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5   # 3.12
      - run: pip install build twine
      - run: python -m build
      - run: twine check dist/*
      - uses: actions/upload-artifact@v4  # dist/
  publish:
    needs: build
    runs-on: ubuntu-latest
    environment: pypi
    permissions:
      id-token: write
    steps:
      - uses: actions/download-artifact@v4
      - uses: pypa/gh-action-pypi-publish@release/v1
```

**Одноразовая ручная настройка (пользователь в браузере):**
1. PyPI: верифицировать email + 2FA → Account settings → Publishing →
   Add pending publisher: project `slopcount`, owner `echernyshev`,
   repo `slopcount`, workflow `release.yml`, environment `pypi`
2. GitHub: Settings → Environments → создать окружение `pypi`

## 6. ci.yml — закрытие хвостов прошлой сессии

- Шаг скачивания scc 4.1.0: добавить `sha256sum -c` с хешем **из зашитой
  таблицы `scc.py`** (Linux x86_64) — один источник правды с рантаймовой
  автозагрузкой.
- Новый job `build` на каждый пуш/PR: `python -m build` + `twine check` +
  ассерты содержимого wheel: есть `slopcount.mo`, `rules/languages.toml`,
  `rules/phrases_*.toml` (ловим забытую локаль/правила до релиза).

## 7. Локальная верификация перед мерджем

1. `ruff check .` + `ruff format --check .` + полный `pytest tests/ -q`
   (включая e2e с настоящим scc).
2. `python -m build` → инспекция содержимого wheel и sdist (locale, rules).
3. Чистый venv: `pip install dist/*.whl` → `slopcount --version`,
   самоскан, fixture с `--evidence`, `--lang ru`.
4. Проверка первого запуска: пустой кеш `~/.cache/slopcount`, scc не в
   PATH → авто-скачивание работает (обещание «1–2 команды» — правда).
5. Установка из sdist во втором чистом venv (sdist собирается без
   репозитория).

## 8. Релизная последовательность

1. Все коммиты работы — на ветке `slopcount-design`.
2. Финальный прогон тестов.
3. **Пауза-гейт: чеклист финальных проверок с пользователем.** Прежде чем
   что-либо сливать, агент останавливается и выдаёт чеклист; каждый пункт
   подтверждается пользователем (или агент показывает доказательство):
   - [ ] полный прогон зелёный — вывод `pytest`, `ruff check`,
         `ruff format --check` показан, а не обещан;
   - [ ] локальная верификация §7 выполнена: wheel и sdist собраны,
         установка в чистые venv прошла, авто-скачивание scc работает,
         `--lang ru` и `--evidence` живы;
   - [ ] `README.md` и `README.ru.md` прочитаны пользователем;
   - [ ] финальный `pyproject.toml` просмотрен (версия 0.1.0,
         description, classifiers);
   - [ ] workflows просмотрены (`release.yml`, изменённый `ci.yml`);
   - [ ] дифф сквоша показан: `git diff main...slopcount-design --stat`
         — пользователь видит, что именно уйдёт в единый коммит;
   - [ ] текст единого коммита и сообщение тега утверждены пользователем;
   - [ ] на стороне пользователя: PyPI-аккаунт верифицирован, pending
         publisher создан (§5), окружение `pypi` существует в GitHub.
   Слияние начинается только после закрытия всех пунктов.
4. `git checkout main && git merge --squash slopcount-design` → один
   коммит: subject `slopcount 0.1.0 — detect AI slop, estimate the cost
   of comprehension`, тело на английском — краткое описание инструмента
   (коммит публичный).
5. Аннотированный тег `v0.1.0`, сообщение: `slopcount 0.1.0`.
6. `git push origin main v0.1.0` — с явного подтверждения пользователя.
7. CI на main; тег запускает release.yml → публикация в PyPI (после
   шага §5).
8. Верификация публикации: `pip install slopcount` из PyPI в чистом venv,
   запуск.
9. Опционально: `gh repo edit --add-topic sloc,llm,ai,code-quality`;
   ветку `slopcount-design` не удаляем.

## 9. Вне рамок

- Поведение инструмента и формат вывода не меняются (никаких правок
  детекторов/метрик/рендера).
- Двухъязычность README не автоматизируется (нет синк-проверки en/ru) —
  сопровождение ручное, осознанное решение.
- CHANGELOG-файл не заводим: 0.1.0 — первая публичная точка.
