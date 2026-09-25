from pathlib import Path

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
    extra.write_text('[[rule]\npattern = "abc"\n')      # unclosed table
    with pytest.raises(RuntimeError):
        load_rules([extra])
