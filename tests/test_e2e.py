import io
from contextlib import redirect_stdout
from pathlib import Path

from slopcount.cli import main

FIXTURES = Path(__file__).parent / "fixtures"
SLOP = FIXTURES / "slop_project"


def run_cli(argv):
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = main(argv)
    return code, buf.getvalue()


def test_mvp_run_on_slop_fixture():
    code, out = run_cli([str(SLOP), "--lang", "en"])
    assert code == 0
    assert "Total Physical Source Lines of Code (SLOC)" in out
    assert "Total Suspicious Lines Of Prose (SLOP)" in out
    assert "Slop Ratio (SLOP/SLOC)" in out
    assert "VERDICT:" in out
    assert "Prose (comments/docstrings)" in out


def test_exit_zero_and_version_still_works():
    assert run_cli(["--version"])[0] == 0


def test_docs_category_in_output():
    import re
    code, out = run_cli([str(SLOP), "--lang", "en"])
    m = re.search(r"Markdown specs\s+\d+\s+(\d+)", out)
    assert m and int(m.group(1)) == 2          # DOCS slop lines from fixture
    assert "= 13" in out                       # total SLOP: 7 evidence lines + 6 infected


def test_style_category_in_output():
    import re
    code, out = run_cli([str(SLOP), "--lang", "en"])
    m = re.search(r"Code style\s+\d+\s+(\d+)", out)
    assert m and int(m.group(1)) == 2          # STYLE: defensive.py lines 2+13
    assert re.search(r"Total Suspicious Lines Of Prose \(SLOP\)\s+= \d+", out)
    assert "= 13" in out                       # 3 prose + 2 docs + 2 style + 6 infected
