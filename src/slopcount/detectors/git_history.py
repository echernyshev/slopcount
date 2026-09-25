"""git-археология слопа. Функция, а не класс: stateless, возвращает
(улики, счётчик коммитов); вызывается только при --history."""

from __future__ import annotations

import re
import subprocess
from datetime import datetime
from pathlib import Path

from slopcount.detectors import EMOJI_RE
from slopcount.evidence import Category, Evidence
from slopcount.i18n import _, ngettext

_REC = re.compile(r"^(\d+)\t(\d+)\t(.+)$")
_COAUTHOR = re.compile(r"Co-Authored-By:.*(?:Claude|Copilot|GPT|Gemini|aider)", re.I)
_GENERATED = re.compile(r"^Generated with (?:Claude Code|Cursor|Copilot|Gemini)", re.I | re.M)
_AIDER = re.compile(r"^(?:aider\b|🤖):?", re.I)
_CONVENTIONAL = re.compile(
    r"^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)(\(.+\))?: .+"
)


class GitUnavailable(Exception):
    pass


def detect(root: Path, limit: int) -> tuple[list[Evidence], int]:
    try:
        out = subprocess.run(
            [
                "git",
                "-C",
                str(root),
                "log",
                f"-{limit}",
                "--no-color",
                # %x1e в начале записи: numstat коммита остаётся внутри его же
                # записи (git печатает diff после разделителя записей)
                "--pretty=format:%x1e%H%x00%aI%x00%B",
                "--numstat",
            ],
            capture_output=True,
            check=True,
            timeout=60,
            encoding="utf-8",
            errors="replace",
        ).stdout
    except subprocess.CalledProcessError as exc:
        if _unborn_head(root):
            return [], 0
        raise GitUnavailable(str(exc)) from exc
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        raise GitUnavailable(str(exc)) from exc

    evidences: list[Evidence] = []
    subjects: list[str] = []
    commits = [r for r in out.split("\x1e") if r.strip()]
    for record in commits:
        chunk = record.strip().split("\x00", 2)
        if len(chunk) < 3:
            continue
        sha, aiso, body = chunk[0].strip(), chunk[1], chunk[2]
        ref = f"git:{sha[:8]}"
        lines = body.split("\n")
        subject = lines[0].strip() if lines else ""
        subjects.append(subject)
        for i, line in enumerate(lines, 1):
            if _COAUTHOR.search(line):
                evidences.append(Evidence(ref, i, Category.HISTORY, 5, _("Co-Authored-By an AI")))
        if _GENERATED.search(body):
            evidences.append(Evidence(ref, 1, Category.HISTORY, 5, _("'Generated with' trailer")))
        if _AIDER.match(subject):
            evidences.append(Evidence(ref, 1, Category.HISTORY, 3, _("aider prefix")))
        if EMOJI_RE.search(subject):
            evidences.append(Evidence(ref, 1, Category.HISTORY, 2, _("emoji in commit subject")))
        hour = _hour(aiso)
        if hour is not None and hour <= 5:
            evidences.append(
                Evidence(ref, 1, Category.HISTORY, 1, _("night commit (%02d:00)") % hour)
            )
        # numstat — строгий хвост записи: с конца до первой не-numstat строки,
        # чтобы цитаты вида "12\t34\tpath" в тексте коммита не считались
        numstat_lines: list[str] = []
        for line in reversed(lines):
            if _REC.match(line.strip()):
                numstat_lines.append(line.strip())
            else:
                break
        changed = sum(
            int(_REC.match(ln).group(1)) + int(_REC.match(ln).group(2)) for ln in numstat_lines
        )
        if changed > 2000:
            evidences.append(
                Evidence(
                    ref,
                    0,
                    Category.HISTORY,
                    3,
                    ngettext("machine velocity (%d line)", "machine velocity (%d lines)", changed)
                    % changed,
                )
            )
    if len(subjects) >= 20 and all(_CONVENTIONAL.match(s) for s in subjects):
        evidences.append(
            Evidence(
                "git:", 0, Category.HISTORY, 3, _("100% conventional commits (humans get tired)")
            )
        )
    return evidences, len(commits)


def _unborn_head(root: Path) -> bool:
    """Пустой репозиторий (нет ни одного коммита): не ошибка, а 0 коммитов.
    Выход git локализован, поэтому различаем по коду rev-parse (1 = unborn)."""
    try:
        return (
            subprocess.run(
                ["git", "-C", str(root), "rev-parse", "--verify", "-q", "HEAD"],
                capture_output=True,
                timeout=60,
            ).returncode
            == 1
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _hour(aiso: str) -> int | None:
    try:
        return datetime.fromisoformat(aiso).hour
    except ValueError:
        return None
