"""ANSI-слой отчёта: глобальный флаг + хелперы-тождества при выключенном цвете."""

import io

import pytest

from slopcount.render import ansi


class _Tty(io.StringIO):
    """Стрим, притворяющийся терминалом (isatty=True)."""

    def isatty(self) -> bool:  # pragma: no cover - тривиальная заглушка
        return True


# ── хелперы ──────────────────────────────────────────────────────────────


def test_helpers_identity_when_disabled():
    ansi.set_enabled(False)
    for fn in (
        ansi.bold,
        ansi.dim,
        ansi.red,
        ansi.green,
        ansi.chartreuse,
        ansi.yellow,
        ansi.orange,
        ansi.magenta,
        ansi.cyan,
        ansi.chess_word,
    ):
        assert fn("plain") == "plain"


def test_helpers_wrap_when_enabled():
    ansi.set_enabled(True)
    assert ansi.bold("x") == "\x1b[1mx\x1b[0m"
    assert ansi.dim("x") == "\x1b[2mx\x1b[0m"
    # 91/95 — bright red/magenta: тёмные 31/35 плохо читаются на тёмных темах
    assert ansi.red("x") == "\x1b[91mx\x1b[0m"
    assert ansi.green("x") == "\x1b[32mx\x1b[0m"
    assert ansi.yellow("x") == "\x1b[33mx\x1b[0m"
    assert ansi.magenta("x") == "\x1b[95mx\x1b[0m"
    assert ansi.cyan("x") == "\x1b[36mx\x1b[0m"
    # переходные ступени шкал — 256-цветная палитра
    assert ansi.chartreuse("x") == "\x1b[38;5;154mx\x1b[0m"  # зелёно-жёлтый
    assert ansi.orange("x") == "\x1b[38;5;208mx\x1b[0m"  # жёлто-красный


def test_chess_word():
    """RECURSION — слово-шахматка: буквы через одну инверсные (SGR 7)."""
    ansi.set_enabled(False)
    assert ansi.chess_word("RECURSION") == "RECURSION"
    ansi.set_enabled(True)
    assert (
        ansi.chess_word("AB") == "\x1b[7mA\x1b[0mB"  # нечётные буквы инверсны, чётные — как есть
    )
    ansi.set_enabled(False)


def test_set_enabled_roundtrip():
    ansi.set_enabled(True)
    assert ansi.is_enabled()
    ansi.set_enabled(False)
    assert not ansi.is_enabled()


# ── autodetect ───────────────────────────────────────────────────────────


def test_autodetect_tty(monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.delenv("FORCE_COLOR", raising=False)
    assert ansi.autodetect(_Tty()) is True
    assert ansi.autodetect(io.StringIO()) is False


def test_autodetect_no_color_wins_over_tty(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    assert ansi.autodetect(_Tty()) is False


def test_autodetect_no_color_wins_over_force_color(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    monkeypatch.setenv("FORCE_COLOR", "1")
    assert ansi.autodetect(io.StringIO()) is False


def test_autodetect_force_color_without_tty(monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("FORCE_COLOR", "3")
    assert ansi.autodetect(io.StringIO()) is True


def test_autodetect_empty_no_color_is_ignored(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "")
    monkeypatch.delenv("FORCE_COLOR", raising=False)
    assert ansi.autodetect(_Tty()) is True


def test_autodetect_stream_without_isatty(monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.delenv("FORCE_COLOR", raising=False)
    assert ansi.autodetect(object()) is False


def test_autodetect_isatty_raising(monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.delenv("FORCE_COLOR", raising=False)

    class _Broken:
        def isatty(self):
            raise ValueError("closed")

    assert ansi.autodetect(_Broken()) is False


@pytest.fixture(autouse=True)
def _color_off():
    """Каждый тест стартует с выключенным цветом (глобальное состояние)."""
    ansi.set_enabled(False)
    yield
    ansi.set_enabled(False)
