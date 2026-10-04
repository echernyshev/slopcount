import io
import os
import subprocess
import time
from contextlib import contextmanager, redirect_stdout
from pathlib import Path

import pytest

from slopcount.cli import main
from slopcount.detectors.perplexity import available

FIXTURES = Path(__file__).parent / "fixtures"
SLOP = FIXTURES / "slop_project"
HUMAN = FIXTURES / "human_project"

pytestmark = pytest.mark.usefixtures("scc_ready")

GIT_ENV = {
    "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_CONFIG_GLOBAL": os.devnull,
}


@contextmanager
def plain_output():
    """На время вызова глушит цвет принудительно (NO_COLOR=1, FORCE_COLOR убран)
    и восстанавливает окружение. На машинах разработчиков с FORCE_COLOR=3
    typer/rich красят help и usage-ошибки даже при redirect_stdout в StringIO —
    строгие подстрочные ассерты падают. GITHUB_ACTIONS вычищаем тоже: rich
    считает раннер GitHub Actions терминалом и красит стили (bold/dim) даже
    при NO_COLOR — без этого два теста CLI падают только в CI."""
    saved = {
        key: os.environ.pop(key, None) for key in ("FORCE_COLOR", "NO_COLOR", "GITHUB_ACTIONS")
    }
    os.environ["NO_COLOR"] = "1"
    try:
        yield
    finally:
        for key, val in saved.items():
            if val is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = val


def run_cli(argv):
    buf = io.StringIO()
    with plain_output(), redirect_stdout(buf):
        code = main(argv)
    return code, buf.getvalue()


def test_mvp_run_on_slop_fixture():
    code, out = run_cli([str(SLOP), "--lang", "en"])
    assert code == 0
    assert "PROJECT VOLUME" in out
    assert "Total SLOC" in out
    assert "Detected SLOP" in out
    assert "DETECTED SLOP" in out
    assert "Prose (comments/docstrings)" in out


def test_exit_zero_and_version_still_works():
    assert run_cli(["--version"])[0] == 0


def test_docs_category_in_output():
    import re

    _code, out = run_cli([str(SLOP), "--lang", "en"])
    m = re.search(r"Markdown specs\s+\d+\s+(\d+)", out)
    assert m and int(m.group(1)) == 2  # DOCS slop lines from fixture
    assert re.search(r"Detected SLOP\s+= 16", out)  # 7 evidence lines + 9 infected


def test_style_category_in_output():
    import re

    _code, out = run_cli([str(SLOP), "--lang", "en"])
    m = re.search(r"Code style\s+\d+\s+(\d+)", out)
    assert m and int(m.group(1)) == 2  # STYLE: defensive.py lines 2+13
    assert re.search(r"Detected SLOP\s+= 16", out)  # 3 prose + 2 docs + 2 style + 9 infected


def test_agency_row_in_output():
    import re

    _code, out = run_cli([str(SLOP), "--lang", "en"])
    m = re.search(r"Environment markers\s+(\d+)", out)
    assert m and int(m.group(1)) == 1  # AGENCY: fixture CLAUDE.md marker


def test_history_flag_on_git_repo(tmp_path):
    import re

    env = {
        **GIT_ENV,
        "GIT_AUTHOR_DATE": "2026-06-01T12:00:00",
        "GIT_COMMITTER_DATE": "2026-06-01T12:00:00",
    }
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True, env=GIT_ENV)
    (tmp_path / "x.md").write_text("# 🚀 doc\n")
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True, env=GIT_ENV)
    subprocess.run(
        [
            "git",
            "-C",
            str(tmp_path),
            "-c",
            "user.name=T",
            "-c",
            "user.email=t@t",
            "commit",
            "-q",
            "-m",
            "feat: x",
        ],
        check=True,
        env=env,
    )
    code, out = run_cli([str(tmp_path), "--history", "10", "--lang", "en"])
    assert code == 0
    # 1 коммит, полдень → ни одной history-улики; счётчик коммитов в строке
    assert re.search(r"Git history \(1\)\s+0\s+0", out)
    assert re.search(r"Detected SLOP\s+= \d+", out)


def test_history_flag_on_non_repo_skips_archaeology(tmp_path):
    import re

    (tmp_path / "m.py").write_text("x = 1\n")
    code, out = run_cli([str(tmp_path), "--history", "5", "--lang", "en"])
    assert code == 0
    assert re.search(r"Git history\s+\d", out)  # строка есть, без (N)
    assert "Git history (" not in out


def test_recursion_grade_on_pure_slop(tmp_path):
    (tmp_path / "ONLY_SLOP.md").write_text("Great question! " * 200)
    _code, out = run_cli([str(tmp_path), "--lang", "en"])
    assert "RECURSION" in out


def test_slocomo_block_present():
    _code, out = run_cli([str(SLOP), "--lang", "en"])
    assert "COMPREHENSION EFFORT & COST" in out
    assert "Reading documentation" in out
    assert "Total reading time" in out
    assert "Team Comprehension Cost" in out
    assert "GPU-hours of Regret" in out


def test_no_therapy_hides_line():
    _code, out = run_cli([str(SLOP), "--no-therapy", "--lang", "en"])
    assert "Therapy Recommended" not in out
    assert "Coffee Required" in out


def test_evidence_lists_findings_with_snippets():
    _code, out = run_cli([str(SLOP), "--evidence", "--lang", "en"])
    assert "EVIDENCE" in out
    assert "greeter.py" in out
    assert "[prose]" in out and "+5" in out
    assert "|" in out  # разделитель сниппета исходной строки


def test_evidence_ru_translated():
    _code, out = run_cli([str(SLOP), "--evidence", "--lang", "ru"])
    assert "УЛИКИ" in out
    assert "greeter.py" in out
    assert "Классический энтузиазм LLM" in out  # описание улики из каталога фраз


def test_ru_output():
    _code, out = run_cli([str(SLOP), "--lang", "ru"])
    assert "ОБЪЁМ ПРОЕКТА" in out
    assert "УСИЛИЕ И СТОИМОСТЬ ПОНИМАНИЯ" in out
    assert "Итоги по источникам слопа" in out
    assert "понять" in out  # §11: comprehension, не «осознать» (Лестница затрат)


def test_ru_table_headers_and_cognitivity():
    _code, out = run_cli([str(SLOP), "--lang", "ru"])
    assert "Источник" in out and "файлы" in out and "строки слопа" in out
    assert "когнитивная сложность" in out
    assert "высокая" in out  # Prose row: cognitivity=high
    assert "Требуется кофе" in out and "чашка" in out


def test_ru_stderr_messages(tmp_path, capsys):
    (tmp_path / "m.py").write_text("x = 1\n")
    assert (
        main(
            [
                "--lang",
                "ru",
                str(tmp_path),
                str(tmp_path),
                "--history",
                "5",
                "--rules",
                str(tmp_path / "nope.toml"),
            ]
        )
        == 0
    )
    err = capsys.readouterr().err
    assert "указано несколько путей" in err  # multi-path warning
    assert "git-история недоступна" in err  # git unavailable
    assert "файл правил не найден" in err  # rules file skipped
    assert main(["--lang", "ru", str(tmp_path / "nope")]) == 2
    assert "путь не найден" in capsys.readouterr().err


def test_perplexity_without_extras_exit_2():
    if available():
        pytest.skip("extras installed")
    code, _out = run_cli([str(SLOP), "--perplexity", "--lang", "en"])
    assert code == 2


def test_human_fixture_stays_clean():
    _code, out = run_cli([str(HUMAN), "--lang", "en"])
    assert "Slop-to-Code Ratio (SLOP/SLOC)" in out
    # фиксируем: человеческий код не параноится — ratio < 10%
    import re

    m = re.search(r"Slop-to-Code Ratio \(SLOP/SLOC\)\s*=\s*([\d.,]+)", out)
    assert m and float(m.group(1).replace(",", "")) < 0.10
    assert "HUMAN" in out  # md=0 → HUMAN; README у фикстуры отсутствует by design
    assert "Almost human" in out


def test_perf_smoke_2k_files(tmp_path):
    deep = tmp_path / "pkg"
    deep.mkdir()
    for i in range(2000):
        (deep / f"m{i}.py").write_text(f"def f{i}():\n    return {i}\n")
    t0 = time.monotonic()
    code, _ = run_cli([str(tmp_path), "--lang", "en"])
    assert code == 0 and time.monotonic() - t0 < 15


def test_run_reports_md_and_comment_metrics(tmp_path):
    from slopcount.app import Options, run

    (tmp_path / "a.py").write_text("x = 1\ny = 2  # trailing\n")
    (tmp_path / "doc.md").write_text("# t\n\ntext\n")
    (tmp_path / "spec.rst").write_text("rst docs\n")
    report = run(Options(paths=[str(tmp_path)]))
    v = report.volume
    assert v.md_files == 1  # .rst не считается
    assert v.md_lines == 3
    assert abs(v.md_sloc_ratio - 1.5) < 1e-9
    assert v.comment_lines == 0
    assert abs(v.comment_sloc_ratio - 0.0) < 1e-9
    assert v.md_words == 5  # doc.md («#», «t», «text») + spec.rst («rst», «docs»): md_words —
    # честный Σ слов kind=markdown+prose, «#» — отдельный токен, .rst не фильтруется


def test_run_wires_new_model_blocks(tmp_path):
    from slopcount.app import Options, run

    (tmp_path / "a.py").write_text("x = 1\n")
    (tmp_path / "d.md").write_text("# head\nbody\n")
    (tmp_path / "p.txt").write_text("plain prose\n")
    (tmp_path / "c.json").write_text('{"k": 1}\n')
    report = run(Options(paths=[str(tmp_path)]))
    v = report.volume
    assert v.files_total == 4
    assert v.sloc == 1
    langs = {r.language: r for r in v.languages}
    assert langs["Python"].sloc == 1 and langs["Python"].files == 1
    assert v.md_files == 1 and v.md_lines == 2
    assert v.md_words == 5  # md («# head» + «body») + prose («plain prose»)
    assert report.slop.total == 0  # чистое дерево
    cb = report.cocomo_breakdown
    assert cb is not None
    sc = cb.buckets["source_code"]
    assert set(cb.buckets) == {"docs", "source_code", "data"}
    assert sc["code"].lines == 1  # a.py
    assert sc["total"] == sc["code"] and sc["comments"] is None  # scc комментарии не считает
    assert cb.buckets["docs"].lines >= 2  # md-код + prose-строка (docs = markdown+prose)
    assert cb.buckets["data"].lines >= 1  # c.json
    lb = report.locomo_breakdown
    assert lb is not None and set(lb) == {"docs", "source_code", "data"}
    assert lb["source_code"]["comments"] is None
    assert (
        abs(
            lb["docs"].cost + lb["source_code"]["total"].cost + lb["data"].cost - report.locomo.cost
        )
        < 1e-9
    )


def test_unreadable_code_file_counts_in_volume(tmp_path):
    from slopcount.app import Options, run

    (tmp_path / "a.py").write_text("x = 1\n")
    (tmp_path / "bad.py").write_bytes("s = 'привет'\n".encode("cp1251"))
    report = run(Options(paths=[str(tmp_path)]))
    # объём — факт о дереве из манифеста: нечитаемый (skip) файл в SLOC входит
    assert report.skip_count == 1
    assert report.volume.sloc == 2


def test_run_docs_only_repo_inf_md_ratio(tmp_path):
    from slopcount.app import Options, run

    (tmp_path / "ONLY.md").write_text("just text\n")
    report = run(Options(paths=[str(tmp_path)]))
    assert report.volume.md_sloc_ratio == float("inf")


def test_run_counts_uppercase_md_extension(tmp_path):
    from slopcount.app import Options, run

    (tmp_path / "a.py").write_text("x = 1\n")
    (tmp_path / "README.MD").write_text("# head\nbody\n")
    report = run(Options(paths=[str(tmp_path)]))
    assert report.volume.md_files == 1
    assert report.volume.md_lines == 2


def test_volume_languages_breakdown(tmp_path):
    from slopcount.app import Options, run

    (tmp_path / "a.py").write_text("x = 1\n")
    (tmp_path / "b.c").write_text("int b() { return 42; }\n")
    report = run(Options(paths=[str(tmp_path)]))
    langs = {row.language: row for row in report.volume.languages}
    assert langs["Python"].sloc == 1 and langs["Python"].files == 1
    assert langs["C"].sloc == 1


def test_md_sloc_lines_in_output():
    _code, out = run_cli([str(SLOP), "--lang", "en"])
    assert "Documentation-to-Code Ratio (MD/SLOC)" in out
    assert "RECURSION" in out
    assert "Comments-to-Code Ratio (comment/SLOC)" in out
    assert "Slop-to-Code Ratio (SLOP/SLOC)" in out


def test_ru_md_sloc_lines():
    _code, out = run_cli([str(SLOP), "--lang", "ru"])
    assert "Доля документации к коду (MD/SLOC)" in out
    assert "Доля комментариев к коду (comment/SLOC)" in out
