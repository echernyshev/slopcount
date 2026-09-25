import csv
import io
import json

from test_e2e import SLOP, run_cli


def test_json_output_stable_keys():
    code, out = run_cli([str(SLOP), "--json", "--lang", "en"])
    data = json.loads(out)
    assert {"sloc", "slop", "slop_ratio", "categories", "slocomo", "verdict"} <= set(data)
    assert set(data["categories"]) == {"prose", "docs", "style", "agency", "history"}
    assert data["verdict"]["code"] in {"HUMAN", "NEURO_CLOUD", "ESTABLISHED_SLOP",
                                       "AGENT_SELF_SERVICE", "AGENT_OCCUPATION", "RECURSION"}
    json.dumps(data)  # сериализуемо


def test_csv_rows():
    code, out = run_cli([str(SLOP), "--csv", "--lang", "en"])
    rows = list(csv.reader(io.StringIO(out)))
    assert rows[0] == ["file", "line", "category", "weight", "description"]
    assert any(r[3] == "5" for r in rows[1:])


def test_text_renderer_golden():
    """Golden-file тест из спеки §9. Первый запуск/обновление эталона:
    GOLDEN=1 python -m pytest tests/test_render.py -v"""
    from pathlib import Path
    import os
    code, out = run_cli([str(SLOP), "--lang", "en"])
    golden = Path(__file__).parent / "golden" / "slop_project_en.txt"
    if golden.exists():
        assert out == golden.read_text()
    elif os.environ.get("GOLDEN"):
        golden.parent.mkdir(exist_ok=True)
        golden.write_text(out)
    else:
        raise AssertionError("golden file missing; regenerate with GOLDEN=1")
