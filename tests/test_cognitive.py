import pytest

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


def test_approximation_pins():
    assert approx_cognitive_complexity("if a:\n    pass\nelse:\n    pass\n", "python") == 2
    assert approx_cognitive_complexity("x = a and b\n", "python") == 1
    assert approx_cognitive_complexity("int main() {}\n", "c") == 0
    assert halstead_seconds("just words here\n") == 0.0
    assert halstead_seconds("") == 0.0


def test_exact_mode_treesitter():
    pytest.importorskip("tree_sitter", reason="no [treesitter] extra")
    from slopcount.metrics.cognitive import cognitive_complexity_tspython
    # вложенность: 1 (if a) + 1 (if b) + 2 (if c вложенный) = 4 (Campbell:
    # вложенный оператор стоит 1 + nesting за каждый уровень)
    src = "if a:\n    pass\nif b:\n    if c:\n        pass\n"
    assert cognitive_complexity_tspython(src) == 4
