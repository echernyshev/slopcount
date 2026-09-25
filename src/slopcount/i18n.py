from __future__ import annotations

import gettext
import os
from importlib import resources

DOMAIN = "slopcount"

_translations = gettext.NullTranslations()
_lang = "en"

_THOUSANDS = {"en": ",", "ru": " "}   # неразрывный узкий пробел
_DECIMAL = {"en": ".", "ru": ","}


def detect_lang() -> str:
    """--lang > LANGUAGE > LC_ALL > LC_MESSAGES > LANG > en (первый токен)."""
    for var in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        val = os.environ.get(var, "")
        token = val.split(":", 1)[0].strip()
        if token and token not in ("C", "POSIX"):
            return token.split(".", 1)[0].split("_", 1)[0]
    return "en"


def setup(lang: str | None = None) -> None:
    """Вызывать ДО любой работы с _(). lang — значение --lang или None."""
    global _translations, _lang
    _lang = lang if lang else detect_lang()
    localedir = os.fspath(resources.files(DOMAIN).joinpath("locale"))
    try:
        _translations = gettext.translation(
            DOMAIN, localedir=localedir, languages=[_lang])
    except (FileNotFoundError, OSError):
        _translations = gettext.NullTranslations()


def _(msgid: str) -> str:
    return _translations.gettext(msgid)


def ngettext(singular: str, plural: str, n: int) -> str:
    return _translations.ngettext(singular, plural, n)


def current_lang() -> str:
    return _lang


def fmt_int(n: int) -> str:
    sep = _THOUSANDS.get(_lang, ",")
    grouped = f"{abs(n):,}".replace(",", "\x00")
    return ("-" if n < 0 else "") + grouped.replace("\x00", sep)


def fmt_float(x: float, ndigits: int = 2) -> str:
    s = f"{x:,.{ndigits}f}"
    if _lang == "ru":
        s = s.replace(",", "\x00").replace(".", ",").replace("\x00", " ")
    return s
