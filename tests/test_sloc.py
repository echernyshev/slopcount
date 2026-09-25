from slopcount.metrics.sloc import count_sloc

SRC = '''\
def f():
    """docstring line
    another docstring line
    """
    # comment
    x = 1

    y = 2  # trailing comment: whole line excluded (no columns)
'''


def test_sloc_excludes_comments_blanks_docstrings():
    assert count_sloc(SRC, "python") == 2


def test_sloc_c_language():
    assert count_sloc("// c\nint x;\n\n/* multi\nline */\nint y;\n", "c") == 2


def test_sloc_edge_cases():
    assert count_sloc("", "python") == 0
    assert count_sloc("   \n\t\n", "python") == 0
    assert count_sloc("int x;\nint y;", "c") == 2  # no trailing newline
    assert count_sloc("-- sql\nselect 1;\n", "sql") == 2  # unknown lang: all non-blank
