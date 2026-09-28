# First Public Release 0.1.0 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prepare slopcount for its first public release: professional English README + Russian mirror, PyPI metadata for 0.1.0, release pipeline (GitHub Actions + Trusted Publishing), CI hardening, full verification, then squash-merge to main, tag v0.1.0 and publish.

**Architecture:** Documentation and release engineering only — no changes to tool behavior or output. All work happens on branch `slopcount-design`; the release itself (Task 7) is a gated interactive sequence with a user-facing checklist before anything is merged or pushed.

**Tech Stack:** Markdown, TOML (pyproject), GitHub Actions YAML, hatchling/build/twine, pipx.

**Spec:** `docs/superpowers/specs/2026-09-28-first-release-design.md`

**Facts pinned for the implementer:**
- scc 4.1.0 Linux x86_64 sha256 (from the pinned table in `src/slopcount/scc.py:39-42`, single source of truth): `c7328436d3027f4357d3d7853f7dc3ac2bbcb4ca08f1adad91a27c593884079b`
- Fixture report output is deterministic; captured in Task 2 (regenerate and compare before committing)
- Tests do NOT reference the repository README (checked); version test reads `__version__` dynamically
- `.venv` already has `build` 1.6.1 and `PyYAML`; `twine` needs an ad-hoc install
- `.gitignore` already covers `dist/`
- Tooling: `.venv/bin/python`, `.venv/bin/ruff`, `.venv/bin/slopcount`

---

### Task 1: Version 0.1.0 and PyPI metadata

**Files:**
- Modify: `pyproject.toml`
- Modify: `src/slopcount/__init__.py`

- [ ] **Step 1: Update pyproject.toml**

Replace lines 7-20 of `pyproject.toml` (from `version` through the classifiers list) with:

```toml
version = "0.1.0"
description = "Detect AI slop in a codebase and estimate the cost of comprehending it"
readme = "README.md"
requires-python = ">=3.11"
license = "MIT"
authors = [{ name = "Egor Chernyshev" }]
dependencies = ["typer>=0.27,<0.28"]
keywords = ["sloc", "sloccount", "ai", "llm", "slop", "code-quality", "cocomo", "cognitive-complexity"]
classifiers = [
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Programming Language :: Python :: 3.13",
    "Environment :: Console",
    "Topic :: Software Development",
    "Topic :: Software Development :: Quality Assurance",
    "License :: OSI Approved :: MIT License",
]
```

(Everything else in the file stays as is. Changes: version 0.5.0→0.1.0, description loses "A loving sloccount parody", keywords lose `parody` and gain `code-quality`/`cocomo`, classifiers gain 3.12/3.13 and the QA topic.)

- [ ] **Step 2: Bump __version__**

`src/slopcount/__init__.py` — replace its single line with:

```python
__version__ = "0.1.0"
```

- [ ] **Step 3: Verify version flag and metadata**

Run: `.venv/bin/slopcount --version && .venv/bin/python -m pytest tests/test_cli.py -q`
Expected: `slopcount 0.1.0`, then all CLI tests pass (the version test reads `__version__` dynamically).

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml src/slopcount/__init__.py
git commit -m "chore: версия 0.1.0 и публичные метаданные PyPI (без «parody», classifiers 3.11–3.13)"
```

---

### Task 2: README.md — full English rewrite

**Files:**
- Modify: `README.md` (complete replacement)

- [ ] **Step 1: Regenerate the fixture report and compare with the pinned text**

Run: `.venv/bin/slopcount --lang en tests/fixtures/slop_project`
Expected: byte-identical to the report inside `<details>` below (deterministic; if any line differs, use the fresh output — the tool is the source of truth, not this plan).

- [ ] **Step 2: Write the new README.md**

Replace the entire file with:

````markdown
# slopcount

**SLOC is what you paid to write. SLOP is what you must now read.**

[![PyPI](https://img.shields.io/pypi/v/slopcount.svg)](https://pypi.org/project/slopcount/)
[![Python](https://img.shields.io/pypi/pyversions/slopcount.svg)](https://pypi.org/project/slopcount/)
[![CI](https://github.com/echernyshev/slopcount/actions/workflows/ci.yml/badge.svg)](https://github.com/echernyshev/slopcount/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/pypi/l/slopcount.svg)](LICENSE)

[English](README.md) · [Русский](README.ru.md)

`slopcount` scans a codebase, detects LLM-generated slop and estimates what the
project costs to *comprehend* — a spiritual successor to the classic
[`sloccount`](https://www.dwheeler.com/sloccount/), which estimated what code
costs to *write*.

## Quick Start

```bash
pipx install slopcount     # or: pip install slopcount
slopcount .
```

That's it. On first run slopcount downloads the [`scc`](https://github.com/boyter/scc)
counter binary (~7 MB) into `~/.cache/slopcount/` and caches it (skipped when
a suitable scc ≥ 4.1.0 is already on PATH). To use your own build:
`--scc-path /path/to/scc` or the `SLOPCOUNT_SCC_BIN` environment variable.

```bash
slopcount . --evidence     # every finding: file, line, snippet, matched rule
slopcount . --json         # machine-readable output for CI
slopcount . --lang ru      # Russian interface
```

## Why

LLM code generation became nearly free. Comprehension did not: a human — or an
agent burning tokens — still has to read every line, and agents now write a
growing share of the world's code. Along the way, slop accumulates: fluent,
confident, low-value text. Comments that restate the code. Docstrings that
explain the signature and nothing else. Documentation generated on demand that
nobody asked for and nobody maintains.

Classical estimation answered *“what did this cost to write?”* (sloccount,
COCOMO). Generation being nearly free makes that question obsolete. The question
that matters now is *“what does this cost to understand?”* — for the engineer
joining the project, for the reviewer, for the agent about to extend it.
slopcount answers it:

- detects slop markers in comments, docstrings and markdown docs — every
  finding is explainable: file, line, snippet, rule;
- estimates the effort of reading the whole project — docs, code, comments,
  cognitive complexity — from published, boring formulas;
- puts three costs side by side: writing the tree from scratch (COCOMO),
  regenerating it with an LLM (LOCOMO), comprehending it (SLOCOMO).

The detection is honest — regular expressions, Campbell's cognitive complexity,
Brysbaert's reading-speed research. The formulas are public. Only the units are
playful (coffee, therapy, GPU-hours of regret); the arithmetic behind them is
real.

## The Report

### Volume

[`scc`](https://github.com/boyter/scc) does the walking and counting: 366
languages (251 of them code), real `.gitignore` semantics (negations
included), shebang-based language detection. Every file is classified into
one of four kinds, and the kind decides its fate:

| Kind | Examples | Slop detection | Role in metrics |
|---|---|---|---|
| **code** | Python, C, Makefile, SQL | style + phrases in comments | the only source of SLOC, comments and complexity |
| **markdown** | `.md`, `.markdown` | bloat + phrases | docs lines; infected lines count toward SLOP |
| **prose** | plain text | phrases | words count toward reading time |
| **data** | JSON, YAML, TOML, XML… | — | not read; line counts still feed COCOMO/LOCOMO estimates |

The boundary is “does a human read this to understand the program”: a Makefile
is code (logic lives there), JSON is data (declarations live there). Want a
different classification for your project? See [`--rules`](#configuration).

### Three ratios, three scales

| Ratio | Meaning | Scale |
|---|---|---|
| **SLOP/SLOC** | detected slop lines per line of code | CLEAN < 0.005 · TRACE < 0.10 · NOTICEABLE < 0.30 · HEAVY < 1.0 · INFESTED |
| **MD/SLOC** | markdown lines per line of code | HUMAN < 0.05 · NEURO_CLOUD < 0.35 · ESTABLISHED_SLOP < 0.50 · AGENT_SELF_SERVICE < 0.75 · AGENT_OCCUPATION < 1.00 · RECURSION |
| **comment/SLOC** | comment lines per line of code | ASCETIC < 0.05 · DOCUMENTED < 0.30 · CHATTY < 0.60 · LECTURE_NOTES < 1.00 · COMMENT_DRIVEN |

Scale bounds are calibrated against reference repositories: django sits at
MD/SLOC 0.0005 and flask at 0.015 (HUMAN), requests at 0.34 (NEURO_CLOUD). The
CLEAN/TRACE boundary for SLOP is the midpoint of the only measured gap between
human repositories (~0.0025) and slop references (~0.0071).

**How SLOP is counted:** unique `(file, line)` findings across the
prose/docs/style/history categories, plus `round(lines × 0.8)` for every
markdown file flagged as infected (giant: > 500 lines, or marker density
> 0.1 per line).

### Comprehension effort (per person)

| Component | Formula |
|---|---|
| Reading documentation | words ÷ 238 wpm × 2.3 (technical-text penalty) |
| Reading code | 200 SLOC per hour |
| Reading comments | ~6 words per comment line |
| Cognitive processing | cognitive complexity × 0.5 min per point |

### The cost ladder

| Model | Question | How |
|---|---|---|
| **COCOMO** | what would the whole tree cost to *write*? | classic 2.4·K^1.05 person-months over all lines |
| **LOCOMO** | what would it cost to *regenerate* with an LLM? | scc's token estimate (in+out): generation + review hours |
| **SLOCOMO** | what does it cost to *comprehend*? | reading hours × (1 + slop ratio) → person-months × wage × overhead; team cost scales 1–21 heads (Fibonacci) |

In dollars, writing usually dominates and regeneration is nearly free.
Comprehension sits between the two — but unlike the sunk cost of writing,
it repeats: every engineer and every agent who joins the project pays it
again.

### Detected slop

Findings fall into five categories. Four count toward SLOP: **prose**
(comments/docstrings), **docs** (markdown), **style** (code style), **history**
(git). **Agency** markers (`CLAUDE.md`, `.claude/`, …) are reported but never
counted: agents living in a repository is a fact, not an accusation.

## Example Output

Fixture project from the test suite
(`slopcount --lang en tests/fixtures/slop_project`):

```
COCOMO  write the whole tree (docs count as code) = $ 352 (0.0 person-months · 0.7 mo · 0.0 people)
LOCOMO  regenerate it with an LLM                = $ 0.01 (0.0 h + 0.0 h review)
SLOCOMO comprehend the project                   = $ 25 (0.1 h reading · 0.0 person-months) — per person

Slop-to-Code Ratio (SLOP/SLOC)                          = 2.000 [████████████████████] 200.0% INFESTED
```

<details>
<summary>Full report</summary>

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

## Configuration

| Option | Meaning |
|---|---|
| `--lang en\|ru` | interface language |
| `--rules FILE` | TOML: `[languages]` reclassification + `[[rule]]` phrase entries (repeatable) |
| `--scc-path PATH` / `SLOPCOUNT_SCC_BIN` | custom `scc` binary |
| `--personcost USD` | monthly person cost for estimates (default 4690.5) |
| `--overhead X` | cost overhead multiplier, applied to COCOMO and SLOCOMO (default 2.4) |
| `--coffee-price USD`, `--no-therapy` | tune the joke units |
| `--history N` | also scan git history, N commits deep |
| `--perplexity` | GPT-2 perplexity detector (see below) |

Reclassify a language for your project without touching code:

```toml
# my-rules.toml — run: slopcount --rules my-rules.toml .
[languages]
"AsciiDoc" = "markdown"   # count as documentation
"SQL" = "data"            # count as data, not code
```

**Perplexity detector** (optional, local GPT-2): contextual per-sentence
perplexity; median < 40 flags machine-smooth prose:

```bash
pipx install 'slopcount[perplexity]'
python -m slopcount.download_model   # fetches GPT-2 once
slopcount . --perplexity
```

## CI Gate

`slopcount` exits 0 on success and 2 on errors; gate on the JSON report:

```bash
slopcount . --json | jq -e '(.slop.ratio // 9) < 0.05' > /dev/null || echo "too much slop"
```

The `// 9` matters: a docs-only repository maps `inf` to `null` in JSON, and a
bare `null < 0.05` would evaluate true — `// 9` sends null to 9, so the gate
fails closed.

## Acknowledgements

All the grunt work — walking the tree, counting lines, comments and complexity,
COCOMO and LOCOMO — is delegated to [scc](https://github.com/boyter/scc) by Ben
Boyter. slopcount only exists because scc does. Our hat is off.

## License

MIT — see [LICENSE](LICENSE).
````

Known limitation, accepted: PyPI strips `<details>` tags, so the full report renders expanded on the PyPI page. GitHub renders it collapsed. Not a blocker.

- [ ] **Step 3: Structural self-check**

Run: `grep -c '^## ' README.md`
Expected: `8` (Quick Start, Why, The Report, Example Output, Configuration, CI Gate, Acknowledgements, License).

Run: `grep -c 'details' README.md`
Expected: `2` (opening and closing tags).

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: README — английская версия для первого релиза: quick start первым, концепция, метрики структурно"
```

---

### Task 3: README.ru.md — Russian mirror

**Files:**
- Create: `README.ru.md`

- [ ] **Step 1: Write README.ru.md**

Create the file with:

````markdown
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
````

- [ ] **Step 2: Structural self-check**

Run: `grep -c '^## ' README.ru.md`
Expected: `8` (Быстрый старт, Зачем, Отчёт, Пример вывода, Конфигурация, CI-гейт, Благодарности, Лицензия).

Run: `grep -c 'README.ru.md' README.md README.ru.md`
Expected: both files reference `README.ru.md` at least once (the language switcher).

- [ ] **Step 3: Commit**

```bash
git add README.ru.md
git commit -m "docs: README.ru.md — зеркальный русский перевод релизного README"
```

---

### Task 4: ci.yml — sha256 verification and build job

**Files:**
- Modify: `.github/workflows/ci.yml`

- [ ] **Step 1: Replace ci.yml with the hardened version**

Replace the entire file with:

```yaml
name: ci
on:
  push:
    branches: [main, slopcount-design]
  pull_request:

jobs:
  tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: python -m pip install -e .[dev]
      - name: Install scc 4.1.0 (pinned, sha256 verified)
        # hash = the pinned table in src/slopcount/scc.py (official checksums.txt v4.1.0)
        run: |
          set -euo pipefail
          curl -fsSL -o /tmp/scc.tar.gz \
            https://github.com/boyter/scc/releases/download/v4.1.0/scc_Linux_x86_64.tar.gz
          echo "c7328436d3027f4357d3d7853f7dc3ac2bbcb4ca08f1adad91a27c593884079b  /tmp/scc.tar.gz" \
            | sha256sum -c
          sudo tar xzf /tmp/scc.tar.gz -C /usr/local/bin scc
      - run: ruff check .
      - run: ruff format --check .
      - run: python -m pytest tests/ -q

  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: python -m pip install build twine
      - run: python -m build
      - run: twine check dist/*
      - name: Wheel must ship locale and rule catalogs
        run: |
          unzip -l dist/*.whl | grep -q 'locale/ru/LC_MESSAGES/slopcount\.mo'
          unzip -l dist/*.whl | grep -q 'rules/languages\.toml'
          unzip -l dist/*.whl | grep -q 'rules/phrases_en\.toml'
          unzip -l dist/*.whl | grep -q 'rules/phrases_ru\.toml'
          unzip -l dist/*.whl | grep -q 'rules/env_markers\.toml'
```

- [ ] **Step 2: YAML sanity check**

Run: `.venv/bin/python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml')); print('ok')"`
Expected: `ok`.

- [ ] **Step 3: Verify the local wheel really contains those paths (pre-flight of the CI assert)**

Run: `.venv/bin/python -m build --wheel >/dev/null && unzip -l dist/*.whl | grep -E 'locale/ru/LC_MESSAGES/slopcount\.mo|rules/languages\.toml|rules/phrases_en\.toml|rules/phrases_ru\.toml'`
Expected: 4 matching lines (`slopcount/locale/ru/LC_MESSAGES/slopcount.mo`, `slopcount/rules/languages.toml`, `slopcount/rules/phrases_en.toml`, `slopcount/rules/phrases_ru.toml`).

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: sha256-проверка scc 4.1.0 и build-job с контролем содержимого wheel"
```

---

### Task 5: release.yml — tag-triggered PyPI publishing

**Files:**
- Create: `.github/workflows/release.yml`

- [ ] **Step 1: Write release.yml**

Create the file with:

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
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: python -m pip install build twine
      - run: python -m build
      - run: twine check dist/*
      - name: Wheel must ship locale and rule catalogs
        run: |
          unzip -l dist/*.whl | grep -q 'locale/ru/LC_MESSAGES/slopcount\.mo'
          unzip -l dist/*.whl | grep -q 'rules/languages\.toml'
          unzip -l dist/*.whl | grep -q 'rules/phrases_en\.toml'
          unzip -l dist/*.whl | grep -q 'rules/phrases_ru\.toml'
          unzip -l dist/*.whl | grep -q 'rules/env_markers\.toml'
      - name: Tag must match package version
        run: |
          grep -Fq "version = \"${GITHUB_REF_NAME#v}\"" pyproject.toml
      - uses: actions/upload-artifact@v4
        with:
          name: dist
          path: dist/

  publish:
    needs: build
    runs-on: ubuntu-latest
    environment: pypi
    permissions:
      id-token: write
    steps:
      - uses: actions/download-artifact@v4
        with:
          name: dist
          path: dist/
      - uses: pypa/gh-action-pypi-publish@release/v1
```

- [ ] **Step 2: YAML sanity check**

Run: `.venv/bin/python -c "import yaml; yaml.safe_load(open('.github/workflows/release.yml')); print('ok')"`
Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/release.yml
git commit -m "ci: release.yml — публикация в PyPI по тегу через trusted publishing"
```

---

### Task 6: Full local verification (spec §7)

No commits here unless a check fails and a fix is required.

- [ ] **Step 1: Lint, format, full test suite**

Run: `.venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/python -m pytest tests/ -q`
Expected: ruff silent, format clean, all tests pass (~20 s; e2e runs real scc).

- [ ] **Step 2: Build and inspect artifacts**

Run:
```bash
.venv/bin/pip install --quiet twine
rm -rf dist && .venv/bin/python -m build
.venv/bin/twine check dist/*
ls dist/
```
Expected: `dist/slopcount-0.1.0-py3-none-any.whl` and `dist/slopcount-0.1.0.tar.gz`, twine check passes for both.

- [ ] **Step 3: Wheel install into a clean venv + full functional pass**

Run:
```bash
python3 -m venv /tmp/slopwheel
/tmp/slopwheel/bin/pip install --quiet dist/slopcount-0.1.0-py3-none-any.whl
/tmp/slopwheel/bin/slopcount --version                       # slopcount 0.1.0
/tmp/slopwheel/bin/slopcount .                               # self-scan renders
/tmp/slopwheel/bin/slopcount tests/fixtures/slop_project --evidence | head -20
/tmp/slopwheel/bin/slopcount --lang ru tests/fixtures/slop_project | head -5
```
Expected: version 0.1.0; three-section report on self-scan; evidence lines with file/line/snippet; Russian output.

- [ ] **Step 4: First-run experience — scc auto-download from a clean home**

Run:
```bash
python3 -m venv /tmp/slopfirst
/tmp/slopfirst/bin/pip install --quiet dist/slopcount-0.1.0-py3-none-any.whl
rm -rf /tmp/slopcount-fake-home
env -i HOME=/tmp/slopcount-fake-home PATH="/tmp/slopfirst/bin" \
  /tmp/slopfirst/bin/slopcount tests/fixtures/slop_project
ls /tmp/slopcount-fake-home/.cache/slopcount/
```
Expected: a full report renders (proving the tool downloaded scc on its own), and the cache listing shows a versioned scc directory. `env -i` guarantees no `SLOPCOUNT_SCC_BIN` and a PATH with no system scc — the resolver must fall through to the pinned download.

- [ ] **Step 5: sdist builds and installs without the repository**

Run:
```bash
python3 -m venv /tmp/slopsdist
/tmp/slopsdist/bin/pip install --quiet dist/slopcount-0.1.0.tar.gz
/tmp/slopsdist/bin/slopcount --version
```
Expected: `slopcount 0.1.0` (pip builds the sdist in isolation, proving hatchling packaging is self-contained).

- [ ] **Step 6: Clean up test venvs**

Run: `rm -rf /tmp/slopwheel /tmp/slopfirst /tmp/slopsdist /tmp/slopcount-fake-home`
Expected: no output.

---

### Task 7: Pause-gate and release (INTERACTIVE — never automated)

**Files:** none (git operations only). Every substep that pushes or publishes requires explicit user confirmation in the moment.

- [ ] **Step 1: Present the pause-gate checklist to the user**

Show the user the checklist from spec §8 and substantiate every item:
1. Green run — paste the actual tail of `pytest`/`ruff` output from Task 6 (not a promise)
2. Local verification §7 done — wheel + sdist built, clean-venv installs passed, scc auto-download proven, `--lang ru` / `--evidence` alive
3. `README.md` and `README.ru.md` — user reads both files
4. Final `pyproject.toml` — user reviews (version 0.1.0, description, classifiers)
5. Workflows — user reviews `release.yml` and the modified `ci.yml`
6. Squash diff — show `git diff main...slopcount-design --stat`
7. Commit message and tag message — user approves the texts below
8. User side: PyPI account verified (email + 2FA), pending publisher created (project `slopcount`, owner `echernyshev`, repo `slopcount`, workflow `release.yml`, environment `pypi`), environment `pypi` exists in the GitHub repo settings

Do NOT proceed until the user explicitly confirms all items.

- [ ] **Step 2: Squash-merge into main**

Run:
```bash
git checkout main
git merge --squash slopcount-design
git commit -m "slopcount 0.1.0 — detect AI slop, estimate the cost of comprehension

slopcount scans a codebase, detects LLM-generated slop in comments,
docstrings and markdown docs, and estimates what the project costs to
comprehend (SLOCOMO) — versus writing it (COCOMO) or regenerating it
with an LLM (LOCOMO). Counting is delegated to scc; every finding is
explainable via --evidence. English/Russian UI, JSON/CSV output for CI."
```
Expected: single commit on main, working tree identical to `slopcount-design`.

- [ ] **Step 3: Tag**

Run: `git tag -a v0.1.0 -m "slopcount 0.1.0"`
Expected: no output.

- [ ] **Step 4: Push (WITH USER CONFIRMATION)**

Run: `git push origin main v0.1.0`
Expected: both refs accepted.

- [ ] **Step 5: Watch CI and the release workflow**

Run: `gh run list --limit 3` (repeat/`gh run watch` as needed)
Expected: ci run on main green; release workflow on tag green; package visible at https://pypi.org/project/slopcount/

- [ ] **Step 6: Verify the public package**

Run:
```bash
python3 -m venv /tmp/pylivetest
/tmp/pylivetest/bin/pip install --quiet slopcount
/tmp/pylivetest/bin/slopcount --version
rm -rf /tmp/pylivetest
```
Expected: `slopcount 0.1.0` installed from the public PyPI.

- [ ] **Step 7 (optional, with user): repository topics**

Run: `gh repo edit echernyshev/slopcount --add-topic sloc --add-topic llm --add-topic ai --add-topic code-quality`
Expected: topics updated on the GitHub page.

Branch `slopcount-design` is kept, not deleted.
