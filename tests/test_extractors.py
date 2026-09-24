from slopcount.extractors import extract_comments


PY = '''\
def f():
    """Does the thing.

    Great question! Let's delve into it.
    """
    x = 1  # Initialize the counter
# top-level comment
'''


def test_python_comments_and_docstrings():
    blocks = extract_comments(PY, "python")
    doc = [b for b in blocks if b.is_docstring]
    assert len(doc) == 1
    assert doc[0].start_line == 2
    assert any("Great question!" in line for b in doc for line in b.lines)
    inline = [(b.start_line, b.lines[0]) for b in blocks if not b.is_docstring]
    # физические номера строк файла (докстринг занимает строки 2-5)
    assert (6, "Initialize the counter") in inline
    assert (7, "top-level comment") in inline


C_LIKE = '''\
// setup the engine
int x = 1;
/* block
   of wisdom */
int y = 2;  // trailing note
'''


def test_c_style_comments():
    blocks = extract_comments(C_LIKE, "c")
    texts = [line for b in blocks for line in b.lines]
    assert "setup the engine" in texts
    assert "block" in texts and "of wisdom" in texts
    assert "trailing note" in texts


def test_unknown_language_returns_empty():
    assert extract_comments("whatever", "brainfuck") == []
