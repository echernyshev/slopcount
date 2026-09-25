import csv
import io
import json

import pytest
from test_e2e import SLOP, run_cli


def test_json_output_stable_keys():
    _code, out = run_cli([str(SLOP), "--json", "--lang", "en"])
    data = json.loads(out)
    assert set(data) == {
        "sloc",
        "slop",
        "slop_ratio",
        "skipped_files",
        "infected_md_lines",
        "history_commits",
        "categories",
        "evidence_count",
        "slocomo",
        "verdict",
    }
    assert set(data["categories"]) == {"prose", "docs", "style", "agency", "history"}
    assert data["verdict"]["code"] in {
        "HUMAN",
        "NEURO_CLOUD",
        "ESTABLISHED_SLOP",
        "AGENT_SELF_SERVICE",
        "AGENT_OCCUPATION",
        "RECURSION",
    }
    json.dumps(data)  # сериализуемо
    # sanity: 1M-окно — это 200K/5 (каждое поле округлено до 4 знаков независимо)
    assert data["slocomo"]["context_windows_1m"] == pytest.approx(
        data["slocomo"]["context_windows_200k"] / 5, abs=1e-4
    )


def test_csv_rows():
    _code, out = run_cli([str(SLOP), "--csv", "--lang", "en"])
    rows = list(csv.reader(io.StringIO(out)))
    assert rows[0] == ["file", "line", "category", "weight", "description"]
    assert any(r[3] == "5" for r in rows[1:])


def test_text_renderer_golden():
    """Golden-file тест из спеки §9. Первый запуск/обновление эталона:
    GOLDEN=1 python -m pytest tests/test_render.py -v"""
    import os
    from pathlib import Path

    from slopcount.metrics.cognitive import exact_available

    if exact_available():
        # Эталон закрепляет вывод режима приближения: с [treesitter] extras
        # суффикс «(approximate)» исчезает — сверять не с чем.
        pytest.skip("exact mode active (treesitter extras installed)")
    _code, out = run_cli([str(SLOP), "--lang", "en"])
    golden = Path(__file__).parent / "golden" / "slop_project_en.txt"
    if golden.exists():
        assert out == golden.read_text()
    elif os.environ.get("GOLDEN"):
        golden.parent.mkdir(exist_ok=True)
        golden.write_text(out)
    else:
        raise AssertionError("golden file missing; regenerate with GOLDEN=1")
