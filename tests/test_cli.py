from test_e2e import SLOP, run_cli

from slopcount.cli import main


def test_version_flag(capsys):
    from slopcount import __version__

    try:
        main(["--version"])
    except SystemExit as e:
        assert e.code == 0
    out = capsys.readouterr().out
    assert __version__ in out


def test_cli_runs_on_directory(tmp_path, capsys):
    (tmp_path / "a.py").write_text("x = 1\n")
    assert main(["--lang", "en", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "SLOC" in out


def test_fail_above_triggers_exit_1():
    code, out = run_cli([str(SLOP), "--fail-above", "5", "--verdict-only", "--lang", "en"])
    assert code == 1 and out.startswith("VERDICT:")


def test_fail_below_ok():
    code, _ = run_cli([str(SLOP), "--fail-above", "200", "--lang", "en"])
    assert code == 0


def test_runtime_error_exit_2(tmp_path):
    code, _ = run_cli([str(tmp_path / "nope"), "--lang", "en"])
    assert code == 2


def test_file_path_exit_2(tmp_path):
    f = tmp_path / "x.py"
    f.write_text("x = 1\n")
    code, _ = run_cli([str(f), "--lang", "en"])
    assert code == 2


def test_bad_rules_exit_2(tmp_path):
    bad = tmp_path / "bad.toml"
    bad.write_text('[[rule]]\npattern = "([unclosed"\n')
    code, _ = run_cli([str(tmp_path), "--rules", str(bad), "--lang", "en"])
    assert code == 2
