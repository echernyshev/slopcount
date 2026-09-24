from slopcount.cli import main


def test_version_flag(capsys):
    from slopcount import __version__
    try:
        main(["--version"])
    except SystemExit as e:
        assert e.code == 0
    out = capsys.readouterr().out
    assert __version__ in out
