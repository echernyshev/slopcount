# slopcount

**SLOC — это то, за что ты заплатил, написав. SLOP — это то, что ты теперь обязан прочитать.**

[![PyPI](https://img.shields.io/pypi/v/slopcount.svg)](https://pypi.org/project/slopcount/)
[![Python](https://img.shields.io/pypi/pyversions/slopcount.svg)](https://pypi.org/project/slopcount/)
[![CI](https://github.com/echernyshev/slopcount/actions/workflows/ci.yml/badge.svg)](https://github.com/echernyshev/slopcount/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/pypi/l/slopcount.svg)](LICENSE)

[English](README.md) · [Русский](README.ru.md)

`slopcount` сканирует проект, детектирует LLM-слоп и оценивает, сколько проект
стоит *понять* — идейный наследник классического
[`sloccount`](https://www.dwheeler.com/sloccount/), который оценивал, сколько код
стоит *написать*.

## Быстрый старт

```bash
pipx install slopcount     # или: pip install slopcount
slopcount .
```

Это всё. При первом запуске slopcount скачивает бинарник
[`scc`](https://github.com/boyter/scc) (~7 МБ) в `~/.cache/slopcount/` и
кеширует его (скачивание пропускается, если подходящий scc ≥ 4.1.0 уже есть
в PATH).
Свой бинарник — `--scc-path /путь/к/scc` или переменная окружения
`SLOPCOUNT_SCC_BIN`.

```bash
slopcount . --evidence     # каждая улика: файл, строка, сниппет, правило
slopcount . --json         # машиночитаемый вывод для CI
slopcount . --lang ru      # русский интерфейс
```

## Зачем

Генерация кода LLM стала почти бесплатной. Понимание — нет: человеку — или
агенту, сжигающему токены — по-прежнему приходится читать каждую строку, а
агенты пишут всё большую долю мирового кода. Попутно накапливается слоп:
гладкий, уверенный, малоценный текст. Комментарии, пересказывающие код.
Докстринги, объясняющие сигнатуру и ничего кроме неё. Документация,
сгенерированная по требованию, которую никто не просил и никто не поддерживает.

Классическая оценка отвечала на вопрос *«сколько это стоило написать?»*
(sloccount, COCOMO). Почти бесплатная генерация делает этот вопрос
устаревшим. Вопрос, который важен теперь: *«сколько стоит это понять?»* — для
инженера, приходящего в проект, для ревьюера, для агента, который будет это
расширять. slopcount отвечает на него:

- детектирует слоп-маркеры в комментариях, докстрингах и markdown-доках —
  каждая улика объяснима: файл, строка, сниппет, правило;
- оценивает усилие чтения всего проекта — доки, код, комментарии, когнитивная
  сложность — по опубликованным скучным формулам;
- ставит рядом три стоимости: написать всё дерево с нуля (COCOMO),
  перегенерировать LLM-ом (LOCOMO), понять (SLOCOMO).

Детекция честная — регулярные выражения, когнитивная сложность Кэмпбелла,
исследования скорости чтения Brysbaert. Формулы публичны. Шутливые только
единицы (кофе, терапия, GPU-часы сожаления) — арифметика за ними настоящая.

## Отчёт

### Объём

Обход дерева и подсчёт — задача [`scc`](https://github.com/boyter/scc): 366
языков (251 из них — код), настоящая семантика `.gitignore` (с отрицаниями),
детект языка по shebang. Каждый файл относится к одному из четырёх классов, и
класс определяет его судьбу:

| Класс | Примеры | Детекция слопа | Роль в метриках |
|---|---|---|---|
| **code** | Python, C, Makefile, SQL | стиль + фразы в комментариях | единственный источник SLOC, комментариев и сложности |
| **markdown** | `.md`, `.markdown` | bloat + фразы | строки доков; заражённые строки — в SLOP |
| **prose** | простой текст | фразы | слова — в оценку времени чтения |
| **data** | JSON, YAML, TOML, XML… | — | не читается; строки всё же идут в оценки COCOMO/LOCOMO |

Граница — «читает ли человек это, чтобы понять программу»: Makefile — код (там
логика), JSON — данные (там декларации). Нужна другая классификация для вашего
проекта — см. [`--rules`](#конфигурация).

### Три доли, три шкалы

| Доля | Смысл | Шкала |
|---|---|---|
| **SLOP/SLOC** | детектированный слоп на строку кода | CLEAN < 0.005 · TRACE < 0.10 · NOTICEABLE < 0.30 · HEAVY < 1.0 · INFESTED |
| **MD/SLOC** | строки markdown на строку кода | HUMAN < 0.05 · NEURO_CLOUD < 0.35 · ESTABLISHED_SLOP < 0.50 · AGENT_SELF_SERVICE < 0.75 · AGENT_OCCUPATION < 1.00 · RECURSION |
| **comment/SLOC** | комментарии на строку кода | ASCETIC < 0.05 · DOCUMENTED < 0.30 · CHATTY < 0.60 · LECTURE_NOTES < 1.00 · COMMENT_DRIVEN |

Границы шкал откалиброваны по эталонным репозиториям: django — MD/SLOC 0.0005 и
flask — 0.015 (HUMAN), requests — 0.34 (NEURO_CLOUD). Граница CLEAN/TRACE для
SLOP — середина единственного измеренного разрыва между человеческими
репозиториями (~0.0025) и слоп-эталонами (~0.0071).

**Как считается SLOP:** уникальные `(файл, строка)` улики по категориям
prose/docs/style/history плюс `round(строки × 0.8)` за каждый markdown-файл,
помеченный как заражённый (гигант: > 500 строк или плотность маркеров > 0.1 на
строку).

### Усилие понимания (на человека)

| Компонента | Формула |
|---|---|
| Чтение документации | слова ÷ 238 сл/мин × 2.3 (штраф технического текста) |
| Чтение кода | 200 SLOC в час |
| Чтение комментариев | ~6 слов на строку комментария |
| Когнитивная обработка | когнитивная сложность × 0.5 мин за балл |

### Лестница затрат

| Модель | Вопрос | Как |
|---|---|---|
| **COCOMO** | сколько стоило бы *написать* всё дерево? | классические 2.4·K^1.05 человеко-месяцев по всем строкам |
| **LOCOMO** | сколько стоит *перегенерировать* LLM-ом? | оценка токенов scc (in+out): генерация + часы ревью |
| **SLOCOMO** | сколько стоит *понять*? | часы чтения × (1 + доля слопа) → человеко-месяцы × ставка × overhead; команда 1–21 (Фибоначчи) |

По долларам написание обычно доминирует, перегенерация почти бесплатна.
Понимание — между ними, но, в отличие от разовых затрат на написание, оно
повторяется: его платит снова каждый инженер и каждый агент, приходящий
в проект.

### Детектированный слоп

Улики делятся на пять категорий. Четыре идут в SLOP: **prose**
(комментарии/докстринги), **docs** (markdown), **style** (стиль кода),
**history** (git). **Agency**-маркеры (`CLAUDE.md`, `.claude/`, …)
выводятся, но не считаются: агенты в репозитории — факт, а не обвинение.

## Пример вывода

Fixture-проект из тестов (`slopcount --lang en tests/fixtures/slop_project`):

```
COCOMO  write the whole tree (docs count as code) = $ 352 (0.0 person-months · 0.7 mo · 0.0 people)
LOCOMO  regenerate it with an LLM                = $ 0.01 (0.0 h + 0.0 h review)
SLOCOMO comprehend the project                   = $ 25 (0.1 h reading · 0.0 person-months) — per person

Slop-to-Code Ratio (SLOP/SLOC)                          = 2.000 [████████████████████] 200.0% INFESTED
```

<details>
<summary>Полный отчёт</summary>

```
PROJECT VOLUME
-------------------------------------------------------------------------------
Code by language:                                files           SLOC
Python                                               2              8
-------------------------------------------------------------------------------
Total SLOC                                              = 8
Files in scan                                           = 4
Documentation                                           = 12 lines (2 files)
Documentation-to-Code Ratio (MD/SLOC)                   = 1.500 [████████████████████] 150.0% RECURSION
                                                         You ran slopcount inside slop. Recursion
Comments                                                = 12 lines
Comments-to-Code Ratio (comment/SLOC)                   = 1.500 [████████████████████] 150.0% COMMENT_DRIVEN
                                                         Comment-driven development. The code is an attachment
Detected SLOP                                           = 16 lines
Slop-to-Code Ratio (SLOP/SLOC)                          = 2.000 [████████████████████] 200.0% INFESTED
                                                         Full slop infestation. Call the exterminators
COMPREHENSION EFFORT & COST
-------------------------------------------------------------------------------
Reading documentation                                   = 0.0 h  (43 words / 238.0 wpm × 2.3)
Reading code                                            = 0.0 h  (8 SLOC / 200.0 per hour)
Reading comments                                        = 0.0 h  (72 words, lines × 6 estimate)
Cognitive processing                                    = 0.1 h  (7 points × 0.5 min)
Total reading time                                      = 0.1 h

-------------------------------------------------------------------------------
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

Team Comprehension Cost (headcount × per person)
    1 person = 0.0 person-months · $ 25
    2 people = 0.0 person-months · $ 49
    3 people = 0.0 person-months · $ 74
    5 people = 0.0 person-months · $ 123
    8 people = 0.0 person-months · $ 196
   13 people = 0.0 person-months · $ 319
   21 people = 0.0 person-months · $ 515

Comprehension Tokens (LOCOMO round-trip: in + out)      = 2,775
Context Windows Consumed                                = 0.0139 × 200K / 0.0028 × 1M
GPU-hours of Regret                                     = 0.0077

Coffee Required                                         = 1 cup ($ 4.00)
Therapy Recommended                                     = 1 session ($ 150.00)
DETECTED SLOP
-------------------------------------------------------------------------------
Totals grouped by slop origin (dominant slop source first):
-------------------------------------------------------------------------------
Origin                           files    slop lines    slop %  cognitivity
-------------------------------------------------------------------------------
Prose (comments/docstrings)          2             3      18.8  high      
Markdown specs                       1             2      12.5  medium    
Code style                           1             2      12.5  medium    
Git history                          0             0       0.0  low       
Environment markers                  1             —         —  —         
-------------------------------------------------------------------------------
Top slop files:  README.md 13 lines · src/defensive.py 2 lines · src/greeter.py 1 line
Agents detected (not counted as slop): CLAUDE.md
Run with --evidence to see every finding with its source line.
```

</details>

## Конфигурация

| Опция | Смысл |
|---|---|
| `--lang en\|ru` | язык интерфейса |
| `--rules ФАЙЛ` | TOML: переклассификация `[languages]` + фразы `[[rule]]` (повторяемый) |
| `--scc-path ПУТЬ` / `SLOPCOUNT_SCC_BIN` | свой бинарник `scc` |
| `--personcost USD` | месячные затраты на человека для оценок (по умолчанию 4690.5) |
| `--overhead X` | множитель накладных расходов для COCOMO и SLOCOMO (по умолчанию 2.4) |
| `--coffee-price USD`, `--no-therapy` | настройка шутливых единиц |
| `--history N` | также сканировать git-историю на N коммитов |
| `--perplexity` | детектор перплексии на GPT-2 (см. ниже) |

Переклассифицировать язык для своего проекта без правки кода:

```toml
# my-rules.toml — запуск: slopcount --rules my-rules.toml .
[languages]
"AsciiDoc" = "markdown"   # считать документацией
"SQL" = "data"            # считать данными, не кодом
```

**Детектор перплексии** (опционально, локальная GPT-2): контекстная
перплексия, посчитанная по предложениям; медиана < 40 помечает машинно-гладкую
прозу:

```bash
pipx install 'slopcount[perplexity]'
python -m slopcount.download_model   # скачивает GPT-2 один раз
slopcount . --perplexity
```

## CI-гейт

`slopcount` возвращает 0 при успехе и 2 при ошибках; гейт — по JSON-отчёту:

```bash
slopcount . --json | jq -e '(.slop.ratio // 9) < 0.05' > /dev/null || echo "too much slop"
```

`// 9` важно: репозиторий только с доками отображает `inf` как `null` в JSON, и
голое `null < 0.05` посчиталось бы истиной — `// 9` превращает null в 9, и гейт
уходит в ошибку.

## Благодарности

Вся черновая работа — обход дерева, подсчёт строк, комментариев и сложности,
COCOMO и LOCOMO — делегирована [scc](https://github.com/boyter/scc) Бена
Бойтера. slopcount существует потому, что существует scc. Наш поклон.

## Лицензия

MIT — см. [LICENSE](LICENSE).
