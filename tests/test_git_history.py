import re
import subprocess

import pytest

from slopcount.detectors.git_history import GitUnavailable, detect
from slopcount.evidence import Category


def git(tmp_path, *args, date="2026-01-01T04:00:00"):
    subprocess.run(["git", "-C", str(tmp_path), *args], check=True,
                   capture_output=True, env={"GIT_AUTHOR_NAME": "T", "GIT_AUTHOR_EMAIL": "t@t",
                   "GIT_COMMITTER_NAME": "T", "GIT_COMMITTER_EMAIL": "t@t",
                   "GIT_AUTHOR_DATE": date,
                   "GIT_COMMITTER_DATE": date,
                   "PATH": "/usr/bin:/bin:/usr/local/bin", "HOME": str(tmp_path)})


@pytest.fixture
def repo(tmp_path):
    git(tmp_path, "init", "-q")
    (tmp_path / "a.txt").write_text("hello\n")
    git(tmp_path, "add", ".")
    git(tmp_path, "-c", "user.name=T", "-c", "user.email=t@t", "commit", "-q",
        "-m", "feat: add hello\n\nCo-Authored-By: Claude <noreply@anthropic.com>")
    return tmp_path


def test_detects_coauthor_and_night(repo):
    evs, n = detect(repo, 500)
    assert n == 1
    assert any("Co-Authored-By" in e.description for e in evs)
    assert any("night commit" in e.description for e in evs)


def test_not_a_repo_raises(tmp_path):
    with pytest.raises(GitUnavailable):
        detect(tmp_path, 500)


def test_ref_is_sha8_and_weights(repo):
    evs, _ = detect(repo, 500)
    co = [e for e in evs if "Co-Authored-By" in e.description][0]
    night = [e for e in evs if "night commit" in e.description][0]
    assert re.fullmatch(r"git:[0-9a-f]{8}", co.file)
    assert co.line == 3 and co.weight == 5                 # 3-я строка сообщения
    assert night.line == 1 and night.weight == 1
    assert co.category is Category.HISTORY and night.category is Category.HISTORY


def test_empty_repo_is_zero_commits_not_error(tmp_path):
    git(tmp_path, "init", "-q")
    assert detect(tmp_path, 500) == ([], 0)


def test_velocity_reads_numstat(tmp_path):
    git(tmp_path, "init", "-q")
    (tmp_path / "big.txt").write_text("line\n" * 2500)
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-q", "-m", "big drop", date="2026-06-01T12:00:00")
    evs, n = detect(tmp_path, 500)
    assert n == 1
    v = [e for e in evs if "velocity" in e.description]
    assert v and v[0].line == 0 and v[0].weight == 3 and "2500" in v[0].description


def test_night_boundary_is_hour_le_5(tmp_path):
    git(tmp_path, "init", "-q")
    (tmp_path / "a.txt").write_text("one\n")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-q", "-m", "late", date="2026-06-01T05:00:00")
    (tmp_path / "a.txt").write_text("two\n")
    git(tmp_path, "commit", "-q", "-am", "early", date="2026-06-01T06:00:00")
    evs, n = detect(tmp_path, 500)
    assert n == 2
    nights = [e for e in evs if "night commit" in e.description]
    assert len(nights) == 1 and "(05:00)" in nights[0].description


def test_conventional_perfection_needs_20_commits(tmp_path):
    git(tmp_path, "init", "-q")
    for i in range(19):
        (tmp_path / "a.txt").write_text(f"{i}\n")
        git(tmp_path, "add", ".")
        git(tmp_path, "commit", "-q", "-m", f"fix: nr {i}", date="2026-06-01T12:00:00")
    evs, n = detect(tmp_path, 500)
    assert n == 19
    assert not any("conventional" in e.description for e in evs)
    (tmp_path / "a.txt").write_text("final\n")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-q", "-m", "fix: nr 19", date="2026-06-01T12:00:00")
    evs, n = detect(tmp_path, 500)
    assert n == 20
    conv = [e for e in evs if "conventional" in e.description]
    assert conv and conv[0].file == "git:" and conv[0].weight == 3


def test_timeout_raises_git_unavailable(repo, monkeypatch):
    def boom(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=args[0], timeout=60)
    monkeypatch.setattr(
        "slopcount.detectors.git_history.subprocess.run", boom)
    with pytest.raises(GitUnavailable):
        detect(repo, 500)
