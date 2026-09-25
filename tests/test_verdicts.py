from slopcount.i18n import setup
from slopcount.verdicts import progress_bar, verdict_for


def test_scale_boundaries():
    assert verdict_for(0).code == "HUMAN"
    assert verdict_for(10).code == "NEURO_CLOUD"
    assert verdict_for(24.9).code == "NEURO_CLOUD"
    assert verdict_for(25).code == "ESTABLISHED_SLOP"
    assert verdict_for(50).code == "AGENT_SELF_SERVICE"
    assert verdict_for(75).code == "AGENT_OCCUPATION"
    assert verdict_for(100.1).code == "RECURSION"
    assert verdict_for(float("inf")).code == "RECURSION"


def test_texts_are_english_msgids():
    assert "slop" in verdict_for(30).text.lower()


def test_progress_bar():
    setup("en")  # в прогресс-баре локализованный процент — фиксируем en
    assert progress_bar(50.0, width=4) == "[██░░] 50.0%"


def test_progress_bar_edges():
    setup("en")
    assert progress_bar(float("inf")) == "[░░░░░░░░░░░░░░░░░░░░] inf%"
    assert progress_bar(150.0, width=4) == "[████] 150.0%"
    assert verdict_for(100).code == "AGENT_OCCUPATION"
