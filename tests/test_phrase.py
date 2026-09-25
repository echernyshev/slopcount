from slopcount.detectors.phrase import PhraseDetector
from slopcount.evidence import Category
from slopcount.rules import load_rules
from slopcount.scanner import ScannedFile


def test_hits_in_python_comments():
    det = PhraseDetector(load_rules())
    sf = ScannedFile("a.py", "python", "code", 10)
    src = 'def f():\n    # Great question! But certainly! here\n    return 1\n'
    evs = det.detect(sf, src)
    assert len(evs) == 2
    assert all(e.category is Category.PROSE for e in evs)
    assert all(e.line == 2 for e in evs)
    assert {e.weight for e in evs} == {5}


def test_hits_in_markdown_lines():
    det = PhraseDetector(load_rules())
    sf = ScannedFile("README.md", None, "markdown", 10)
    evs = det.detect(sf, "intro\n\nIt's important to note that this rocks.\n")
    assert len(evs) == 1 and evs[0].line == 3 and evs[0].weight == 2


def test_no_hits_in_code_lines_without_comments():
    det = PhraseDetector(load_rules())
    sf = ScannedFile("a.py", "python", "code", 10)
    assert det.detect(sf, "msg = 'Great question!'\n") == []
