import io
import os
import subprocess
from contextlib import redirect_stdout
from pathlib import Path

from slopcount.cli import main

FIXTURES = Path(__file__).parent / "fixtures"
SLOP = FIXTURES / "slop_project"

GIT_ENV = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"),
           "GIT_CONFIG_NOSYSTEM": "1",
           "GIT_CONFIG_GLOBAL": os.devnull}


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


def test_agency_row_in_output():
    import re
    code, out = run_cli([str(SLOP), "--lang", "en"])
    m = re.search(r"Environment markers\s+(\d+)", out)
    assert m and int(m.group(1)) == 1          # AGENCY: fixture CLAUDE.md marker


def test_history_flag_on_git_repo(tmp_path):
    import re
    env = {**GIT_ENV,
           "GIT_AUTHOR_DATE": "2026-06-01T12:00:00",
           "GIT_COMMITTER_DATE": "2026-06-01T12:00:00"}
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True, env=GIT_ENV)
    (tmp_path / "x.md").write_text("# 🚀 doc\n")
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True, env=GIT_ENV)
    subprocess.run(["git", "-C", str(tmp_path), "-c", "user.name=T", "-c",
                    "user.email=t@t", "commit", "-q", "-m", "feat: x"],
                   check=True, env=env)
    code, out = run_cli([str(tmp_path), "--history", "10", "--lang", "en"])
    assert code == 0
    # 1 коммит, полдень → ни одной history-улики; счётчик коммитов в строке
    assert re.search(r"Git history \(1\)\s+0\s+0", out)
    assert re.search(r"Total Suspicious Lines Of Prose \(SLOP\)\s+= \d+", out)


def test_history_flag_on_non_repo_skips_archaeology(tmp_path):
    import re
    (tmp_path / "m.py").write_text("x = 1\n")
    code, out = run_cli([str(tmp_path), "--history", "5", "--lang", "en"])
    assert code == 0
    assert re.search(r"Git history\s+\d", out)     # строка есть, без (N)
    assert "Git history (" not in out
