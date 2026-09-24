from __future__ import annotations

from slopcount.extractors import extract_comments


def count_sloc(text: str, language: str) -> int:
    """Физический SLOC: непустые строки, не являющиеся комментариями
    целиком (докстринги — комментарии). Ограничение сканера: строка «код +
    трейлинг-комментарий» тоже исключается — колонок у нас нет."""
    lines = text.split("\n")
    comment_lines: set[int] = set()
    for block in extract_comments(text, language):
        # инвариант: блок занимает ровно len(lines) физических строк,
        # начиная со start_line (пустые строки НЕ фильтруются)
        comment_lines.update(range(block.start_line, block.start_line + len(block.lines)))
    n = 0
    for i, line in enumerate(lines, 1):
        if line.strip() and i not in comment_lines:
            n += 1
    return n
