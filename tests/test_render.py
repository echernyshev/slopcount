import csv
import io
import json

import pytest
from test_e2e import HUMAN, SLOP, run_cli

pytestmark = pytest.mark.usefixtures("scc_ready")


def test_json_output_new_model():
    _code, out = run_cli([str(SLOP), "--json", "--lang", "en"])
    data = json.loads(out)
    assert set(data) == {"scan", "volume", "slop", "comprehension", "costs", "evidence_count"}
    assert set(data["scan"]) == {"tool", "files", "skipped", "history_commits"}
    assert set(data["volume"]) == {
        "sloc",
        "comment_lines",
        "complexity",
        "cognitive",
        "md_files",
        "md_lines",
        "md_words",
        "md_sloc_ratio",
        "comment_sloc_ratio",
        "languages",
        "grades",
    }
    assert set(data["slop"]) == {"total", "ratio", "infected_md_lines", "categories", "top_files"}
    assert set(data["slop"]["categories"]) == {"prose", "docs", "style", "agency", "history"}
    assert set(data["costs"]) == {"cocomo", "locomo"}
    assert data["volume"]["sloc"] == 8
    assert data["volume"]["comment_lines"] == 12
    assert data["volume"]["md_files"] == 2 and data["volume"]["md_lines"] == 12
    assert data["volume"]["md_sloc_ratio"] == 1.5
    assert data["volume"]["grades"]["doc"] == "RECURSION"
    assert data["slop"]["total"] == 16
    assert data["slop"]["infected_md_lines"] == 9
    assert data["slop"]["top_files"][0]["file"] == "README.md"
    assert data["scan"]["tool"].startswith("scc ")
    assert data["costs"]["locomo"]["preset"] == "medium"
    for model in ("locomo", "cocomo"):
        bd = data["costs"][model]["breakdown"]
        assert set(bd) == {"docs", "source_code", "data"}
        assert set(bd["source_code"]) == {"total", "code", "comments"}
        assert bd["source_code"]["comments"] is None  # scc их не считает
    comp = data["comprehension"]
    assert set(comp) == {
        "reading_hours",
        "reading_components",
        "person_months",
        "person_years",
        "schedule_months",
        "therapists",
        "cost_per_person",
        "cost_breakdown",
        "team_costs",
        "comprehension_tokens",
        "context_windows_200k",
        "context_windows_1m",
        "gpu_hours",
        "coffee_cups",
        "coffee_cost",
        "therapy_sessions",
        "therapy_cost",
    }
    assert set(comp["reading_components"]) == {"docs", "code", "comments", "cognitive"}
    assert [t["people"] for t in comp["team_costs"]] == [1, 2, 3, 5, 8, 13, 21]
    assert abs(comp["team_costs"][2]["cost"] - 3 * comp["cost_per_person"]) < 0.02
    cbd = comp["cost_breakdown"]
    assert set(cbd) == {"docs", "source_code", "data"}
    assert set(cbd["source_code"]) == {"total", "code", "comments"}
    assert cbd["data"] is None  # data-файлы не читаем
    assert abs(cbd["docs"] + cbd["source_code"]["total"] - comp["cost_per_person"]) < 0.01
    json.dumps(data)  # сериализуемо


def test_json_human_fixture_zero_md():
    _code, out = run_cli([str(HUMAN), "--json", "--lang", "en"])
    data = json.loads(out)
    assert data["volume"]["md_files"] == 0
    assert data["volume"]["md_sloc_ratio"] == 0.0
    assert data["volume"]["grades"]["doc"] == "HUMAN"


def test_json_inf_becomes_null(tmp_path):
    from slopcount.evidence import Report, SlopStats, VolumeStats, safe_ratio
    from slopcount.render.json_out import render_json

    (tmp_path / "ONLY.md").write_text("just text\n")
    rep = Report(
        root=str(tmp_path),
        volume=VolumeStats(md_lines=5, md_sloc_ratio=safe_ratio(5, 0)),
        slop=SlopStats(total=3, ratio=safe_ratio(3, 0)),
    )
    d = json.loads(render_json(rep))
    assert d["volume"]["md_sloc_ratio"] is None
    assert d["slop"]["ratio"] is None
    assert d["comprehension"] is None


def test_json_inf_comprehension_nulls(tmp_path):
    """inf-маршрут comprehension целиком: person-months/cost/team → null,
    source_code-подкорзины остаются нулями (0·inf ≠ nan)."""
    from slopcount.app import Options
    from slopcount.evidence import Report, SlopStats, VolumeStats, safe_ratio
    from slopcount.metrics.slocomo import compute
    from slopcount.render.json_out import render_json

    (tmp_path / "ONLY.md").write_text("just text\n")
    slocomo = compute(
        md_words=2,
        comment_lines=0,
        sloc=0,
        cognitive_total=0,
        slop_ratio=float("inf"),
        locomo=None,
        opts=Options(),
    )
    rep = Report(
        root=str(tmp_path),
        volume=VolumeStats(md_lines=2, md_sloc_ratio=safe_ratio(2, 0)),
        slop=SlopStats(total=1, ratio=safe_ratio(1, 0)),
        slocomo=slocomo,
    )
    comp = json.loads(render_json(rep))["comprehension"]
    assert comp["person_months"] is None and comp["cost_per_person"] is None
    assert comp["cost_breakdown"]["docs"] is None
    assert comp["cost_breakdown"]["source_code"] == {"total": 0.0, "code": 0.0, "comments": 0.0}
    assert all(t["person_months"] is None and t["cost"] is None for t in comp["team_costs"])


def test_csv_rows_with_source():
    _code, out = run_cli([str(SLOP), "--csv", "--lang", "en"])
    rows = list(csv.reader(io.StringIO(out)))
    assert rows[0] == ["file", "line", "category", "weight", "description", "source"]
    assert any(r[3] == "5" for r in rows[1:])
    # есть реальный сниппет, а не поголовная деградация в «—» (line=0/git:*)
    assert any(r[5] not in ("", "—") and not r[5].startswith("—") for r in rows[1:])
    # и минимум один конкретный: фразовая улика в README.md:3 / src/greeter.py:4
    assert any(r[5].startswith("Great question") for r in rows[1:])


def test_top_slop_files_block_layout():
    """Топ файлов — по строке на файл: ранг, имя, полоса █░ от худшего, строки."""
    _code, out = run_cli([str(SLOP), "--lang", "en"])
    lines = out.splitlines()
    idx = lines.index("Top slop files:")
    block = lines[idx + 1 : idx + 4]  # в фикстуре ровно 3 файла в топе
    assert [ln.lstrip()[:2] for ln in block] == ["1.", "2.", "3."]
    assert block[0].lstrip().startswith("1. README.md ")
    assert block[1].lstrip().startswith("2. src/defensive.py ")
    assert block[2].lstrip().startswith("3. src/greeter.py ")
    for ln in block:
        assert "█" in ln  # полоса есть у каждого
    assert block[0].endswith("13 lines")
    assert block[1].endswith("2 lines")
    assert block[2].endswith("1 line")
    # полоса худшего файла — полная, у остальных короче (относительная)
    assert block[0].count("█") > block[1].count("█") > block[2].count("█")
    # за блоком сразу идёт строка про агентов, а не хвост старого « · »-формата
    assert " · " not in lines[idx + 1]


def test_color_off_report_has_no_ansi():
    _code, out = run_cli([str(SLOP), "--lang", "en"])
    assert "\x1b" not in out


def test_color_on_paints_and_preserves_text():
    """Включённый цвет: ANSI-коды есть во всех секциях, и после зачистки
    кодов текст побайтово совпадает с бесцветным рендером — подсветка не
    имеет права менять содержимое и выравнивание."""
    import re

    from slopcount.app import Options, run
    from slopcount.render import ansi
    from slopcount.render.text import render_comprehension, render_slop, render_volume

    report = run(Options(paths=[str(SLOP)]))
    sections = (render_volume, render_comprehension, render_slop)
    plain = [fn(report) for fn in sections]

    ansi.set_enabled(True)
    try:
        painted = [fn(report) for fn in sections]
    finally:
        ansi.set_enabled(False)

    strip = lambda s: re.sub(r"\x1b\[[0-9;]*m", "", s)  # noqa: E731
    for plain_s, painted_s in zip(plain, painted, strict=True):
        assert "\x1b[" in painted_s
        assert strip(painted_s) == plain_s
    # якорные цвета: bold-заголовки, cyan-файлы, dim-ранг, yellow-полоса/деньги,
    # RECURSION — слово-шахматка инверсией (у фикстуры md_sloc_ratio=1.5)
    assert "\x1b[1m" in painted[0]  # PROJECT VOLUME
    assert "\x1b[7m" in painted[0]  # RECURSION (chess_word)
    assert "▚▞" in painted[0]  # шахматная полоса вместо прогресс-бара
    assert "\x1b[33m" in painted[1]  # деньги Cost Ladder
    assert "\x1b[36m" in painted[2]  # имена файлов топа
    assert "\x1b[2m" in painted[2]  # ранги 1./2./3.
    assert "\x1b[33m" in painted[2]  # полоса/счётчик строк топа


def test_grade_colors_explicit_palette():
    """Палитра вердиктов — явная таблица-градиент: green → chartreuse →
    yellow → orange → red; RECURSION — ч/б слово-шахматка."""
    from slopcount.render import ansi
    from slopcount.render.text import _grade_color
    from slopcount.scales import SCALES, grade

    expected = {
        "HUMAN": ansi.green,
        "NEURO_CLOUD": ansi.chartreuse,
        "ESTABLISHED_SLOP": ansi.yellow,
        "AGENT_SELF_SERVICE": ansi.orange,
        "AGENT_OCCUPATION": ansi.red,
        "RECURSION": ansi.chess_word,
        "ASCETIC": ansi.green,
        "DOCUMENTED": ansi.chartreuse,
        "CHATTY": ansi.yellow,
        "LECTURE_NOTES": ansi.orange,
        "COMMENT_DRIVEN": ansi.red,
        "CLEAN": ansi.green,
        "TRACE": ansi.chartreuse,
        "NOTICEABLE": ansi.yellow,
        "HEAVY": ansi.orange,
        "INFESTED": ansi.red,
    }
    pairs = [(metric, g) for metric in SCALES for _bound, g in SCALES[metric]]
    pairs.append(("doc", grade("doc", 1.5)))  # RECURSION — спец-вердикт
    for metric, g in pairs:
        assert _grade_color(g) is expected[g.code], f"{metric}/{g.code}"


def test_text_renderer_golden():
    """Golden-file тест из спеки §8. Первый запуск/обновление эталона:
    GOLDEN=1 python -m pytest tests/test_render.py -v"""
    import os
    from pathlib import Path

    _code, out = run_cli([str(SLOP), "--lang", "en"])
    golden = Path(__file__).parent / "golden" / "slop_project_en.txt"
    if golden.exists():
        assert out == golden.read_text()
    elif os.environ.get("GOLDEN"):
        golden.parent.mkdir(exist_ok=True)
        golden.write_text(out)
    else:
        raise AssertionError("golden file missing; regenerate with GOLDEN=1")
