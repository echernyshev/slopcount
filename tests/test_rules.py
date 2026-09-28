import pytest

from slopcount.rules import load_rules


def test_builtin_rules_loaded_and_compiled():
    rules = load_rules()
    assert len(rules) >= 15
    hit = [r for r in rules if r.pattern.search("Great question! Let's see.")]
    assert hit and hit[0].weight == 5


def test_case_insensitive_and_user_extra(tmp_path):
    extra = tmp_path / "mine.toml"
    extra.write_text('[[rule]]\npattern = "ну давай уже"\nweight = 4\ndescription = "x"\n')
    rules = load_rules([extra])
    assert any(r.weight == 4 for r in rules if r.pattern.search("Ну давай уже"))


def test_word_boundary_on_exclamation_rules():
    rules = load_rules()
    assert not any(r.pattern.search("Бесконечно! движемся") and r.weight == 5 for r in rules)
    assert not any(r.pattern.search("Uncertainly! we proceed") and r.weight == 5 for r in rules)
    assert any(r.pattern.search("Конечно! Давайте") for r in rules)
    assert any(r.pattern.search("Let's delve deep into it") for r in rules)


def test_missing_file_warns_and_defaults(tmp_path, capsys):
    rules = load_rules([tmp_path / "nope.toml"])
    assert len(rules) == 18
    assert "nope.toml" in capsys.readouterr().err


def test_weight_default_and_bad_regex(tmp_path):
    extra = tmp_path / "d.toml"
    extra.write_text('[[rule]]\npattern = "abc"\n')
    assert any(r.weight == 1 and r.description == "" for r in load_rules([extra]))
    extra.write_text('[[rule]]\npattern = "([unclosed"\n')
    with pytest.raises(RuntimeError):
        load_rules([extra])


def test_bad_toml_raises_runtime_error(tmp_path):
    extra = tmp_path / "broken.toml"
    extra.write_text('[[rule]\npattern = "abc"\n')  # unclosed table
    with pytest.raises(RuntimeError):
        load_rules([extra])


def test_languages_catalog_counts():
    from slopcount.rules import load_languages

    catalog = load_languages([])
    kinds = {}
    for _name, (kind, _ext) in catalog.items():
        kinds[kind] = kinds.get(kind, 0) + 1
    assert kinds == {"code": 251, "markdown": 2, "prose": 1, "data": 112}
    assert len(catalog) == 366


def test_extractor_languages_are_code():
    from slopcount.rules import load_languages

    catalog = load_languages([])
    assert catalog["Python"] == ("code", "python")
    assert catalog["C Header"] == ("code", "c")
    assert catalog["BASH"] == ("code", "sh")
    # каждый язык с extractor-id обязан быть code
    assert all(kind == "code" for kind, ext in catalog.values() if ext)


def test_user_override_merges_and_warns(tmp_path, capsys):
    from slopcount.rules import load_languages

    rules = tmp_path / "r.toml"
    rules.write_text('[languages]\n"Zig" = "data"\n"Org" = "prose"\n"Nope" = "code"\n')
    catalog = load_languages([rules])
    assert catalog["Zig"] == ("data", None)
    assert catalog["Org"] == ("prose", None)
    assert "Nope" in capsys.readouterr().err  # неизвестное имя — предупреждение


def test_markdown_and_prose_kinds():
    from slopcount.rules import load_languages

    catalog = load_languages([])
    assert catalog["Markdown"] == ("markdown", None)
    assert catalog["ReStructuredText"] == ("markdown", None)
    assert catalog["Plain Text"] == ("prose", None)
    assert catalog["JSON"] == ("data", None)


def test_user_override_bad_kind_raises(tmp_path):
    from slopcount.rules import load_languages

    rules = tmp_path / "r.toml"
    rules.write_text('[languages]\nZig = "bogus"\n')
    with pytest.raises(RuntimeError, match="kind"):
        load_languages([rules])


def test_user_override_erases_extractor_id(tmp_path):
    from slopcount.rules import load_languages

    rules = tmp_path / "r.toml"
    rules.write_text('[languages]\nPython = "data"\n')
    catalog = load_languages([rules])
    assert catalog["Python"] == ("data", None)
