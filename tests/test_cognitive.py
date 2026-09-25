from slopcount.metrics.cognitive import approx_cognitive_complexity, halstead_seconds


def test_flat_control_flow_scores_low():
    src = "if a:\n    pass\nif b:\n    pass\n"
    assert approx_cognitive_complexity(src, "python") == 2


def test_nesting_increases_score():
    flat = "if a:\n    pass\nif b:\n    pass\n"
    nested = "if a:\n    if b:\n        if c:\n            pass\n"
    assert approx_cognitive_complexity(nested, "python") > approx_cognitive_complexity(flat, "python")
    # 1 + (1+1) + (1+2) = 6
    assert approx_cognitive_complexity(nested, "python") == 6


def test_halstead_seconds_positive_and_monotone():
    small = halstead_seconds("x = 1\n")
    big = halstead_seconds("x = 1\ny = x + 2 * 3 - x / (1 + 2)\n")
    assert small > 0 and big > small
