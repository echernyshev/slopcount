from __future__ import annotations

import math
import re

_NESTING = re.compile(
    r"\b(if|for|while|case|when|switch)\b|&&|\|\||\b(and|or)\b(?=\s)", re.I)
_FLAT = re.compile(r"\b(else|elif|catch|except)\b", re.I)


def _indent_unit(lines: list[str]) -> int:
    for line in lines:
        stripped = line.lstrip(" ")
        if stripped and len(line) != len(stripped):
            return len(line) - len(stripped)
    return 4


def approx_cognitive_complexity(text: str, language: str) -> int:
    """Аппроксимация Cognitive Complexity (Campbell 2018): каждое управляющее
    выражение стоит 1 + nesting (за уровень вложенности; вложенный оператор
    стоит 1+nesting), else/catch/except — плоско +1. Вложенность оценивается
    по отступам (только пробелы; табы не распознаются — приближение), язык
    не влияет на расчёт. Помечается в выводе как 'approximate' (точный
    режим — treesitter, Task 23). Ключевые слова в комментариях и строках
    тоже считаются — цена приближения без лексера."""
    lines = text.split("\n")
    unit = _indent_unit(lines)
    score = 0
    for line in lines:
        if not line.strip():
            continue
        nesting = (len(line) - len(line.lstrip(" "))) // unit
        score += len(_NESTING.findall(line)) * (1 + nesting)
        score += len(_FLAT.findall(line))
    return score


_IDENT = re.compile(r"[A-Za-z_]\w*")
_NUM = re.compile(r"\b\d+(?:\.\d+)?\b")
_MULTI_OPS = ["==", "!=", "<=", ">=", "->", "::", "+=", "-=", "*=", "/=",
              "**", "//", "&&", "||"]
_OPS_KEYWORDS = {"if", "for", "while", "return", "def", "class", "import",
                 "from", "function", "func", "fn", "switch", "case", "try"}


def halstead_seconds(text: str) -> float:
    """Halstead: V=N*log2(n), D=(n1/2)*(N2/n2), время = V*D/18 (секунды)."""
    rest = text
    n1: set[str] = set()
    N1 = 0
    for op in _MULTI_OPS:
        N1 += rest.count(op)
        if op in rest:
            n1.add(op)
        rest = rest.replace(op, " ")
    for tok in _IDENT.findall(rest):
        if tok.lower() in _OPS_KEYWORDS:
            n1.add(tok)
            N1 += 1
    ops_single = set("+-*/%=<>!&|^~")
    for ch in rest:
        if ch in ops_single:
            n1.add(ch)
            N1 += 1
    operands = _NUM.findall(rest) + [
        t for t in _IDENT.findall(rest) if t.lower() not in _OPS_KEYWORDS]
    n2 = set(operands)
    N2 = len(operands)
    n = len(n1) + len(n2)
    N = N1 + N2
    if n < 2 or N2 == 0 or len(n2) == 0 or len(n1) == 0:
        return 0.0
    V = N * math.log2(n)
    D = (len(n1) / 2) * (N2 / len(n2))
    return V * D / 18
