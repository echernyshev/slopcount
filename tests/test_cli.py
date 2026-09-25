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
