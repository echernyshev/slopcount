# Делегирование подсчёта и сканирования в scc

- Дата: 2026-09-27
- Статус: утверждён (brainstorming-сессия)
- Ветка: `slopcount-design`

## 1. Контекст и цель

Базовые метрики (SLOC, комментарии, complexity, обход дерева) реализованы в проекте
самописно и содержат подтверждённые дефекты (строка «код + трейлинг-комментарий»
исключается из SLOC — проверено сравнением со scc). Решение: делегировать известную
функциональность инструменту [scc](https://github.com/boyter/scc) и оставить в проекте
только код, участвующий в детекции SLOP и формуле SLOCOMO.

Цели:

1. Один обходчик дерева — scc; манифест файлов scc = единый источник файлов для
   детекторов и числителей метрик (джойн «по построению»).
2. Удалить самописные `metrics/sloc.py`, `metrics/cognitive.py`, обход `scanner.py`.
3. Получить бесплатно: COCOMO, LOCOMO, cognitive complexity, честную gitignore-семантику,
   детекцию языка по shebang/имени файла (не только по расширению).
4. UX: пользователь не думает про scc — ленивая установка при первом запуске.

Не-цели: сохранение обратной совместимости JSON (модель перепроектируется),
перекалибровка вердиктов (шкала MD/SLOC 2026-09-26 сохраняется — формула и суффиксный
фильтр не меняются).

## 2. Принятые решения (сводка)

| Вопрос | Решение |
|---|---|
| Версия scc | 4.1.0 (последняя; go-модуль `github.com/boyter/scc/v4`), пин + sha256 |
| Источник файлов | единственный вызов scc `--format json2 --by-file` → манифест |
| Классификация kind | куратируемая таблица всех 366 имён языков scc (allowlist `code` = 251) |
| Конфиги/данные (JSON, YAML, XML…) | `kind="data"` — видны в статах скана, не анализируются, не входят в SLOC |
| Подсчёт SLOC | сумма `Code` по kind=code строкам манифеста |
| COCOMO/LOCOMO | totals того же вызова, по полному набору scc; наши `--avg-wage/--overhead` |
| Cognitive | scc `Cognitive` per-file; `metrics/cognitive.py` и `[treesitter]` extra удаляются |
| Halstead | удаляется; `reading = проза/238wpm×2.3 + cognitive×0.5мин` |
| Зависимость | ленивый бутстрап официального релиза с GitHub → кеш; без fallback на самописное |
| Корректировка языков пользователем | секция `[languages]` в пользовательском `--rules` TOML, точечный мердж |
| Лестница затрат | COCOMO (написать) / LOCOMO (перегенерировать) / SLOCOMO (осознать) в выводе |
| JSON | свободный редизайн, сгруппирован по смыслу |

## 3. Архитектура

```
БЫЛО:  os.walk + gitignore-lite → свои счётчики → свой cognitive → SLOCOMO
СТАНЕТ: scc (один subprocess) → манифест + числа → детекторы → SLOCOMO

resolve scc → вызов:
  scc --format json2 --by-file --cognitive --locomo
      --avg-wage <round(personcost×12)> --overhead <overhead>
      --exclude-dir <SKIP_DIRS> <абс. root>
  (cwd = нейтральный пустой temp-dir; флаг --no-config гасит авто-детект
   .sccconfig/SCC_CONFIG_PATH — см. Прил. B)
    ↓ SccReport { files[], scc_version, cocomo, locomo }
    ↓
классификация kind/language → ScannedFile[] → детекторы (не меняются)
    ↓
SLOC/comments/complexity = суммы по тем же строкам → aggregate → SLOCOMO → render
```

Конвейер `детекторы → Evidence[] → aggregate → SLOCOMO → render` и диспетчеризация
`kind → детекторы` не меняются; меняется производитель списка файлов.

## 4. Модуль `src/slopcount/scc.py`

### 4.1 Резолв бинарника (ленивая установка)

Приоритет:

1. флаг `--scc-path` (явный путь);
2. env `SLOPCOUNT_SCC_BIN`;
3. `shutil.which("scc")`, если `scc --version` ≥ `SCC_MIN_VERSION` ("4.1.0");
   найден, но устаревший → предупреждение в stderr, идём дальше;
4. кеш: Unix `~/.cache/slopcount/scc/<версия>/scc`, Windows
   `%LOCALAPPDATA%\slopcount\scc\<версия>\scc.exe`;
5. скачивание официального релиза `SCC_VERSION` с GitHub Releases: выбор asset по
   `{linux,darwin}-{amd64,arm64}, windows-amd64`, проверка sha256 по зашитой таблице,
   распаковка (tar.gz/zip, stdlib), `chmod +x`, укладка в кеш, одна строка прогресса
   в stderr («Downloading scc 4.1.0…»);
6. любой провал → `RuntimeError` → exit 2 с подсказками ручной установки
   (brew/snap/choco/scoop/`go install github.com/boyter/scc/v4@v4.1.0`/releases).

Точные имена asset'ов и sha256 снимаются со страницы релиза 4.1.0 на этапе реализации
и закрепляются константами + unit-тестом полноты платформенной таблицы. Несовпадение
чексуммы → удалить частичный файл, ошибка с подсказкой.

### 4.2 Вызов и парсинг

Один subprocess (без shell), аргументы — см. §3; таймаут защитный (например 300 с).
Парсинг json2 (фактическая схема проверена на 4.1.0):

- per-file в `languageSummary[].Files[]`: `Location, Language, Extension, Bytes,
  Lines, Code, Comment, Blank, Complexity, Cognitive, Binary, Minified, Generated, Uloc`;
- summary: `estimatedCost, estimatedScheduleMonths, estimatedPeople` (COCOMO) и
  `estimatedLLMCost, estimatedLLMInputTokens, estimatedLLMOutputTokens,
  estimatedLLMGenerationSeconds, estimatedLLMReviewHours, estimatedLLMCycles,
  estimatedLLMPreset` (LOCOMO).

Битый JSON / не-нулевый exit / отсутствие ожидаемых ключей → `RuntimeError` → exit 2.

### 4.3 Модель данных

```python
@dataclass(frozen=True)
class SccFile:
    # path (posix, отн. root); language (extractor id | None); kind
    # ("code"|"markdown"|"prose"|"data"); size (Bytes); lines, code, comment,
    # blank, complexity, cognitive — int; binary — bool
    ...

@dataclass(frozen=True)
class Cocomo:       # cost: float; schedule_months: float; people: float

@dataclass(frozen=True)
class Locomo:       # cost, generation_seconds, review_hours, cycles: float;
                    # input_tokens, output_tokens: int; preset: str

@dataclass(frozen=True)
class SccReport:    # files: list[SccFile]; scc_version: str; cocomo; locomo
```

`ScannedFile` сохраняет поля `(path, language, kind, size)` — `size` нужен
`docs_bloat` (Σ байт markdown-файлов), берётся из `Bytes`. `SKIP_DIRS` переезжает
из `scanner.py` в аргумент `--exclude-dir` (список scc по умолчанию `.git,.hg,.svn`
расширяется нашим списком: `node_modules`, `.venv`, `venv`, `env`, `__pycache__`,
`dist`, `build`, `target`, `.tox`, `.mypy_cache`, `.pytest_cache`, `.ruff_cache`,
`.idea`, `.vscode`, `.eggs`, `.serena`).

Семантика обхода scc, зафиксированная как поведение slopcount: настоящая
gitignore-семантика (с отрицаниями — замена упрощённой), symlink'и не обходятся,
`.sccconfig` нейтрализован cwd, дубликаты файлов считаются (как сегодня).

## 5. Каталог `rules/languages.toml` и пользовательские оверрайды

### 5.1 Builtin-каталог

Новый TOML рядом с `phrases_en.toml`/`phrases_ru.toml`, грузится тем же загрузчиком
(`rules.py`), fail-fast при бите. Полная таблица — Приложение A. Формат:

```toml
[languages]          # scc Language (display name) → kind
Python = "code"      # 251 имя "code"
Markdown = "markdown"      # + ReStructuredText
"Plain Text" = "prose"
JSON = "data"        # и остальные 112 «не-кода» — явно, для валидации имён
...

[extractors]         # scc Language → id для extractors.py (поддерживаемое подмножество)
Python = "python"
"JavaScript" = "javascript"
"TypeScript" = "typescript"
...
```

Все 366 имён scc 4.1.0 (источник — `scc -l`) классифицированы явно: `code` × 251,
`markdown` × 2, `prose` × 1, `data` × 112. Имя, которое отдал scc, но которого нет
в таблице (будущая версия scc) → консервативный `kind="data"`, `language=None`,
без предупреждения (задокументировано).

### 5.2 Пользовательские оверрайды

В пользовательском `--rules` TOML (повторяемый, как сегодня):

```toml
[languages]
"Zig" = "code"     # добавили то, что «забыли»
"SQL" = "data"     # исключили лишнее
"Org"  = "prose"   # скорректировали прозу
```

Мердж — `dict.update()` поверх builtin. Значение — любой из четырёх kind.
Неизвестное scc-имя в пользовательском файле → предупреждение в stderr при загрузке
(опечатки не молчат; полный список известных имён — builtin-каталог). Секция
`[extractors]` из пользовательского файла не расширяется (только builtin) — наружу
торчит только классификация.

### 5.3 Матрица поведения: как kind определяет судьбу файла

Ортогональные детекторы (env-маркеры по именам файлов, git-история) матрицей не
затрагиваются — они не зависят от kind.

| Аспект | code | markdown | prose | data |
|---|---|---|---|---|
| Содержимое читается (`read_text`) | да | да | да | **нет** |
| Детекторы | style + phrase | docs_bloat + phrase (+ pplx) | phrase (+ pplx) | — |
| `sloc` (знаменатель SLOP/SLOC, comment/SLOC) | Σ `Code` | — | — | — |
| `comment_lines` | Σ `Comment` | — | — | — |
| `complexity`, `cognitive` (JSON `code`) | Σ | — | — | — |
| cognitive → SLOCOMO | по файлам со style-уликами | — | — | — |
| `md_files` / `md_lines` (числитель MD/SLOC) | — | суффикс `.md`/`.markdown` | — | — |
| Улики → SLOP | style/phrase | docs/phrase (+ pplx) | phrase (+ pplx) | нет |
| `prose_words` → время чтения SLOCOMO | слова из улик | слова из улик + `0.8×` слов заражённых файлов | слова из улик | — |
| COCOMO / LOCOMO | да | да | да | да |
| `scan.files` | да | да | да | да (только факт наличия) |

Следствия, которые стоит проговорить явно:

- **data не читается вообще** — ни байта содержимого не попадает в детекторы;
  файл существует только как строка в статах скана.
- **SLOC формируется исключительно классом code** — знаменатели SLOP/SLOC и
  comment/SLOC не разбавляются конфигами и разметкой.
- **Числитель MD/SLOC — только markdown с суффиксом** `.md`/`.markdown`
  (`.rst` детектируется docs_bloat, но в числитель не входит — калибровка 2026-09-26).
- **COCOMO/LOCOMO — единственное место, где класс не важен**: scc считает их по
  всему распознанному дереву (включая data) — «стоимость всего дерева» vs
  «стоимость осознания слопа» у SLOCOMO.

## 6. Метрики: источник каждой

| Метрика | Источник |
|---|---|
| `sloc` | Σ `Code` по kind=code |
| `comment_lines` | Σ `Comment` по kind=code |
| `complexity` (новая) | Σ `Complexity` по kind=code |
| cognitive для SLOCOMO | Σ `Cognitive` по kind=code файлам **со style-уликами** (как сегодня; внутренний вход формулы) |
| `cognitive` в JSON (`code`) | Σ `Cognitive` по всем kind=code — факт о проекте, не вход SLOCOMO |
| `scan.files` / `scan.skipped` | всего файлов в манифесте / непрочитанные `read_text` из kind∈{code,markdown,prose} (как сегодня) |
| `md_files`, `md_lines` | kind=markdown + суффикс `.md`/`.markdown`; `md_lines` = Σ `Lines` (проверено: совпадает с текущей формулой физических строк байт-в-байт) |
| COCOMO, LOCOMO | summary того же вызова, по **полному** набору scc (осознанно: «написать всё дерево» / «перегенерировать всё дерево» vs «осознать слоп»); экономика едина — `--avg-wage = round(personcost×12)`, `--overhead = overhead` |
| SLOP, улики, вердикты | наше, без изменений |

Семантические сдвиги подсчёта (багфиксы): строка «код + трейлинг-комментарий» теперь
код; докстринги остаются комментариями (совпадает); SLOC распространяется на 251 язык
вместо 23 расширений (для чисто-python-репозиториев без .sql/.sh-файлов знаменатель
не меняется — TOML остаётся `data`).

## 7. Вывод: лестница затрат и новая модель отчёта

### 7.1 Текстовый рендер (новый блок)

```
── Лестница затрат ───────────────────────────────
COCOMO  написать всё это людьми     $ 84 211      5,4 мес
LOCOMO  перегенерировать LLM-ом     $ 20          3,9 ч + 5,9 ч ревью
SLOCOMO осознать весь слоп          $ 1 557       0,14 чел-мес
──────────────────────────────────────────────────
```

Все строки локализуются (`_()`), ru-каталог обновляется, `msgfmt` drift-guard действует.

### 7.2 JSON (свободный редизайн)

```json
{
  "scan":  { "tool": "scc 4.1.0", "files": 54, "skipped": 0, "history_commits": null },
  "code":  { "sloc": 2953, "comment_lines": 116, "complexity": 400, "cognitive": 123 },
  "slop":  { "total": 66, "infected_md_lines": 20, "ratio": 0.0224,
             "categories": { "prose": { "files": 7, "slop_lines": 38, "weight": 45,
                                          "cognitivity": "высокая" }, "...": {} } },
  "docs":  { "md_files": 10, "md_lines": 5901, "md_sloc_ratio": 1.999 },
  "costs": {
    "cocomo":  { "cost": 84211.0, "schedule_months": 5.37, "people": 1.39 },
    "locomo":  { "cost": 20.0, "input_tokens": 3000000, "output_tokens": 700000,
                 "generation_seconds": 14040.0, "review_hours": 5.9, "cycles": 2.1,
                 "preset": "medium" },
    "slocomo": { "reading_hours": 1.2, "person_months": 0.14, "person_years": 0.01,
                 "schedule_months": 1.18, "therapists": 0.12, "cost": 1556.55,
                 "context_windows_200k": 0.0, "context_windows_1m": 0.0,
                 "gpu_hours": 0.0, "coffee_cups": 3, "coffee_cost": 12.0,
                 "therapy_sessions": 1, "therapy_cost": 150.0 }
  },
  "evidence_count": 57,
  "verdict": { "code": "RECURSION", "md_sloc_ratio": 1.999 }
}
```

Правила: `inf` → `null` (как сегодня); ключи стабильны для CI; `approximate` удалён;
CSV-вывод (пофайловые улики) не меняется.

## 8. CLI

- Новый флаг `--scc-path PATH` — явный путь к бинарнику (`Options.scc_path`).
- `--personcost`/`--overhead` транслируются в `--avg-wage`/`--overhead` scc.
- `[treesitter]` extra удаляется из `pyproject.toml`; `[perplexity]` не трогается.
- Остальные флаги без изменений (`--fail-above` работает по `md_sloc_ratio`).

## 9. Удаления и миграция

| Файл/сущность | Судьба |
|---|---|
| `metrics/sloc.py` (25 строк) | удалить целиком |
| `metrics/cognitive.py` (162) | удалить целиком (approx + treesitter + halstead) |
| `scanner.py` (130) | удалить; `read_text` + `ScannedFile` → `evidence.py` (иначе цикл импортов app↔детекторы); `SKIP_DIRS` → `scc.py` |
| `extractors.py` | остаётся (нумерация улик phrase-детектора), теряет counting-потребителя |
| SLOCOMO | сигнатура без `halstead_secs`/`approximate`; `SlocomoResult.approximate` удалён |
| `Report` | + `scc_version`, `complexity`, `cocomo`, `locomo`; `sloc`/`comment_lines` наполняются из scc |
| `json_out.py` | переписан под модель §7.2 |
| `text.py` | + блок лестницы; текст «(approximate)» удалён |
| `rules.py` | + загрузка `languages.toml`, мердж `[languages]`, валидация имён |
| тесты | обновить ожидания; см. §11 |

## 10. Обработка ошибок

| Случай | Поведение |
|---|---|
| scc не найден, сети нет | `RuntimeError` → exit 2 + подсказки установки |
| скачивание оборвалось / чексумма | чистый отказ, удалить частичный файл, подсказка |
| PATH-версия < 4.1.0 | предупреждение, используется управляемый кеш |
| scc упал / битый JSON / нет ключей | `RuntimeError` → exit 2 с выводом stderr scc |
| неизвестный язык от scc | молча `data` (задокументировано) |
| опечатка в пользовательском `[languages]` | предупреждение при загрузке |
| битый пользовательский TOML | существующее поведение: `RuntimeError` → exit 2 |

## 11. Тестирование

- **Фикстура json2**: запечь реальный вывод `scc 4.1.0` (эталонный слоп + файл
  докстрингов/трейлинг-комментариев) → unit-тесты парсинга и модели.
- **Таблица языков**: каждый `[extractors]`-язык обязан иметь kind=code; полное
  покрытие 366 имён (сумма по kind = 366); мердж оверрайдов; предупреждение об опечатке.
- **Резолв бинарника**: mock `shutil.which`/env/сети — порядок приоритетов, версия,
  кеш-попадание, отказ без сети. Сеть в тестах не нужна.
- **e2e**: обновить ожидаемые числа (SLOC растёт на trailing-комментариях; возможен
  сдвиг `comment_sloc_ratio`); интеграционный маркер `requires-scc` для полного прогона.
- **i18n**: новые msgids в ru-каталоге, побайтовый drift-guard продолжает работать.

## 12. CI и документация

- Workflow: шаг установки scc (кеш артефакта) — установка нашим бутстрапом
  (`python -c "from slopcount.scc import ensure_binary; …"`) или релизный бинарник.
- README: раздел «Концепция подсчёта» (классы файлов и их влияние — добавлен в этой
  же сессии вместе со спекой); при реализации дополнить: первый запуск качает ~4 МБ,
  `--scc-path`/`SLOPCOUNT_SCC_BIN`, breaking-список, обновить примеры вывода.
- CLAUDE.md: переписать «Архитектуру» (конвейер через scc) и «Команды».

## 13. Breaking changes

1. JSON — новая модель (§7.2), включая переименование/перегруппировку всех ключей.
2. SLOC: 251 язык вместо 23 расширений; trailing-комментарии — код; shebang-детект.
3. gitignore: настоящая git-семантика вместо упрощённой (без `!`).
4. `comment_sloc_ratio` считается scc (докстринги — как и раньше комментарии).
5. Удалён `[treesitter]` extra и `approximate` в отчётах.
6. Требуется scc ≥ 4.1.0 (лениво устанавливается; PATH-альтернатива).

## Приложение A. Таблица языков (все 366 имён scc 4.1.0)

Источник имён: `scc -l` (бинарник 4.1.0). Классификация: GitHub Linguist
`languages.yml` (`type:`) + популярность (SO Survey 2024/2025, Octoverse) + критерий
«файл — действительно исходный код, который читают и поддерживают». Осознанные
отступления от Linguist: SQL=code (миграции/запросы — код под ревью; вся семья
cloc/tokei/scc так считает), Vue/Svelte/Astro=code (script-блоки — исходник
приложения), Thrift/IDL/Cap'n Proto/GraphQL/TypeSpec=data (контракты схем единообразно
с .proto), шаблоны (Jinja/Twig/…) = data равномерно, XSLT=code (Turing-полная
трансформация), Makefile/CMake/Bazel/Gradle/Dockerfile/HCL/Nix/Jsonnet=code (языки
с логикой vs ключ-значение конфиги), MSBuild=data (XML-метаданные) при Gradle=code.

### kind="code" — tier 1 (27, top-usage)

BASH, C, C Header, C#, C++, C++ Header, Dart, Go, JSX, Java, JavaScript, Kotlin, Lua,
PHP, Perl, Powershell, Python, R, Ruby, Rust, SQL, Scala, Shell, Swift, TypeScript,
TypeScript Typings, Zsh

### kind="code" — tier 2 (40, распространены в поддерживаемых репо)

ABAP, Apex, Assembly, Astro, Batch, Bazel, CMake, Clojure, Cuda, Cython, Dockerfile,
Elixir, Erlang, FORTRAN Legacy, Fortran Modern, Fragment Shader File, GDScript, GLSL,
Gradle, Groovy, HCL, Julia, MATLAB, Makefile, Nix, Objective C, OpenTofu, PL/SQL, SAS,
Solidity, Svelte, SystemVerilog, Terraform, VHDL, Verilog, Vertex Shader File,
Visual Basic, Visual Basic for Applications, Vue, Zig

### kind="code" — tier 3 (184, нишевые, но настоящий программный код)

AL, APL, ASP, ASP.NET, ATS, AWK, ActionScript, Ada, Agda, Alchemist, Alex, Algol 68,
Alloy, Amber, AppleScript, ArkTs, Arturo, AutoHotKey, Autoconf, Basic, Bicep, Bitbake,
Boo, Bosque, Brainfuck, C Shell, C3, COBOL, Cairo, Cangjie, Ceylon, Chapel, Circom,
Clipper, ClojureScript, CodeQL, CoffeeScript, Cogent, ColdFusion, ColdFusion CFScript,
Coq, Crystal, Cypher, D, DAML, DM, Dhall, Elm, Emacs Lisp, EmiT, Expect,
Extensible Stylesheet Language Transformations, F#, F*, FSL, Factor, Fennel, Fish,
Flow9, Forth, Futhark, Game Maker Language, Gemfile, Gherkin Specification, Gleam, Go+,
Gremlin, Gwion, Happy, Hare, Haskell, Haxe, IEC61131-3, Idris, Isabelle, JAI, JCL,
Janet, JavaServer Pages, Jenkins Buildfile, Jsonnet, Just, K, Korn Shell, Koto, LALRPOP,
LD Script, LEX, LLVM IR, LOLCODE, Lean, Lisp, LiveScript, Luau, Luna, MLIR, MQL Header,
MQL4, MQL5, MUMPS, Madlang, Meson, Metal, Modula3, Mog, Mojo, Monkey C, Moonbit, Move,
Nature, Nial, Nim, Nushell, OCaml, Objective C++, Odin, Opalang, OpenQASM, Oz, PKGBUILD,
PRQL, Pascal, Picat, Pkl, Pony, Processing, Prolog, Puppet, PureScript, Q#, QCL, QML,
Racket, Rakefile, Raku, ReScript, ReasonML, Rebol, Redscript, Robot Framework, SKILL,
SNOBOL, SPL, Scallop, Scheme, Scons, Seed7, Sieve, Slang, Smalltalk, Snakemake,
Softbridge Basic, Specman e, Stan, Standard ML (SML), Stata, Swig, TCL, TOON, TTCN-3,
Tact, Teal, Treetop, Unreal Script, Up, Ur/Web, V, Vala, Varnish Configuration,
Vim Script, WebGPU Enhanced Shading Language, WebGPU Shading Language, Wolfram, Wren,
XMake, Xtend, Zen C, ZoKrates, bait, hoon, jq, m4, sed, wenyan

### kind="markdown" (2)

Markdown, ReStructuredText

### kind="prose" (1)

Plain Text

### kind="data" (112)

ABNF, Android Interface Definition Language, AsciiDoc, Avro, Bean, Bitbucket Pipeline,
Blade template, Blueprint, Bru, BuildStream, CSS, CSV, Cabal, Cap'n Proto, Cassius,
CloudFormation (JSON), CloudFormation (YAML), Closure Template, Creole, D2, DOT,
Device Tree, Docker ignore, Document Type Definition, Elixir Template, Emacs Dev Env,
FIDL, FXML, Freemarker Template, GN, Game Maker Project, Go Template, Godot Scene,
GraphQL, HAML, HEEx, HEX, HTML, Hamlet, Handlebars, IDL, INI, Intel HEX, JSON, JSON5,
JSONC, JSONL, Jade, Jinja, Julius, Jupyter, LESS, LaTeX, License, Lucius, MDX, MSBuild,
Macromedia eXtensible Markup Language, Mako, Max, Module-Definition, Mustache, Org,
POML, PSL Assertion, Patch, Polly, PostScript, Properties File, Protocol Buffers,
Qt Translation Source, RAML, Razor, Report Definition Language, Rich Text Format, Ruby HTML,
SPDX, SRecode Template,
SVG, Sass, Slint, Smarty Template, Spice Netlist, Stylus, Systemd, TL, TOML, TaskPaper,
TeX, Templ, TemplateToolkit, Tera, Textile, Thrift, Twig Template, TypeSpec, Typst,
Ur/Web Project, Verilog Args File, W.I.S.E. Jobfile, Web Services Description Language,
Windows Resource-Definition Script, XAML, XHTML, XML, XML Schema, Xcode Config, YAML,
Yarn, gitignore, ignore, nuspec

### [extractors] — scc Language → id `extractors.py`

| id | scc Language |
|---|---|
| python | Python |
| javascript | JavaScript, JSX |
| typescript | TypeScript, TypeScript Typings, ArkTs |
| go | Go, Go+ |
| rust | Rust |
| c | C, C Header |
| cpp | C++, C++ Header, Cuda |
| java | Java |
| ruby | Ruby, Rakefile, Gemfile |
| sh | BASH, Shell, Zsh, Korn Shell, C Shell, Fish, Nushell, PKGBUILD |
| php | PHP |
| csharp | C# |
| swift | Swift |
| kotlin | Kotlin |
| scala | Scala |

## Приложение B. Проверенные факты об scc

- Версии: 3.7.0 — последний v3-модуль (`go install …/scc@latest`); 4.x — модуль
  `github.com/boyter/scc/v4`; LOCOMO и `--cognitive` появились в 4.0.0; проверено на 4.1.0.
- `--format json2` даёт COCOMO (`estimatedCost/ScheduleMonths/People`) и LOCOMO
  (`estimatedLLM*`) в корне JSON; per-file — только с `--by-file`.
- Python: докстринги = Comment (совпадает с нашей семантикой); строка «код +
  трейлинг-комментарий» = Code (наш счётчик ошибался).
- Markdown: `Lines` = физические строки, включая пустые (совпадает с нашей формулой
  `md_lines` байт-в-байт; проверено на трёх файлах).
- `.sccconfig` (v4) подхватывается из **cwd** и глобально через `SCC_CONFIG_PATH`
  (приоритет global < project < CLI; проверено живьём: чужой конфиг менял
  `estimatedLLMCost` в 100×, флаги CLI перекрывают лишь переданное) →
  нейтрализуется флагом `--no-config`; пустой temp-dir как cwd — дополнительный
  ремень.
- Флаги: `--avg-wage` (default 56286 = наш `personcost 4690.50 × 12` — конвенции
  совпадают), `--overhead` (default 2.4 = наш), `--exclude-dir`, `--no-gitignore`,
  `--include-symlinks` (off по умолчанию), `-d` дедупликация (off по умолчанию).
- stdin-режима подачи списка файлов нет → манифест+join вместо явного списка.
