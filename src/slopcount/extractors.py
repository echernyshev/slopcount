from __future__ import annotations

import re
from dataclasses import dataclass

HASH_LANGS = {"ruby", "sh"}
SLASH_LANGS = {
    "javascript",
    "typescript",
    "go",
    "rust",
    "c",
    "cpp",
    "java",
    "php",
    "csharp",
    "swift",
    "kotlin",
    "scala",
}

_TRIPLE = re.compile(r'(?:[rbfu]*)("""|\'\'\')(.*)$')


@dataclass(frozen=True)
class CommentBlock:
    start_line: int  # физическая строка файла, 1-based
    lines: list[str]  # очищенные строки текста комментария
    is_docstring: bool = False


def _clean(text: str) -> str:
    s = text.strip()
    for tok in ("///", "//", "#", "/*", "*/", "*"):
        if s.startswith(tok):
            return s[len(tok) :].strip()
    return s


def extract_comments(text: str, language: str) -> list[CommentBlock]:
    """Приближение: без полноценного лексера строк. Строковые литералы с
    маркерами внутри — редкий шум, принято осознанно (задокументировано).

    Нумерация: start_line — физическая строка файла, 1-based; блок занимает
    ровно len(lines) физических строк, запись k соответствует строке
    start_line + k (пустые строки сохраняются как "").

    Известные приближения: /* ... */ в середине строки после кода не
    распознаётся (только блоки с начала строки); незакрытый docstring даёт
    блок до конца файла, незакрытый C-блок отбрасывается."""
    if language == "python":
        return _python(text)
    if language in HASH_LANGS:
        return _line_comments(text, "#")
    if language in SLASH_LANGS:
        return _slash(text)
    return []


def _line_comments(text: str, marker: str) -> list[CommentBlock]:
    out = []
    for i, line in enumerate(text.split("\n"), 1):
        if marker in line:
            out.append(CommentBlock(i, [_clean(line.split(marker, 1)[1].strip())]))
    return out


def _slash(text: str) -> list[CommentBlock]:
    out: list[CommentBlock] = []
    block: list[str] = []
    start = 0
    for i, line in enumerate(text.split("\n"), 1):
        stripped = line.strip()
        if block:
            if "*/" in stripped:
                block.append(stripped.split("*/", 1)[0].lstrip("*").strip())
                out.append(CommentBlock(start, block))
                block = []
            else:
                block.append(stripped.lstrip("*").strip())
            continue
        if stripped.startswith("/*"):
            start = i
            body = stripped[2:]
            if "*/" in body:
                out.append(CommentBlock(i, [body.split("*/", 1)[0].strip()]))
            else:
                block = [body.strip()]
        elif "//" in line:
            out.append(CommentBlock(i, [_clean(line.split("//", 1)[1].strip())]))
    return out


def _python(text: str) -> list[CommentBlock]:
    out: list[CommentBlock] = []
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if stripped.startswith("#"):
            out.append(CommentBlock(i + 1, [stripped.lstrip("#").strip()]))
            i += 1
            continue
        m = _TRIPLE.match(stripped)
        if m:
            quote, rest = m.group(1), m.group(2)
            if rest.rstrip().endswith(quote):
                # однострочный docstring: """Does the thing."""
                out.append(CommentBlock(i + 1, [rest[: -len(quote)].strip()], True))
                i += 1
                continue
            body = [rest.strip()]
            j = i + 1
            while j < len(lines) and quote not in lines[j]:
                body.append(lines[j].strip())
                j += 1
            if j < len(lines):  # закрывающий ограничитель найден
                body.append(lines[j].split(quote, 1)[0].strip())
            out.append(CommentBlock(i + 1, body, True))
            i = j + 1  # за строку с закрывающим ограничителем
            continue
        if "#" in line:
            out.append(CommentBlock(i + 1, [line.split("#", 1)[1].strip()]))
        i += 1
    return out
