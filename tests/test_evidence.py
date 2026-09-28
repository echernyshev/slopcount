from slopcount.evidence import (
    Category,
    CategoryTotals,
    Evidence,
    LanguageRow,
    SlopStats,
    VolumeStats,
    aggregate_slop,
    safe_ratio,
)


def _ev(file, line, cat, weight):
    return Evidence(file=file, line=line, category=cat, weight=weight, description="d")


def test_aggregate_slop_counts_unique_lines_per_category():
    evs = [
        _ev("a.py", 1, Category.PROSE, 5),
        _ev("a.py", 1, Category.PROSE, 2),  # та же строка — не удваивает slop_lines
        _ev("a.py", 9, Category.PROSE, 5),
        _ev("b.py", 3, Category.STYLE, 1),
    ]
    s = aggregate_slop(evs, sloc=100)
    assert s.categories[Category.PROSE].files == 1
    assert s.categories[Category.PROSE].slop_lines == 2
    assert s.categories[Category.PROSE].weight == 12
    assert s.categories[Category.STYLE].files == 1


def test_aggregate_slop_total_and_ratio_with_infected_md():
    evs = [_ev("README.md", 1, Category.DOCS, 5)]
    s = aggregate_slop(evs, sloc=100, infected=[("SPEC.md", 40)])
    # 1 улика + round(40 * 0.8); ratio — доля (33/100), не проценты
    assert s.total == 33
    assert abs(s.ratio - 0.33) < 1e-9
    assert s.infected_md_lines == 32


def test_aggregate_slop_top_files():
    evs = [
        _ev("a.py", 1, Category.PROSE, 5),
        _ev("a.py", 2, Category.PROSE, 5),
        _ev("b.md", 4, Category.DOCS, 2),
    ]
    s = aggregate_slop(evs, sloc=50, infected=[("big.md", 100)])  # +80 строк big.md
    assert s.top_files[0] == ("big.md", 80)
    assert ("a.py", 2) in s.top_files
    assert len(s.top_files) <= 5


def test_aggregate_slop_agency_excluded():
    evs = [_ev(".claude", 0, Category.AGENCY, 3)]
    s = aggregate_slop(evs, sloc=10)
    assert s.total == 0 and s.ratio == 0.0
    assert len(s.agency) == 1
    assert s.details == evs


def test_aggregate_slop_full_formula():
    evs = [
        _ev("a.py", 1, Category.PROSE, 5),
        _ev("a.py", 1, Category.STYLE, 2),  # разные категории на одной строке
        _ev("b.md", 4, Category.DOCS, 2),
        _ev("git:ab12cd34", 2, Category.HISTORY, 5),
        _ev(".claude", 0, Category.AGENCY, 3),  # не входит в SLOP
    ]
    s = aggregate_slop(evs, sloc=50, infected=[("big.md", 100)])
    # уникальных строк с уликами: (a.py,1), (b.md,4), (git:...,2) = 3; md: round(100*.8)=80
    assert s.total == 83
    assert abs(s.ratio - 1.66) < 1e-9  # доля: 83/50


def test_safe_ratio_edges():
    assert safe_ratio(5, 0) == float("inf")
    assert safe_ratio(0, 0) == 0.0
    assert abs(safe_ratio(30, 200) - 0.15) < 1e-9


def test_aggregate_slop_zero_sloc_inf_ratio():
    assert aggregate_slop([_ev("a.md", 1, Category.DOCS, 5)], sloc=0).ratio == float("inf")
    assert aggregate_slop([], sloc=0).ratio == 0.0


def test_volume_stats_defaults():
    v = VolumeStats()
    assert (v.sloc, v.md_files, v.md_lines, v.md_words) == (0, 0, 0, 0)
    assert v.languages == []
    assert isinstance(SlopStats().categories, dict)


def test_language_row_ordering_source():
    rows = [LanguageRow("Python", 2, 8), LanguageRow("C", 1, 9)]
    assert sorted(rows, key=lambda r: -r.sloc)[0].language == "C"


def test_cognitivity_grades():
    assert CategoryTotals(files=1, slop_lines=10, weight=40).cognitivity == "high"
    assert CategoryTotals(files=1, slop_lines=10, weight=20).cognitivity == "medium"
    assert CategoryTotals(files=1, slop_lines=10, weight=5).cognitivity == "low"
    assert CategoryTotals(files=1, slop_lines=0, weight=7).cognitivity == "low"
