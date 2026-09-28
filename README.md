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
