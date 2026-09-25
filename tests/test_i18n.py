import os
import tempfile

import pytest

from slopcount.i18n import _, detect_lang, fmt_float, fmt_int, ngettext, setup


def test_default_is_english_identity(monkeypatch):
    for var in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        monkeypatch.delenv(var, raising=False)
    setup(None)
    assert _("Totals") == "Totals"          # каталога ru не выбрано — msgid
    assert fmt_int(12411) == "12,411"
    assert fmt_float(14.76) == "14.76"


def test_lang_argument_forces_language():
    setup("en")                              # en — всегда msgid
    assert fmt_int(1234567) == "1,234,567"
    setup("ru")
    assert fmt_int(1234567) == "1\u202f234\u202f567"
    assert fmt_float(14.76) == "14,76"


def test_ngettext_english_forms():
    setup("en")
    assert ngettext("%d cup", "%d cups", 1) % 1 == "1 cup"
    assert ngettext("%d cup", "%d cups", 5) % 5 == "5 cups"


def test_russian_translation_active():
    setup("ru")
    assert _("Slop Ratio (SLOP/SLOC)") == "Доля слопа (SLOP/SLOC)"
    assert _("VERDICT:") == "ВЕРДИКТ:"


def test_russian_plurals():
    setup("ru")
    assert ngettext("%d cup", "%d cups", 1) % 1 == "1 чашка"
    assert ngettext("%d cup", "%d cups", 3) % 3 == "3 чашки"
    assert ngettext("%d cup", "%d cups", 5) % 5 == "5 чашек"
    assert ngettext("%d cup", "%d cups", 21) % 21 == "21 чашка"


def test_po_mo_consistency():
    import shutil
    import subprocess
    from importlib import resources
    from pathlib import Path
    if shutil.which("msgfmt") is None:
        pytest.skip("msgfmt not available")
    base = Path(os.fspath(resources.files("slopcount") / "locale"))
    po = base / "ru" / "LC_MESSAGES" / "slopcount.po"
    mo = base / "ru" / "LC_MESSAGES" / "slopcount.mo"
    out = Path(tempfile.mkdtemp()) / "check.mo"
    subprocess.run(["msgfmt", "--check", "-o", str(out), str(po)], check=True)
    assert out.read_bytes() == mo.read_bytes(), ".po changed without recompiling .mo"


@pytest.mark.parametrize(("env", "expected"), [
    ({"LANGUAGE": "ru:en", "LANG": "en_US.UTF-8"}, "ru"),
    ({"LC_ALL": "ru_RU.UTF-8", "LANG": "en"}, "ru"),
    ({"LANG": "de_DE.UTF-8@euro"}, "de"),
    ({"LANG": "C"}, "en"),
    ({"LANG": "C.UTF-8"}, "en"),
    ({"LANG": "POSIX"}, "en"),
    ({}, "en"),
])
def test_detect_lang_matrix(monkeypatch, env, expected):
    for var in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        monkeypatch.delenv(var, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    assert detect_lang() == expected
