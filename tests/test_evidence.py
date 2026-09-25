from slopcount.evidence import Category, CategoryTotals, Evidence, aggregate


def _ev(file, line, cat, weight):
    return Evidence(file=file, line=line, category=cat, weight=weight, description="d")


def test_aggregate_counts_unique_slop_lines_per_category():
    evs = [
        _ev("a.py", 1, Category.PROSE, 5),
        _ev("a.py", 1, Category.PROSE, 2),   # та же строка — не удваивает slop_lines
        _ev("a.py", 9, Category.PROSE, 5),
        _ev("b.py", 3, Category.STYLE, 1),
    ]
    report = aggregate(evs, sloc=100)
    assert report.categories[Category.PROSE].files == 1
    assert report.categories[Category.PROSE].slop_lines == 2
    assert report.categories[Category.PROSE].weight == 12
    assert report.categories[Category.STYLE].files == 1


def test_aggregate_slop_and_ratio_with_infected_md():
    evs = [_ev("README.md", 1, Category.DOCS, 5)]
    report = aggregate(evs, sloc=100, infected=[("SPEC.md", 40)])
    # 1 улика + round(40 * 0.8)
    assert report.slop == 33
    assert abs(report.slop_ratio - 33.0) < 1e-9


def test_cognitivity_grades():
    assert CategoryTotals(files=1, slop_lines=10, weight=40).cognitivity == "high"
    assert CategoryTotals(files=1, slop_lines=10, weight=20).cognitivity == "medium"
    assert CategoryTotals(files=1, slop_lines=10, weight=5).cognitivity == "low"


def test_zero_sloc_edge():
    ev = _ev("a.md", 1, Category.DOCS, 5)
    assert aggregate([ev], sloc=0).slop_ratio == float("inf")
    assert aggregate([], sloc=0).slop_ratio == 0.0
    assert CategoryTotals(files=1, slop_lines=0, weight=7).cognitivity == "low"


def test_aggregate_full_slop_formula():
    evs = [
        _ev("a.py", 1, Category.PROSE, 5),
        _ev("a.py", 1, Category.STYLE, 2),      # разные категории на одной строке
        _ev("b.md", 4, Category.DOCS, 2),
        _ev("git:ab12cd34", 2, Category.HISTORY, 5),
        _ev(".claude", 0, Category.AGENCY, 3),  # не входит в SLOP
    ]
    report = aggregate(evs, sloc=50, infected=[("big.md", 100)])
    # уникальных строк с уликами: (a.py,1), (b.md,4), (git:...,2) = 3; md: round(100*.8)=80
    assert report.slop == 83
    assert abs(report.slop_ratio - 166.0) < 1e-9
