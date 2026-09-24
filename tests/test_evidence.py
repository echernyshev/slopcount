from slopcount.evidence import Category, CategoryTotals, Evidence, Report, aggregate


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
