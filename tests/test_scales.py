from slopcount.i18n import setup
from slopcount.scales import SCALES, grade, progress_bar


def test_doc_scale_boundaries():
    assert grade("doc", 0).code == "HUMAN"
    assert grade("doc", 0.049).code == "HUMAN"
    assert grade("doc", 0.05).code == "NEURO_CLOUD"
    assert grade("doc", 0.349).code == "NEURO_CLOUD"
    assert grade("doc", 0.35).code == "ESTABLISHED_SLOP"
    assert grade("doc", 0.50).code == "AGENT_SELF_SERVICE"
    assert grade("doc", 0.75).code == "AGENT_OCCUPATION"
    assert grade("doc", 0.999).code == "AGENT_OCCUPATION"
    assert grade("doc", 1.0).code == "RECURSION"
    assert grade("doc", float("inf")).code == "RECURSION"


def test_comment_and_slop_scale_structure():
    """5 категорий, коды уникальны, границы возрастают (значения границ
    может уточнить калибровка — тест проверяет структуру, не константы)."""
    for metric in ("comment", "slop"):
        entries = SCALES[metric]
        codes = [g.code for _b, g in entries]
        assert len(codes) == len(set(codes)) == 5
        bounds = [b for b, _g in entries]
        assert bounds == sorted(bounds)
        # последняя граница inf → grade всегда находит категорию
        assert bounds[-1] == float("inf")
        assert grade(metric, 1e9).code == codes[-1]


def test_grade_texts_are_english_msgids():
    for entries in SCALES.values():
        for _b, g in entries:
            assert g.text and g.code.isupper()


def test_calibrated_boundaries_pinned():
    """Итог калибровки 2026-09-27 (спека §7): разрыв flask 0.0025 → naumen 0.0071."""
    assert grade("slop", 0.0049).code == "CLEAN"
    assert grade("slop", 0.005).code == "TRACE"
    assert grade("comment", 0.299).code == "DOCUMENTED"
    assert grade("comment", 0.30).code == "CHATTY"


def test_progress_bar():
    setup("en")  # в прогресс-баре локализованный процент — фиксируем en
    assert progress_bar(50.0, width=4) == "[██░░] 50.0%"
    assert progress_bar(float("inf")) == "[░░░░░░░░░░░░░░░░░░░░] inf%"
    assert progress_bar(150.0, width=4) == "[████] 150.0%"
