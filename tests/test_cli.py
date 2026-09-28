import pytest
from test_e2e import SLOP, plain_output, run_cli

from slopcount.cli import main

pytestmark = pytest.mark.usefixtures("scc_ready")


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


def test_removed_flags_rejected(tmp_path):
    for flag in ("--details", "--fail-above", "--verdict-only"):
        code, _ = run_cli([str(tmp_path), flag, "--lang", "en"])
        assert code == 2


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


def test_unknown_flag_exit_2(tmp_path):
    code, _ = run_cli([str(tmp_path), "--nope", "--lang", "en"])
    assert code == 2


def test_bad_lang_exit_2(tmp_path):
    code, _ = run_cli([str(tmp_path), "--lang", "xx"])
    assert code == 2


def test_help_exit_0():
    code, out = run_cli(["--help"])
    assert code == 0
    for flag in ("--evidence", "--history", "--perplexity"):
        assert flag in out
    assert run_cli(["-h"])[0] == 0


def test_rules_repeated_accumulates(tmp_path):
    r1 = tmp_path / "r1.toml"
    r1.write_text('[[rule]]\npattern = "zqfirst"\nweight = 9\ndescription = "zz-marker-one"\n')
    r2 = tmp_path / "r2.toml"
    r2.write_text('[[rule]]\npattern = "zqsecond"\nweight = 9\ndescription = "zz-marker-two"\n')
    (tmp_path / "a.md").write_text("zqfirst zqsecond\n")
    code, out = run_cli(
        [str(tmp_path), "--evidence", "--lang", "en", "--rules", str(r1), "--rules", str(r2)]
    )
    assert code == 0
    assert "zz-marker-one" in out
    assert "zz-marker-two" in out


def test_pricing_and_wide_flags_accepted(tmp_path):
    (tmp_path / "a.py").write_text("x = 1\n")
    code, out = run_cli(
        [
            str(tmp_path),
            "--lang",
            "en",
            "--personcost",
            "1000",
            "--overhead",
            "1.0",
            "--coffee-price",
            "2.5",
            "--wide",
        ]
    )
    assert code == 0
    assert "SLOC" in out


def test_pricing_values_change_output():
    _code, default_out = run_cli([str(SLOP), "--lang", "en"])
    _code, custom_out = run_cli(
        [
            str(SLOP),
            "--lang",
            "en",
            "--personcost",
            "100",
            "--overhead",
            "1.0",
            "--coffee-price",
            "9",
        ]
    )
    assert default_out != custom_out


def test_no_args_scans_cwd(tmp_path, monkeypatch, capsys):
    (tmp_path / "a.py").write_text("x = 1\n")
    monkeypatch.chdir(tmp_path)
    assert main([]) == 0
    assert "SLOC" in capsys.readouterr().out


def test_history_bare_requires_value(tmp_path, capsys):
    (tmp_path / "a.py").write_text("x = 1\n")
    # прямой вызов main: тот же глушитель цвета, что в run_cli (см. test_e2e)
    with plain_output():
        code = main([str(tmp_path), "--history"])
    assert code == 2
    assert "--history" in capsys.readouterr().err


def test_json_wins_over_csv():
    code, out = run_cli([str(SLOP), "--json", "--csv", "--lang", "en"])
    assert code == 0
    assert out.lstrip().startswith("{")


def test_scc_path_env_exit_2(tmp_path, capsys):
    # явный несуществующий путь → наш RuntimeError, а не typer usage error:
    # проверяем и код, и подсказку в stderr (иначе exit 2 даёт ложный зелёный)
    code, _ = run_cli([str(tmp_path), "--scc-path", "/nonexistent/scc", "--lang", "en"])
    assert code == 2
    assert "scc binary not found" in capsys.readouterr().err


def test_scc_path_valid(tmp_path):
    from slopcount import scc as scc_mod

    try:
        binary = scc_mod.ensure_binary()
    except RuntimeError as exc:
        pytest.skip(f"scc unavailable: {exc}")
    (tmp_path / "a.py").write_text("x = 1\n")
    code, out = run_cli([str(tmp_path), "--scc-path", binary, "--lang", "en"])
    assert code == 0 and "SLOC" in out
