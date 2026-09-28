from __future__ import annotations

import re
from dataclasses import dataclass
from importlib import resources
from pathlib import Path

from slopcount.i18n import _


@dataclass(frozen=True)
class PhraseRule:
    pattern: re.Pattern
    weight: int
    description: str


def load_rules(extra_paths: list[Path] | None = None) -> list[PhraseRule]:
    """Load built-in phrase catalogs (en, ru) plus any user-supplied TOML files.

    Each catalog is a sequence of ``[[rule]]`` tables with ``pattern``
    (a regex, compiled case-insensitively), ``weight`` (int, default 1)
    and ``description`` (str, default ""). Missing files warn on stderr
    and are skipped; a malformed catalog (bad TOML, bad regex, wrong field
    types) raises :class:`RuntimeError` — cli maps it to exit 2.
    """
    import os
    import sys
    import tomllib

    rules: list[PhraseRule] = []
    names = ["phrases_en.toml", "phrases_ru.toml"]
    base = resources.files("slopcount").joinpath("rules")
    paths = [Path(os.fspath(base / n)) for n in names] + list(extra_paths or [])
    for p in paths:
        if not p.is_file():
            print(_("slopcount: rules file not found, skipped: {p}").format(p=p), file=sys.stderr)
            continue
        try:
            data = tomllib.loads(p.read_text(encoding="utf-8"))
            for r in data.get("rule", []):
                desc = r.get("description", "")
                rules.append(
                    PhraseRule(
                        pattern=re.compile(r["pattern"], re.IGNORECASE),
                        weight=int(r.get("weight", 1)),
                        # пустая строка — без _(): gettext("") вернул бы PO-заголовок
                        description=_(desc) if desc else "",
                    )
                )
        except (tomllib.TOMLDecodeError, re.error, KeyError, TypeError, ValueError) as exc:
            raise RuntimeError(f"slopcount: bad rules file {p}: {exc}") from exc
    return rules


VALID_KINDS = ("code", "markdown", "prose", "data")


def load_languages(extra_paths: list[Path] | None = None) -> dict[str, tuple[str, str | None]]:
    """builtin rules/languages.toml + точечные [languages] из пользовательских --rules.

    Возвращает {scc display name: (kind, extractor_id | None)}. Неизвестные
    имена в пользовательских файлах — предупреждение; битый TOML или структура
    секций ([languages]/[extractors] не таблица) — RuntimeError."""
    import os
    import sys
    import tomllib

    base = resources.files("slopcount").joinpath("rules")
    path = Path(os.fspath(base / "languages.toml"))
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        languages: dict[str, tuple[str, str | None]] = {}
        for name, kind in data.get("languages", {}).items():
            languages[name] = (kind, None)
        for name, ext in data.get("extractors", {}).items():
            # не «kind, _ = …»: локальное _ затенило бы gettext-_ для merge() ниже
            # KeyError (extractor без [languages]-записи) — сознательно сырой
            kind = languages[name][0]
            languages[name] = (kind, ext)
    except (tomllib.TOMLDecodeError, AttributeError, TypeError) as exc:
        raise RuntimeError(f"slopcount: bad built-in languages.toml: {exc}") from exc

    def merge(section: dict, source: Path) -> None:
        for name, kind in section.items():
            if kind not in VALID_KINDS:
                raise RuntimeError(
                    f"slopcount: bad rules file {source}: kind must be one of {VALID_KINDS}"
                )
            if name not in languages:
                print(
                    _(
                        "slopcount: unrecognized language %s in --rules [languages]; "
                        "known names are in the built-in languages.toml"
                    )
                    % name,
                    file=sys.stderr,
                )
            languages[name] = (kind, None)  # оверрайд стирает extractor-id

    languages: dict[str, tuple[str, str | None]]
    for p in extra_paths or []:
        if not p.is_file():
            continue  # load_rules уже предупредил о каждом отсутствующем файле
        try:
            user = tomllib.loads(p.read_text(encoding="utf-8"))
            merge(user.get("languages", {}), p)
        except (tomllib.TOMLDecodeError, AttributeError, TypeError) as exc:
            raise RuntimeError(f"slopcount: bad rules file {p}: {exc}") from exc
    return languages
