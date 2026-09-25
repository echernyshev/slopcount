from slopcount.i18n import _, fmt_float, fmt_int, ngettext, setup


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
    assert fmt_int(1234567) == "1 234 567"
    assert fmt_float(14.76) == "14,76"


def test_ngettext_english_forms():
    setup("en")
    assert ngettext("%d cup", "%d cups", 1) % 1 == "1 cup"
    assert ngettext("%d cup", "%d cups", 5) % 5 == "5 cups"
