import io
import os
import subprocess
import time
from contextlib import redirect_stdout
from pathlib import Path

import pytest

from slopcount.cli import main
from slopcount.detectors.perplexity import available

FIXTURES = Path(__file__).parent / "fixtures"
SLOP = FIXTURES / "slop_project"
HUMAN = FIXTURES / "human_project"

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


def test_recursion_verdict_on_pure_slop(tmp_path):
    (tmp_path / "ONLY_SLOP.md").write_text("Great question! " * 200)
    code, out = run_cli([str(tmp_path), "--lang", "en"])
    assert "Recursion" in out


def test_slocomo_block_present():
    code, out = run_cli([str(SLOP), "--lang", "en"])
    assert "Cognitive Awareness Effort" in out
    assert "Total Estimated Cost to Comprehend" in out
    assert "GPU-hours of Regret" in out
    assert "(SLOCOMO model, Person-Months = 2.4 * (KSLOP**1.05))" in out


def test_no_therapy_hides_line():
    code, out = run_cli([str(SLOP), "--no-therapy", "--lang", "en"])
    assert "Therapy Recommended" not in out
    assert "Coffee Required" in out


def test_details_lists_evidence():
    code, out = run_cli([str(SLOP), "--details", "--lang", "en"])
    assert "DETAILS" in out
    assert "greeter.py" in out
    assert "[prose]" in out and "+5" in out


def test_ru_output():
    code, out = run_cli([str(SLOP), "--lang", "ru"])
    assert "ВЕРДИКТ:" in out and "Доля слопа" in out
    assert "Итоги по источникам слопа" in out


def test_ru_table_headers_and_cognitivity():
    code, out = run_cli([str(SLOP), "--lang", "ru"])
    assert "Источник" in out and "файлы" in out and "строки слопа" in out
    assert "когнитивность" in out
    assert "высокая" in out                       # Prose row: cognitivity=high
    assert "Требуется кофе" in out and "чашка" in out


def test_ru_stderr_messages(tmp_path, capsys):
    (tmp_path / "m.py").write_text("x = 1\n")
    assert main(["--lang", "ru", str(tmp_path), str(tmp_path),
                 "--history", "5", "--rules", str(tmp_path / "nope.toml")]) == 0
    err = capsys.readouterr().err
    assert "указано несколько путей" in err        # multi-path warning
    assert "git-история недоступна" in err         # git unavailable
    assert "файл правил не найден" in err          # rules file skipped
    assert main(["--lang", "ru", str(tmp_path / "nope")]) == 2
    assert "путь не найден" in capsys.readouterr().err


def test_perplexity_without_extras_exit_2():
    if available():
        pytest.skip("extras installed")
    code, out = run_cli([str(SLOP), "--perplexity", "--lang", "en"])
    assert code == 2


def test_human_fixture_stays_clean():
    code, out = run_cli([str(HUMAN), "--lang", "en"])
    assert "Slop Ratio (SLOP/SLOC)" in out
    # фиксируем: человеческий код не параноится — ratio < 10%
    import re
    m = re.search(r"Slop Ratio \(SLOP/SLOC\)\s*=\s*([\d.,]+)%", out)
    assert m and float(m.group(1).replace(",", "")) < 10.0


def test_perf_smoke_2k_files(tmp_path):
    deep = tmp_path / "pkg"
    deep.mkdir()
    for i in range(2000):
        (deep / f"m{i}.py").write_text(f"def f{i}():\n    return {i}\n")
    t0 = time.monotonic()
    code, _ = run_cli([str(tmp_path), "--lang", "en"])
    assert code == 0 and time.monotonic() - t0 < 15
