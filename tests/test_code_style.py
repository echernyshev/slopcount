from slopcount.detectors.code_style import CodeStyleDetector
from slopcount.evidence import Category
from slopcount.scanner import ScannedFile

SF = ScannedFile("m.py", "python", "code", 0)


def test_trivial_docstring_flagged():
    det = CodeStyleDetector()
    evs = det.detect(SF, "def add(a, b):\n    '''Adds two numbers and returns the result.'''\n    return a + b\n")
    assert any(e.description == "trivial docstring on obvious function" for e in evs)
    assert all(e.category is Category.STYLE for e in evs)


def test_docstring_longer_than_body():
    det = CodeStyleDetector()
    src = "def f():\n    '''Line1\n    Line2\n    Line3\n    Line4\n    Line5\n    '''\n    return 1\n"
    evs = det.detect(SF, src)
    assert any("docstring longer than" in e.description for e in evs)


def test_catch_all_density():
    det = CodeStyleDetector()
    src = "\n".join(
        f"try:\n    f{d}()\nexcept Exception:\n    pass" for d in range(6)
    ) + "\nx = 1\n" * 40
    evs = det.detect(SF, src)
    assert sum(e.weight for e in evs if "catch-all" in e.description) >= 6


def test_emoji_in_comment():
    det = CodeStyleDetector()
    evs = det.detect(SF, "# 🎉 shipped it\nx = 1\n")
    assert any("emoji in code comment" in e.description for e in evs)


def test_clean_human_code_not_flagged():
    det = CodeStyleDetector()
    src = "/* parse args */\nint n = argc;\nfor (;;) {}\n"
    assert det.detect(ScannedFile("m.c", "c", "code", 0), src) == []


def test_docstring_perfection_flagged():
    det = CodeStyleDetector()
    funcs = []
    for i in range(6):
        funcs.append(
            f"def f{i}(x):\n    '''Does f{i}.\n\n    Args:\n        x: value\n\n    Returns:\n        result\n    '''\n    return x + {i}\n"
        )
    evs = det.detect(SF, "".join(funcs))
    assert any("textbook-perfect docstrings" in e.description for e in evs)


def test_monotone_comments_flagged():
    det = CodeStyleDetector()
    body = "\n".join(f"def f{i}():\n    return {i}\n" for i in range(6))
    comments = "\n".join("# performs the computation step now" for _ in range(12))
    evs = det.detect(SF, comments + "\n" + body)
    assert any("monotone comment length" in e.description for e in evs)


def test_negative_boundaries():
    det = CodeStyleDetector()
    four = "\n".join(f"try:\n    f{d}()\nexcept Exception:\n    pass" for d in range(4))
    assert not [e for e in det.detect(SF, four + "\nx = 1\n" * 20) if "density" in e.description]
    nine = "\n".join("# performs the computation step now" for _ in range(9))
    assert not [e for e in det.detect(SF, nine + "\nx = 1\n") if "monotone" in e.description]
    assert det.detect(SF, "catch (event) {}\n") == []
