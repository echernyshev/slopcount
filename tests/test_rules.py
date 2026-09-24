from pathlib import Path

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
