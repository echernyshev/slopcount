from __future__ import annotations

import math
import re
from functools import lru_cache

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


@lru_cache(maxsize=None)     # доступность extras не меняется за один запуск
def exact_available() -> bool:
    """Есть ли [treesitter] extras: точный режим возможен только для python."""
    try:
        import tree_sitter  # noqa: F401
        import tree_sitter_python  # noqa: F401
        return True
    except ImportError:
        return False


# Узлы AST tree-sitter-python, стоящие 1 + nesting (Campbell: вложенное
# управляющее выражение дорожает на 1 за уровень). Имена сверены с грамматикой
# tree-sitter-python: except_clause (не catch_clause), case_clause (не
# switch_expression); try_statement/match_statement сами по себе не считаются.
_CONTROL_NODES = {"if_statement", "for_statement", "while_statement",
                  "case_clause", "conditional_expression", "boolean_operator"}

# else/elif/except — плоско +1, без надбавки за вложенность.
_FLAT_NODES = {"else_clause", "elif_clause", "except_clause"}


def cognitive_complexity_tspython(text: str) -> int:
    """Точный Cognitive Complexity для python через tree-sitter (Campbell
    2018: управляющее выражение стоит 1 + nesting, else/elif/except — +1).
    Семантика вложенности повторяет approx-режим (Task 16): boolean_operator
    тоже увеличивает nesting — сознательное упрощение против «+1 за
    последовательность операторов» у Кэмпбелла. elif: в грамматике
    tree-sitter-python 0.25 elif_clause НЕ содержит вложенного if_statement
    (проверено на реальном AST); на случай, если грамматика это изменит,
    прямой if_statement-потомок elif_clause пропускается — иначе elif
    считался бы дважды (плоско +1 и как вложенный 1+nesting)."""
    import tree_sitter
    import tree_sitter_python as tsp

    # API tree-sitter >=0.22: Language(ptr) + Parser(language)
    lang = tree_sitter.Language(tsp.language())
    parser = tree_sitter.Parser(lang)
    tree = parser.parse(text.encode())

    score = 0

    def walk(node, nesting: int) -> None:
        nonlocal score
        for child in node.children:
            if child.type in _CONTROL_NODES:
                score += 1 + nesting
                walk(child, nesting + 1)
            elif child.type in _FLAT_NODES:
                score += 1
                if child.type == "elif_clause":
                    # Грамматика может заворачивать elif в if_statement —
                    # тогда он уже посчитан как сам elif (+1), не считаем дважды.
                    subs = [s for s in child.children if s.type != "if_statement"]
                else:
                    subs = child.children
                for sub in subs:
                    walk(sub, nesting)
            else:
                walk(child, nesting)

    walk(tree.root_node, 0)
    return score


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
