# Слоуккаунт 0.5.0: редизайн оценок и отчёта (comprehension redesign)

Дата: 2026-09-27. Ветка: `slopcount-design` (поверх делегирования scc 0.4.0).

## 1. Контекст и проблема

Текущий отчёт смешивает три несводимые вещи в одном списке строк, а SLOCOMO
завязан на объём, пойманный детекторами:

1. **SLOCOMO занижен.** `reading_hours` и `person_months` считаются от
   `prose_words` (слова, отмеченные детекторами) и cognitive только
   слоп-кода. Детекторы ловят мало (naumen-smp-mcp: 271 строка слопа при
   93 356 строках доков) — «стоимость осознания» получается смехотворной
   (22.8 ч на проект, где только доков 93K строк).
2. **`context_windows_*` и `gpu_hours`** считаются от того же пойманного
   объёма (`prose_words × 1.33`), хотя по смыслу — это про весь проект и
   ближе к LOCOMO, где токены уже посчитаны scc.
3. **UX отчёта инвертирован**: пользователь должен сначала оценить объём и
   сложность проекта, и только потом лезть с микроскопом к детекциям;
   сегодня таблица детекций идёт первой.
4. **Общий вердикт** от MD/SLOC — синтетика при трёх независимых ratio.

UX-модель нового отчёта: **объём → сложность и стоимость понимания →
детектированный слоп под микроскопом**.

## 2. Решение — обзор

- Три секции текстового отчёта: *Project Volume*, *Comprehension Effort &
  Cost*, *Detected Slop*. Модель данных — композит из трёх блоков
  (`VolumeStats`, `SlopStats`, `ComprehensionStats`), конвейер `run()`
  фазируется явно.
- `reading_hours` отражает **реальный объём проекта**: чтение доков,
  комментариев, кода + когнитивная обработка (cognitive всего проекта).
- SLOCOMO: `person_months = reading_hours/152 × (1 + slop_ratio)` — честная
  база чтения, пойманный слоп удорожает понимание.
- Стоимость понимания считается **на одного человека** и подписывается так
  в отчёте; рядом — шкала для команды (1/2/3/5/8/13/21 человек, ряд
  Фибоначчи): comprehension не параллелится — каждый читает всё сам,
  команда умножает деньги и суммарные человеко-месяцы, но не календарное
  время чтения.
- Токены понимания берутся из LOCOMO (`input + output`), контекстные окна
  и GPU-часы — от них.
- Три самостоятельные шкалы (doc/code, comment/code, slop/code) вместо
  общего вердикта; категория рендерится у каждой метрики.
- Все три стоимостные метрики получают единую структуру корзин
  docs / source code (код + комментарии) / data: деньги + усилие
  (человеко-месяцы/часы); календарный schedule только на уровне total.
- Терминология: везде **comprehension** (в русской локали — «понимание»),
  вместо «awareness/осознание».
- Флаги: `--details`, `--fail-above`, `--verdict-only` удаляются;
  добавляется `--evidence` (улики с текстом исходных строк). Утилита
  становится чисто информативной; CI-гейтинг — обёрткой поверх `--json`.

Не входит в скоуп: состав детекторов и их категорий, реестр детекторов,
perplexity-режим, механика делегирования scc.

## 3. Модель данных

Новые блоки (живут в `evidence.py`; если он распухнет — вынести в
`stats.py`, решение за реализацией):

```python
@dataclass
class LanguageRow:
    language: str        # display-имя scc
    files: int
    sloc: int            # Σ Code по kind=code файлам языка

@dataclass
class VolumeStats:                  # секция 1
    sloc: int                       # Σ Code, kind=code
    comment_lines: int              # Σ Comment, kind=code
    files_total: int                # весь манифест scc (включая data)
    languages: list[LanguageRow]    # сортировка по sloc desc
    md_files: int                   # .md/.markdown (как сейчас)
    md_lines: int
    md_words: int                   # честный Σ слов текста kind=markdown+prose
    md_sloc_ratio: float            # md_lines/sloc, inf-семантика как сейчас
    comment_sloc_ratio: float

@dataclass
class SlopStats:                    # секция 3
    total: int                      # SLOP: улики (prose/docs/style/history)
                                    # + round(строки × 0.8) заражённых md
    ratio: float                    # total/sloc
    infected_md_lines: int
    categories: dict[Category, CategoryTotals]
    top_files: list[tuple[str, int]]   # топ-5 путей по слоп-строкам
    agency: list[Evidence]          # AGENCY не входит в SLOP (без изменений)
    details: list[Evidence]

@dataclass
class ComprehensionStats:           # секция 2 (= SLOCOMO на новой концепции)
    reading_hours: float
    reading_components: dict[str, float]   # docs/code/comments/cognitive, часы
    person_months: float
    person_years: float
    schedule_months: float          # 2.5·person_months^0.38 — шутка-структура COCOMO
    therapists: float
    cost: float                     # person_months · personcost · overhead
                                    #   — НА ОДНОГО человека (per person)
    team_costs: list[tuple[int, float, float]]   # (человек, person-months, $) для TEAM_SIZES
    comprehension_tokens: float | None    # locomo.input+output; None → «—»
    context_windows_200k: float | None
    context_windows_1m: float | None
    gpu_hours: float | None
    coffee_cups: int
    coffee_cost: float
    therapy_sessions: int           # 0 при --no-therapy
    therapy_cost: float
```

`Report` = `scan`-поля (root, scc_version, skip_count, history_commits) +
`volume: VolumeStats` + `slop: SlopStats` + `cocomo`/`locomo` (из scc) +
`cocomo_breakdown`/`locomo_breakdown` (см. §6) + `slocomo:
ComprehensionStats`. Плоские дубли (`report.sloc`, `report.slop`,
`report.categories`, …) удаляются; потребители — рендеры, JSON, тесты.

`SlocomoResult` в `metrics/slocomo.py` переименовывается в
`ComprehensionStats` (или переезжает в модель данных — за реализацией;
одно имя, одно место).

## 4. Конвейер

Фазы `app.py:run()` — явные, под секции отчёта:

1. **collect** — один вызов `scc.collect()` (без изменений).
2. **volume** — агрегация манифеста: языки (только kind=code), SLOC,
   комментарии, md-строки; в файловом цикле — честный `md_words` из
   текста kind=markdown+prose.
3. **detect** — тот же проход по файлам, детекторы как сейчас (состав не
   меняем); копятся Evidence[] и infected.
4. **aggregate** — `SlopStats`: категории, top-5 файлов, SLOP/ratio.
5. **comprehension** — `metrics/slocomo.py:compute()` + разбивки
   `metrics/costs.py` (§6).
6. **render** — три секции + `--evidence`.

Фазы 2–3 остаются одним физическим проходом по файлам (I/O не
дублируется), но счётчики объёма и улики накапливаются раздельно.

## 5. Формулы

### 5.1. reading_hours — время понимания проекта

```
reading_hours = docs_words/(238·60)·2.3     # доки: слова markdown+prose,
                                            #   238 wpm × 2.3 (перечитывают)
             + comment_lines·6/(238·60)     # комментарии: слова ≈ строки×6
             + sloc/200                     # код: темп понимания 200 SLOC/ч
             + cognitive_total·0.5/60       # когнитива: 0.5 мин/балл,
                                            #   по всему проекту
```

Константы (`metrics/slocomo.py`):

| константа | значение | статус/якорь |
|---|---|---|
| `WPM` | 238 | существующая (средняя скорость чтения прозы) |
| `REREAD` | 2.3 | существующая (доки перечитывают) |
| `COMMENT_WORDS_PER_LINE` | 6 | новая, документированная аппроксимация: экстракторы знают 31 язык, оценка единообразна для всех |
| `SLOC_PER_HOUR` | 200 | новая: темп понимания, не пролистывания; ревью-практики дают 200–400 LOC/ч как верхнюю границу |
| `COG_MINUTES` | 0.5 | существующая; теперь по `cognitive_total`, не только слоп-коду |
| `HOURS_PER_PERSON_MONTH` | 152 | новая: стандарт COCOMO II (19 дней × 8 ч) |
| `TEAM_SIZES` | [1, 2, 3, 5, 8, 13, 21] | новая: ряд Фибоначчи для шкалы команды |

`TOKENS_PER_WORD` удаляется — токены больше не считаем от prose_words.

Каждая компонента хранится в `reading_components` и рендерится с
расшифровкой входа (слова/SLOC/баллы) — «показываем на цифрах».

### 5.2. SLOCOMO

```
person_months = reading_hours/152 × (1 + slop_ratio)   # чтение × слоп-множитель
schedule      = 2.5 · person_months^0.38               # календарные месяцы (mo), шутка-структура COCOMO
therapists    = person_months / schedule               # guard: 0 при schedule=0
cost          = person_months · personcost · overhead  # НА ОДНОГО человека
team_cost(N)  = N · cost                               # команда: каждый осознаёт сам;
                                                       #   суммарные человеко-месяцы = N · person_months
```

`person_months` (человеко-месяцы) — *усилие*: месяцы работы одного
человека; из них выводится стоимость. Не путать с `schedule` (mo) —
*календарной длительностью* при команде `therapists` человек (340
человеко-месяцев ≈ 14.8 человек × 22.9 месяцев); см. §6.4.

Все величины SLOCOMO — в расчёте **на одного человека**. Понимание не
параллелится: каждый из N членов команды читает проект целиком сам,
поэтому команда из N умножает стоимость и суммарные человеко-месяцы на
N, а календарное время чтения остаётся `reading_hours`. Шкала команды —
`TEAM_SIZES` (Фибоначчи: 1/2/3/5/8/13/21), в отчёте и JSON —
`team_costs`. Шуточные интерпретации (кофе, терапия) остаются
подушевыми.

Шуточные интерпретации (производные, корректируются автоматически):

```
comprehension_tokens    = locomo.input_tokens + locomo.output_tokens
                          # полный round-trip: прочитать (in) + переизложить (out)
context_windows_200k/1m = tokens / 200_000 / 1_000_000
gpu_hours               = tokens / 100 / 3600      # инференс 100 ток/с
coffee_cups             = ⌈reading_hours/4⌉        # чашка на 4 часа
therapy_sessions        = max(1, ⌈person_months·2⌉); --no-therapy гасит
```

Рёбра: `locomo is None` → `comprehension_tokens`/окна/`gpu_hours` = None,
в тексте `—`; `sloc=0 ∧ slop>0` → `slop_ratio=inf` → person_months/cost=inf →
рендер `∞`; `reading_hours=0` → person_months=0, schedule=0 → therapists=0.

### 5.3. Валидация формул (оценка на утверждении спеки; замер сборки 0.5.0 — naumen-smp-mcp)

| величина | старая | оценка спеки | замер 0.5.0 |
|---|---|---|---|
| reading_hours | 22.8 | ≈433 | 399.2 |
| person-months | 0.62 (2.4·KSLOP^1.05) | ≈2.87 | 2.645 (×(1+0.0071)) |
| cost | ≈$7K | ≈$32K | ≈$29.8K |

Лестница становится осмысленной: LOCOMO $57 ≪ SLOCOMO $32K ≪ COCOMO
$3.83M — «перегенерировать дешевле, чем понять, понять дешевле, чем
написать с нуля».

### 5.4. Проверка COCOMO scc (выполнена, к воспроизведению в тестах)

Вход COCOMO у scc — **только Code-строки всех языков** (комментарии и
пустые строки модель не берут; md считается кодом). На naumen-smp-mcp:
`person_months = 2.4·(111.841)^1.05 = 339.7`; `cost = 339.7·4690.5·2.4 =
$3 825 364` — совпадает с `estimatedCost` scc ($3 825 363.57) до
доллара; schedule 22.9 mo и people 14.84 совпадают. Формула базового
COCOMO organic подтверждена — её реплицируем (§6.1).

## 6. Разбивки стоимостей по корзинам

Корзины — по kind-классификации `languages.toml`, строки из манифеста;
структура **едина** у всех трёх метрик — docs / source code / data, где
строка «source code» несёт итог корзины, а подстроки — только «код» и
«комментарии» (строки «всего» нет):

- **docs** = kind `markdown` + kind `prose` (Code-строки);
- **source code** = **код** (kind `code`, Code-строки) + **комментарии**
  (поле `Comment` у kind=code). Заполнение честное по возможностям
  метрики: вход COCOMO/LOCOMO у scc — только Code-строки, поэтому у них
  итог корзины равен подстроке «код», а «комментарии» — прочерк с пометкой
  «scc их не учитывает»; у SLOCOMO (линейная модель чтения) обе подстроки
  живые, итог = код + комментарии. Для COCOMO вход проверен до доллара
  (§5.4); для LOCOMO — экспериментально 2026-09-27: +100 comment-строк к
  100 Code-строкам не меняют input/output/cost ни на один токен, при
  удвоении Code-строк всё удваивается — токены строго пропорциональны
  Code-строкам;
- **data** = kind `data` (json/yaml/xml/toml/…): scc включает в
  COCOMO/LOCOMO (корзина нужна для сверки с total), но SLOCOMO data-файлы
  не читает — прочерк «не читаем».

Неаддитивность независимых оценок принята осознанно (COCOMO суперлинеен:
2.4·(a+b)^1.05 > 2.4·a^1.05 + 2.4·b^1.05); метод каждой разбивки
подписывается в отчёте.

### 6.1. COCOMO — независимые оценки, репликация формулы

`person_months_i = 2.4·(K_i)^1.05`, `cost_i = person_months_i·wage/12·overhead`,
`K_i` — Code-строки корзины (в тыс.). Считаем в новом `metrics/costs.py`.

**Drift-guard:** на каждом запуске пересчитываем total по реплицированной
формуле из всех Code-строк и сверяем с `estimatedCost` scc; расхождение
>1% — предупреждение в stderr («scc сменил модель COCOMO, разбивка может
отличаться»); в тестах — жёсткий ассерт (фикстура
`tests/fixtures/scc_slop_project.json2` + e2e). Если scc сменит модель —
узнаем сразу, а не соврём молча.

### 6.2. LOCOMO — пропорциональная атрибуция

Модель LOCOMO (токены, циклы, review-часы, ценовые пресеты версий scc)
не реплицируется. Фактические `cost`, `generation_seconds`,
`review_hours` атрибутируются **по долям Code-строк корзин** — аддитивно
ровно к total. Подпись: «вклад по доле строк». Ориентир naumen-smp-mcp:
docs 64.1% / code 34.5% / data 1.3%.

### 6.3. SLOCOMO — точная аддитивная разбивка

Модель линейна по чтению: `cost_i = reading_i/152·(1+slop_ratio)·personcost·overhead`.
Компоненты — docs (слова md+prose), comments, code (SLOC + cognitive);
в единой структуре корзин source_code.total = code + comments (обе
подстроки живые), data — прочерк: data-файлы не читаются.
Сумма корзин **ровно** равна total. Множитель `(1+slop_ratio)` —
глобальный (слоп проекта удорожает понимание в целом).

### 6.4. Время в разбивках

В корзинах — **усилие**, не календарь: COCOMO — человеко-месяцы
(`person_months_i`), LOCOMO — часы (атрибутированные gen+review),
SLOCOMO — часы чтения (`reading_components`). Календарный `schedule` и `people` —
только на уровне total (длительность — свойство параллельной работы
команды, по корзинам не разлагается).

## 7. Шкалы

Три независимые шкалы; категория рендерится у каждой метрики секции 1
(`0.342 [▮▮▮░░] NEURO_CLOUD`), коды — стабильные значения JSON.

| метрика | границы | калибровка (якоря — §14) |
|---|---|---|
| doc/code (MD/SLOC) | 0.05 / 0.35 / 0.50 / 0.75 / 1.0; ≥1.0 → RECURSION | 2026-09-26: django 0.0005, requests 0.34 |
| comment/code | <0.05 / <0.30 / <0.60 / <1.00 / ≥1.00 | 2026-09-27: django 0.151, redis 0.238 → DOCUMENTED; naumen 0.331 → CHATTY; фикстура 1.5 → COMMENT_DRIVEN |
| slop/code | <0.005 / <0.10 / <0.30 / <1.00 / ≥1.00 | 2026-09-27: human-репо ≤0.0025 → CLEAN; naumen 0.0071 → TRACE; фикстура 2.0 → INFESTED |

Коды comment: ASCETIC / DOCUMENTED / CHATTY / LECTURE_NOTES /
COMMENT_DRIVEN; slop: CLEAN / TRACE / NOTICEABLE / HEAVY / INFESTED.
Калибровка 2026-09-27 (§7.1) подтвердила comment-границы и ужесточила
CLEAN по slop с 0.02 до 0.005; тексты статусов не менялись, кроме самого
CLEAN: после ужесточения старый «Detectors found nothing» стал бы
фактической неправдой (в полосе <0.005 человеческие репо несут десятки
улик) — текст заменён на «Slop at human noise level. Either clean or
sneaky».

### 7.1. Процедура калибровки (эмпирическая, разовая, вне CI)

Эталоны: чистые человеческие (sqlite, redis, django), docs-тяжёлые humane
(requests, flask), слоп-эталоны (`tests/fixtures/slop_project`,
`/stg/git/naumen-smp-mcp`). Прогнать scc/slopcount, снять фактические
comment/code и slop/code, границы поставить в естественных разрывах
между классами; итог — таблица в §14 и константы в `scales.py`;
репозитории в CI не нужны.

**Выполнено 2026-09-27** (slopcount 0.5.0, scc 4.1.0; GitHub shallow-клоны
django/django, pallets/flask, psf/requests, redis/redis, sqlite/sqlite;
linux не клонировался — объём/время клона за пределами одного прогона). Итог:

- **comment/code 0.05 / 0.30 / 0.60 / 1.00 — подтверждены без изменений**:
  naumen (0.331) лежит внутри гуманного кластера requests 0.320 /
  sqlite 0.343 / flask 0.415 — естественного разрыва между классами по
  comment/code нет (метрика информационная, на вердикт не влияет);
  единственный сильный разрыв 0.41 → 1.5 черновым границам не
  противоречит.
- **slop/code: CLEAN ужесточен 0.02 → 0.005**: единственный измеренный
  разрыв между классами — flask 0.0025 → naumen 0.0071; граница в середине
  разрыва отделяет слоп-эталон от CLEAN.
  Точек между 0.0071 и 2.0 не измерялось — 0.10 / 0.30 / 1.00 остались
  круглыми черновыми.

### 7.2. `verdicts.py` → `scales.py`

`Verdict` → `Grade`, `_SCALE` → реестр `SCALES: dict[metric, list[(bound,
Grade)]]`, `verdict_for()` → `grade(metric, ratio)`. `progress_bar`
остаётся (мини-бар у ratio; `inf` рендерится пустым баром — как сейчас).
`Verdict`-строка отчёта, `--verdict-only`, `--fail-above`,
`verdict_for(md_sloc_ratio)` в JSON — удаляются.

## 8. Отчёт (текстовый, макет)

```
PROJECT VOLUME
-------------------------------------------------------------------------------
Code by language:                            files            SLOC
Python                                           2               8
-------------------------------------------------------------------------------
Total SLOC                                          = 8 (2 files)
Documentation                                       = 12 lines (2 files)
Documentation-to-Code Ratio (MD/SLOC)               = 1.500 [▮▮▮▮▮] RECURSION
Comments                                            = 12 lines
Comments-to-Code Ratio (comment/SLOC)               = 1.500 [▮▮▮▮▮] COMMENT_DRIVEN
Detected SLOP                                       = 16 lines
Slop-to-Code Ratio (SLOP/SLOC)                      = 2.000 [▮▮▮▮▮] INFESTED

COMPREHENSION EFFORT & COST
-------------------------------------------------------------------------------
Reading documentation     = 0.1 h   (84 words / 238 wpm × 2.3 reread)
Reading code              = 0.0 h   (8 SLOC / 200 per hour)
Reading comments          = 0.1 h   (72 words, lines × 6 estimate)
Cognitive processing      = 0.1 h   (9 points × 0.5 min)
Total reading time        = 0.3 h

Cost Ladder (write / regenerate / comprehend)
-------------------------------------------------------------------------------
COCOMO  write the whole tree (docs count as code) = $ 352 (0.0 person-months · 0.7 mo · 0.0 people)
           docs                   0.0 person-months · $ 170
           source code            0.0 person-months · $ 170
             code                 0.0 person-months · $ 170
             comments               —  (scc does not count comments)
           data                   0.0 person-months · $ 0
LOCOMO  regenerate it with an LLM                = $ 0.01 (0.0 h + 0.0 h review)
           docs                   0.0 h · $ 0.01
           source code            0.0 h · $ 0.01
             code                 0.0 h · $ 0.01
             comments               —  (scc does not count comments)
           data                   0.0 h · $ 0.00
SLOCOMO comprehend the project                   = $ 25 (0.1 h reading · 0.0 person-months) — per person
           (a team multiplies by headcount — see the scale below)
           docs                   0.0 h · $ 2
           source code            0.1 h · $ 23
             code                 0.1 h · $ 22  (incl. cognitive 0.1 h)
             comments             0.0 h · $ 1
           data                     —  (not read)
Team Comprehension Cost (headcount × per person):
   1 person   = 0.0 person-months · $ 25
   2 people   = 0.0 person-months · $ 49
   3 people   = 0.0 person-months · $ 74
   5 people   = 0.0 person-months · $ 123
   8 people   = 0.0 person-months · $ 196
  13 people   = 0.0 person-months · $ 319
  21 people   = 0.0 person-months · $ 515
(числа — фактический вывод фикстуры; эталон — tests/golden/slop_project_en.txt)
Comprehension Tokens               = 1 234 (LOCOMO round-trip: in + out)
Context Windows Consumed           = 0.0061 × 200K / 0.0012 × 1M
GPU-hours of Regret                = 0.0034
Coffee Required                    = 1 cup ($ 4.00)
Therapy Recommended                = 1 session ($ 150.00)

DETECTED SLOP
-------------------------------------------------------------------------------
Origin                        files    slop lines    slop %
Prose (comments/docstrings)       2             3      18.8
Markdown specs                   1             2      12.5
…(таблица категорий — нынешняя, переехавшая сюда целиком)
Top slop files:  README.md 6 · src/defensive.py 4 · …
Agents detected: AGENTS.md, CLAUDE.md — not counted as slop
Run with --evidence to see every finding with its source line.
```

Таблица языков — только kind=code, топ-10 + строка «остальные».
`COCOMO write the whole tree` несёт пояснение входа: scc считает md как
код, включая документацию (чтобы цифра $3.8M не выглядела ошибкой).
`--evidence`: все улики `file:line [CAT] описание → текст исходной строки`
(сниппет дочитывается лениво при рендере, в `Evidence` не хранится).

## 9. Флаги

| флаг | судьба |
|---|---|
| `--details` | удалить (заменён) |
| `--fail-above` | удалить (CI-гейтинг — поверх `--json`) |
| `--verdict-only` | удалить (вердикта нет) |
| `--evidence` | добавить: все улики + текст строк |
| остальные | без изменений |

## 10. JSON (схема 0.5.0)

Ключи английские, стабильные, не локализуются. SLOCOMO не дублируется:
блок `comprehension` и есть он; в `costs` — только внешние модели.

```json
{
  "scan": {"tool": "scc 4.1.0", "files": 850, "skipped": 0, "history_commits": null},
  "volume": {
    "sloc": 38429, "comment_lines": 12717, "complexity": 4386, "cognitive": 12153,
    "md_files": 435, "md_lines": 93356, "md_words": 840000,
    "md_sloc_ratio": 2.4293, "comment_sloc_ratio": 0.3310,
    "languages": [{"language": "Java", "files": 300, "sloc": 30000}],
    "grades": {"doc": "RECURSION", "comment": "CHATTY", "slop": "TRACE"}
  },
  "slop": {"total": 271, "ratio": 0.0071, "infected_md_lines": 140,
            "categories": {}, "top_files": [{"file": "README.md", "lines": 6}]},
  "comprehension": {
    "reading_hours": 433.2,
    "reading_components": {"docs": 135.4, "code": 192.1, "comments": 5.3, "cognitive": 101.3},
    "person_months": 2.87, "person_years": 0.24, "schedule_months": 3.7,
    "therapists": 0.78, "cost_per_person": 32200.0,
    "cost_breakdown": {"docs": 28900.0,
                       "source_code": {"total": 3300.0, "code": 2200.0, "comments": 1100.0},
                       "data": null},
    "team_costs": [{"people": 1, "person_months": 2.87, "cost": 32200.0},
                    {"people": 2, "person_months": 5.74, "cost": 64400.0},
                    {"people": 3, "person_months": 8.61, "cost": 96600.0},
                    {"people": 5, "person_months": 14.35, "cost": 161000.0},
                    {"people": 8, "person_months": 22.96, "cost": 257600.0},
                    {"people": 13, "person_months": 37.31, "cost": 418600.0},
                    {"people": 21, "person_months": 60.27, "cost": 676200.0}],
    "comprehension_tokens": 10562128.4,
    "context_windows_200k": 52.8, "context_windows_1m": 10.6, "gpu_hours": 29.3,
    "coffee_cups": 109, "coffee_cost": 435.0,
    "therapy_sessions": 6, "therapy_cost": 900.0
  },
  "costs": {
    "cocomo": {"cost": 3825363.57, "person_months": 339.7,
                "schedule_months": 22.9, "people": 14.84,
                "breakdown": {"docs": {"lines": 71706, "person_months": 213.0, "cost": 2397000},
                               "source_code": {"total": {"lines": 38639, "person_months": 111.4, "cost": 1253000},
                                               "code": {"lines": 38639, "person_months": 111.4, "cost": 1253000},
                                               "comments": null},
                               "data": {"lines": 1496, "person_months": 3.7, "cost": 41000}}},
    "locomo": {"cost": 57.13, "input_tokens": 8440553.1, "output_tokens": 2120575.3,
                "generation_seconds": 42411.5, "review_hours": 18.64, "cycles": 1.9,
                "preset": "medium",
                "breakdown": {"docs": {"lines": 71706, "hours": 19.5, "cost": 36.6},
                               "source_code": {"total": {}, "code": {}, "comments": null},
                               "data":  {}}}
  },
  "evidence_count": 134
}
```

Единая структура корзин (§6) во всех breakdown: `source_code` несёт итог
и подстроки `total`/`code`/`comments`; у COCOMO/LOCOMO `comments` = `null`
(scc их не считает, итог равен подстроке «код»); у SLOCOMO `data` = `null`
(не читаем). `None`-поля (нет locomo) → `null`. Значения JSON округляются
независимо — суммы под-корзин могут отличаться от `total` на последнюю
цифру (аддитивность — свойство модели, не сериализации).

**CSV** — прежние колонки `file,line,category,weight,description` +
`source` (текст строки улики, обрезка ~120 символов).

## 11. i18n

- Все новые подписи — английские msgid через `_()`; замена терминологии:
  `Cognitive Awareness Effort` → `Comprehension Effort`,
  `SLOCOMO become aware of the slop` → `SLOCOMO comprehend the project`;
  в ru-каталоге «осознание» → «понимание».
- Плюрализм только `ngettext`, интерполяция только `%`-стиль, числа —
  `fmt_int`/`fmt_float`.
- После правки `.po` обязательно `msgfmt` (drift-тест `test_i18n.py`
  проверяет побайтовое совпадение).
- Заголовок po-каталога — версия 0.5.0.

## 12. Версионирование и миграция

Версия **0.5.0**. Breaking changes (в README и changelog):

1. Удалены `--details`, `--fail-above`, `--verdict-only`; добавлен
   `--evidence`.
2. JSON-схема реструктурирована (scan/volume/slop/comprehension/costs);
   `verdict`, старые плоские поля (`slop.total` сохранён, `code.*`
   переехали) — по §10.
3. SLOCOMO: новая семантика (объём проекта, множитель слопа, токены из
   LOCOMO); `person_months = 2.4·KSLOP^1.05` удалена.
4. Общий вердикт удалён; шкалы per-metric.
5. Терминология awareness → comprehension (текст отчёта и msgid).

Golden-файлы (`tests/golden/slop_project_en.txt`) перегенерируются.
CLAUDE.md и README обновляются: конвейер, формулы, команда самоскана,
термин «стоимость понимания».

## 13. Тесты

- **volume**: агрегация языков (топ-10 + остальные), md_words по
  markdown+prose, ratios (включая inf-ветки sloc=0).
- **формулы**: каждая компонента чтения на просчитанных вручную числах;
  person_months/множитель; team_costs = N × (person_months, cost) для всех
  TEAM_SIZES;
  рёбра (reading=0, slop_ratio=inf, locomo=None, cost=inf → вся шкала ∞).
- **metrics/costs.py**: репликация COCOMO сверяется с `estimatedCost`
  фикстуры `scc_slop_project.json2` и e2e (drift-guard, допуск на
  округление); атрибуция LOCOMO суммируется ровно в total; корзины
  SLOCOMO суммируются ровно в total.
- **scales**: границы всех трёх шкал (значение ровно на границе, inf,
  RECURSION при ≥1.0), стабильность кодов.
- **render**: три секции, `--evidence` со сниппетами, `—` для
  невозможных корзин, `∞` для inf.
- **json/csv**: структура-снапшот 0.5.0, `source` в CSV.
- **e2e**: флаги (в т.ч. отсутствие удалённых → typer-ошибка), golden.
- **i18n**: drift-тест побайтово после msgfmt.

## 14. Опорные цифры калибровки (сводка)

Снято 2026-09-27 (slopcount 0.5.0, scc 4.1.0; GitHub shallow-клоны,
`git clone --depth 1`):

| репозиторий | класс | doc/code | comment/code | slop/code |
|---|---|---|---|---|
| django/django | чистый код | 0.0005 | 0.1508 | 0.0015 |
| redis/redis | чистый код | 0.0156 | 0.2378 | 0.0002 |
| sqlite/sqlite | чистый код | 0.0162 | 0.3433 | 0.0005 |
| psf/requests | docs-тяжёлый humane | 0.3135 | 0.3195 | 0.0021 |
| pallets/flask | docs-тяжёлый humane | 0.0146 | 0.4149 | 0.0025 |
| naumen-smp-mcp | слоп | 2.4293 | 0.3309 | 0.0071 |
| tests/fixtures/slop_project | слоп-фикстура | 1.5000 | 1.5000 | 2.0000 |

Колонка doc/code — контроль повторного измерения против спеки
2026-09-26 (django 0.0005, flask 0.015, requests 0.34 — совпало в пределах
дрейфа репозиториев (замер 0.3135);
naumen 0.3309 против 0.3310 — дрейф содержимого репозитория). linux не
клонировался. SQLite по comment/code (0.343) оказался «болтливее»
слоп-эталона naumen — классы по comment/code не разделяются (§7.1).
Границы по разрывам между классами — §7.
