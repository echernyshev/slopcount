import json
from pathlib import Path

import pytest

from slopcount.metrics.costs import CocomoSplit, attribute_locomo, split_cocomo, split_slocomo
from slopcount.rules import load_languages
from slopcount.scc import Cocomo, Locomo, parse_json2


def _cocomo():
    # фактические цифры scc 4.1.0 для naumen-smp-mcp (проверено до доллара,
    # спека §5.4): 2.4·(111.841)^1.05 = 339.7 PM × 4690.5 × 2.4
    return Cocomo(cost=3_825_363.5675040204, schedule_months=22.9, people=14.84)


def _locomo():
    return Locomo(
        cost=57.13,
        input_tokens=8_440_553.1,
        output_tokens=2_120_575.3,
        generation_seconds=42_411.5,
        review_hours=18.64,
        cycles=1.9,
        preset="medium",
    )


def test_split_cocomo_independent_buckets():
    cs = split_cocomo(
        _cocomo(),
        docs_lines=71_706,
        code_lines=38_639,
        data_lines=1_496,
        personcost=4690.50,
        overhead=2.4,
    )
    assert isinstance(cs, CocomoSplit)
    assert abs(cs.buckets["docs"].person_months - 2.4 * 71.706**1.05) < 0.05
    sc = cs.buckets["source_code"]
    assert set(cs.buckets) == {"docs", "source_code", "data"}
    assert abs(sc["code"].person_months - 2.4 * 38.639**1.05) < 0.05
    assert sc["total"] == sc["code"]  # вход scc — только Code-строки
    assert sc["comments"] is None  # комментарии scc не считает
    rate = 4690.50 * 2.4
    assert abs(cs.buckets["docs"].cost - cs.buckets["docs"].person_months * rate) < 1.0
    assert cs.buckets["docs"].lines == 71_706
    # НЕаддитивность: сумма корзин < total (суперлинейность 2.4·K^1.05)
    assert (
        cs.buckets["docs"].cost + sc["total"].cost + cs.buckets["data"].cost
        < cs.total_person_months * rate
    )


def test_split_cocomo_drift_guard_warns(capsys):
    skewed = Cocomo(cost=10_000_000.0, schedule_months=22.9, people=14.84)
    split_cocomo(
        skewed,
        docs_lines=71_706,
        code_lines=38_639,
        data_lines=1_496,
        personcost=4690.50,
        overhead=2.4,
    )
    assert "drift" in capsys.readouterr().err


def test_split_cocomo_no_drift_warning_on_match(capsys):
    split_cocomo(
        _cocomo(),
        docs_lines=71_706,
        code_lines=38_639,
        data_lines=1_496,
        personcost=4690.50,
        overhead=2.4,
    )
    assert capsys.readouterr().err == ""


def test_attribute_locomo_sums_exactly():
    lb = attribute_locomo(_locomo(), docs_lines=71_706, code_lines=38_639, data_lines=1_496)
    total_hours = 42_411.5 / 3600 + 18.64
    sc = lb["source_code"]
    assert set(lb) == {"docs", "source_code", "data"}
    assert sc["total"] == sc["code"] and sc["comments"] is None
    flat = [lb["docs"], sc["total"], lb["data"]]
    assert abs(sum(b.hours for b in flat) - total_hours) < 1e-9
    assert abs(sum(b.cost for b in flat) - 57.13) < 1e-9
    share_docs = 71_706 / 111_841
    assert abs(lb["docs"].hours - total_hours * share_docs) < 1e-6
    assert abs(lb["docs"].cost - 57.13 * share_docs) < 1e-6


def test_split_slocomo_additive():
    comps = {"docs": 135.0, "code": 192.0, "comments": 5.0, "cognitive": 101.0}
    b = split_slocomo(comps, slop_ratio=0.5, personcost=4690.50, overhead=2.4)
    factor = 1.5 * 4690.50 * 2.4 / 152
    assert abs(b["docs"] - 135.0 * factor) < 1e-6
    sc = b["source_code"]
    assert abs(sc["code"] - (192.0 + 101.0) * factor) < 1e-6
    assert abs(sc["comments"] - 5.0 * factor) < 1e-6
    assert abs(sc["total"] - sc["code"] - sc["comments"]) < 1e-9
    assert b["data"] is None  # data-файлы не читаем
    total_hours = 135.0 + 192.0 + 5.0 + 101.0
    assert abs(b["docs"] + sc["total"] - total_hours * factor) < 1e-6


def test_split_slocomo_inf_ratio_keeps_additivity():
    comps = {"docs": 100.0, "code": 0.0, "comments": 0.0, "cognitive": 0.0}
    b = split_slocomo(comps, slop_ratio=float("inf"), personcost=4690.50, overhead=2.4)
    assert b["docs"] == float("inf")
    sc = b["source_code"]
    assert sc["comments"] == 0.0 and sc["code"] == 0.0  # не nan
    assert sc["total"] == 0.0
    assert b["docs"] + sc["total"] == float("inf")


def test_all_zero_tree_no_division_errors():
    lb = attribute_locomo(_locomo(), docs_lines=0, code_lines=0, data_lines=0)
    flat = [lb["docs"], lb["source_code"]["total"], lb["data"]]
    assert all(b.hours == 0.0 and b.cost == 0.0 for b in flat)
    cs = split_cocomo(
        _cocomo(),
        docs_lines=0,
        code_lines=0,
        data_lines=0,
        personcost=4690.50,
        overhead=2.4,
    )
    assert cs.buckets["docs"].lines == 0 and cs.buckets["docs"].person_months == 0.0
    assert cs.buckets["source_code"]["code"].lines == 0
    assert split_slocomo(
        {"docs": 0.0, "code": 0.0, "comments": 0.0, "cognitive": 0.0},
        slop_ratio=0.0,
        personcost=4690.50,
        overhead=2.4,
    ) == {
        "docs": 0.0,
        "source_code": {"total": 0.0, "code": 0.0, "comments": 0.0},
        "data": None,
    }


def _load_scc_fixture():
    data = json.loads((Path(__file__).parent / "fixtures" / "scc_slop_project.json2").read_text())
    # root не участвует: пути в фикстуре относительные (ветка absolute в parse_json2)
    return parse_json2(data, root=Path("."))


def test_drift_guard_hard_assert_on_fixture(capsys):
    """Спека §6.1: репликация COCOMO сходится с estimatedCost scc на
    записанной фикстуре json2 (жёсткий ассерт против дрейфа модели scc)."""
    rep = _load_scc_fixture()
    langmap = load_languages(None)
    lines = {"code": 0, "markdown": 0, "prose": 0, "data": 0}
    for f in rep.files:
        lines[langmap.get(f.language_name, ("data", None))[0]] += f.code
    cs = split_cocomo(
        rep.cocomo,
        docs_lines=lines["markdown"] + lines["prose"],
        code_lines=lines["code"],
        data_lines=lines["data"],
        personcost=4690.50,
        overhead=2.4,
    )
    implied = rep.cocomo.cost / (4690.50 * 2.4)
    assert cs.total_person_months == pytest.approx(implied, rel=0.01)
    assert capsys.readouterr().err == ""  # на честной фикстуре guard молчит
