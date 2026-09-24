from __future__ import annotations

import fnmatch
import os
from dataclasses import dataclass
from pathlib import Path

SKIP_DIRS = {
    ".git", ".hg", ".svn", "node_modules", ".venv", "venv", "env",
    "__pycache__", "dist", "build", "target", ".tox", ".mypy_cache",
    ".pytest_cache", ".ruff_cache", ".idea", ".vscode", ".eggs", ".serena",
}

CODE_EXTS = {
    ".py": "python", ".js": "javascript", ".mjs": "javascript",
    ".cjs": "javascript", ".ts": "typescript", ".tsx": "typescript",
    ".jsx": "javascript", ".go": "go", ".rs": "rust", ".c": "c", ".h": "c",
    ".cpp": "cpp", ".cc": "cpp", ".hpp": "cpp", ".java": "java",
    ".rb": "ruby", ".sh": "sh", ".bash": "sh", ".zsh": "sh", ".php": "php",
    ".cs": "csharp", ".swift": "swift", ".kt": "kotlin", ".kts": "kotlin",
    ".scala": "scala",
}
PROSE_EXTS = {".md": "markdown", ".markdown": "markdown", ".rst": "markdown",
              ".txt": "prose"}


@dataclass(frozen=True)
class ScannedFile:
    path: str            # posix-путь относительно корня
    language: str | None
    kind: str            # "code" | "markdown" | "prose" | "other"
    size: int


class Gitignore:
    """Упрощённый .gitignore: пустые строки/#комментарии игнорируются,
    паттерны без '/' матчатся по имени компоненты пути; литеральные паттерны
    с '/' — по префиксу пути; glob-паттерны — через fnmatch.
    Полной git-семантики нет — осознанно."""

    def __init__(self, root: Path):
        self.patterns: list[str] = []
        gi = root / ".gitignore"
        if gi.is_file():
            for raw in gi.read_text(encoding="utf-8", errors="replace").splitlines():
                line = raw.strip()
                if line and not line.startswith("!") and not line.startswith("#"):
                    self.patterns.append(line.rstrip("/"))

    def matches(self, relpath: str) -> bool:
        parts = Path(relpath).parts
        for pat in self.patterns:
            if "/" in pat:
                if relpath == pat or relpath.startswith(pat + "/"):
                    return True
                if fnmatch.fnmatch(relpath, f"*{pat}") or fnmatch.fnmatch(relpath, pat):
                    return True
            else:
                if any(fnmatch.fnmatch(p, pat) for p in parts):
                    return True
        return False


def scan(root: Path) -> list[ScannedFile]:
    ignore = Gitignore(root)
    out: list[ScannedFile] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            full = Path(dirpath) / name
            rel = full.relative_to(root).as_posix()
            if ignore.matches(rel):
                continue
            ext = full.suffix.lower()
            if ext in CODE_EXTS:
                kind, lang = "code", CODE_EXTS[ext]
            elif ext in PROSE_EXTS:
                kind, lang = PROSE_EXTS[ext], None
            else:
                kind, lang = "other", None
            try:
                size = full.stat().st_size
            except OSError:
                continue
            out.append(ScannedFile(rel, lang, kind, size))
    return sorted(out, key=lambda f: f.path)


def read_text(path: Path) -> str | None:
    """None для бинарных/нечитаемых файлов (счётчик skip)."""
    try:
        raw = path.read_bytes()
        if b"\0" in raw[:1024]:
            return None
        return raw.decode("utf-8")
    except (OSError, UnicodeDecodeError):
        return None
