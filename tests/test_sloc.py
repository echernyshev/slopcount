from slopcount.metrics.sloc import count_sloc

SRC = '''\
def f():
    """docstring line
    another docstring line
    """
    # comment
    x = 1

    y = 2  # trailing comment counts as code
'''


def test_sloc_excludes_comments_blanks_docstrings():
    assert count_sloc(SRC, "python") == 2


def test_sloc_c_language():
    assert count_sloc("// c\nint x;\n\n/* multi\nline */\nint y;\n", "c") == 2
