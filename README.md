# slopcount

> SLOC — это то, за что ты заплатил. SLOP — это то, что ты теперь обязан прочитать.

`slopcount` сканирует проект, находит LLM-нейрослоп и считает, сколько будет
стоить его **осознать** — пародия на классический `sloccount` Дэвида Уилера, где COCOMO оценивал стоимость *написания*
кода.

    $ slopcount .
    Totals grouped by slop origin (dominant slop source first):
    -------------------------------------------------------------------------------
    Origin                           files    slop lines    slop %  cognitivity
    ...
    Total Physical Source Lines of Code (SLOC)              = 1,882
    Total Suspicious Lines Of Prose (SLOP)                  = 55
    Slop Ratio (SLOP/SLOC)                                  = 2.9%
    ...
    Total Estimated Cost to Comprehend                        = $ 1,285.35
    Coffee Required                                           = 2 cups ($ 8.00)
    VERDICT: [█░░░░░░░░░░░░░░░░░░░] 2.9%  Almost human. Suspiciously clean. Where are you hiding the slop?

(Да, это самоскан репозитория slopcount — инструмент считает, что мы почти люди.)

## Установка

    pip install slopcount

## Философия

Генерация бесплатна — осознание дорого. Детекторы работают честно (регексы,
когнитивная сложность Кэмпбелла, скорость чтения Brysbaert), единицы — шуточные
(терапия, кофе, GPU-часы сожаления). Каждая улика объяснима: `--details`
покажет файл, строку, правило и вес.

Мы бы написали это на Perl, как оригинал — LLM не умеют Perl, инструмент был бы
гарантированно slop-free. Но мы слабы.

## Скриншот вывода

Реальный прогон на fixture-проекте из тестов репозитория
(`slopcount tests/fixtures/slop_project`):

    Totals grouped by slop origin (dominant slop source first):
    -------------------------------------------------------------------------------
    Origin                           files    slop lines    slop %  cognitivity
    -------------------------------------------------------------------------------
    Prose (comments/docstrings)          2             3      23.1  high
    Markdown specs                       1             2      15.4  medium
    Code style                           1             2      15.4  medium
    Git history                          0             0       0.0  low
    Environment markers                  1             —         —  —
    -------------------------------------------------------------------------------
    Total Physical Source Lines of Code (SLOC)              = 8
    Total Suspicious Lines Of Prose (SLOP)                  = 13
    Slop Ratio (SLOP/SLOC)                                  = 162.5%
    -------------------------------------------------------------------------------
    ...
    VERDICT: [████████████████████] 162.5%  You ran slopcount inside slop. Recursion

## CI-режим (шутка, которую можно поставить в пайплайн)

    slopcount . --json --fail-above 40 || echo "too much slop"

## Локализация

Вывод — en (default) / ru: `slopcount --lang ru .`

## Опциональная мощь

    pipx install 'slopcount[perplexity]'   # локальная GPT-2: гладкость прозы
    python -m slopcount.download_model
    slopcount . --perplexity

    pipx install 'slopcount[treesitter]'   # точная когнитивная сложность

## Лицензия

MIT — см. [LICENSE](LICENSE).
