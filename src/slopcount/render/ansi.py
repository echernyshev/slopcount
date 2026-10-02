"""ANSI-подсветка текстового отчёта.

Глобальное состояние в духе :func:`slopcount.i18n.setup`: cli один раз
резолвит флаг (``--color/--no-color``/авто) до первого рендера. Все хелперы
при выключенном флаге — тождественны, поэтому golden-тесты, пайпы и
``--json``/``--csv`` видят чистый текст.
"""

from __future__ import annotations

import os
import sys
from typing import IO

_enabled = False

_RESET = "\x1b[0m"


def autodetect(stream: IO | None = None) -> bool:
    """Цвет включён? NO_COLOR (no-color.org, любое непустое значение) бьёт
    всё; FORCE_COLOR включает даже без терминала; иначе — isatty потока
    (по умолчанию sys.stdout; redirect_stdout в StringIO честно гасит)."""
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    stream = stream if stream is not None else sys.stdout
    try:
        return bool(stream.isatty())
    except (AttributeError, ValueError):  # нет isatty / закрытый поток
        return False


def set_enabled(value: bool) -> None:
    global _enabled
    _enabled = value


def is_enabled() -> bool:
    return _enabled


def _paint(text: str, code: str) -> str:
    return f"\x1b[{code}m{text}{_RESET}" if _enabled else text


def bold(text: str) -> str:
    return _paint(text, "1")


def dim(text: str) -> str:
    return _paint(text, "2")


def red(text: str) -> str:
    # 91 — bright red («светло-красный»): обычный 31 малоконтрастен
    # на тёмных терминальных темах
    return _paint(text, "91")


def green(text: str) -> str:
    return _paint(text, "32")


def yellow(text: str) -> str:
    return _paint(text, "33")


def chartreuse(text: str) -> str:
    # 256-цветной зелёно-жёлтый (салатовый): переходная ступень #1 шкал
    # green → chartreuse → yellow → orange → red
    return _paint(text, "38;5;154")


def orange(text: str) -> str:
    # 256-цветной оранжевый: переходная ступень #3 шкал (жёлтый → красный)
    return _paint(text, "38;5;208")


def magenta(text: str) -> str:
    # 95 — bright magenta: обычный 35 малоконтрастен на тёмных темах
    return _paint(text, "95")


def cyan(text: str) -> str:
    return _paint(text, "36")


def chess_word(text: str) -> str:
    """RECURSION — слово-шахматка: буквы через одну инверсные. Только SGR 7,
    чёрно-белое, работает в любом терминале (без 256/TrueColor)."""
    if not _enabled:
        return text
    return "".join(_paint(ch, "7") if i % 2 == 0 else ch for i, ch in enumerate(text))
