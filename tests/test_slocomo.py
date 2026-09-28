from slopcount.app import Options
from slopcount.metrics.slocomo import TEAM_SIZES, compute
from slopcount.scc import Locomo


def _locomo():
    return Locomo(
        cost=57.13,
        input_tokens=100_000.0,
        output_tokens=28_000.0,
        generation_seconds=3600.0,
        review_hours=1.0,
        cycles=1.9,
        preset="medium",
    )


def test_reading_components():
    r = compute(
        md_words=23_800,
        comment_lines=60,
        sloc=200,
        cognitive_total=100,
        slop_ratio=0.0,
        locomo=None,
        opts=Options(),
    )
    assert abs(r.reading_components["docs"] - 23_800 / 238 / 60 * 2.3) < 1e-9
    assert abs(r.reading_components["comments"] - 60 * 6 / 238 / 60) < 1e-9
    assert abs(r.reading_components["code"] - 200 / 200) < 1e-9
    assert abs(r.reading_components["cognitive"] - 100 * 0.5 / 60) < 1e-9
    assert abs(r.reading_hours - sum(r.reading_components.values())) < 1e-9


def test_person_months_formula():
    r = compute(
        md_words=0,
        comment_lines=0,
        sloc=15_200,
        cognitive_total=0,
        slop_ratio=0.5,
        locomo=None,
        opts=Options(),
    )
    # чтение = 15200/200 = 76 ч; pm = 76/152 × 1.5 = 0.75
    assert abs(r.person_months - 0.75) < 1e-9
    assert abs(r.schedule_months - 2.5 * 0.75**0.38) < 1e-9
    assert abs(r.cost - 0.75 * 4690.50 * 2.4) < 1e-6


def test_tokens_from_locomo():
    r = compute(
        md_words=0,
        comment_lines=0,
        sloc=100,
        cognitive_total=0,
        slop_ratio=0.0,
        locomo=_locomo(),
        opts=Options(),
    )
    assert abs(r.comprehension_tokens - 128_000.0) < 1e-6
    assert abs(r.context_windows_200k - 128_000 / 200_000) < 1e-9
    assert abs(r.context_windows_1m - 128_000 / 1_000_000) < 1e-9
    assert abs(r.gpu_hours - 128_000 / 100 / 3600) < 1e-9


def test_tokens_none_without_locomo():
    r = compute(
        md_words=0,
        comment_lines=0,
        sloc=100,
        cognitive_total=0,
        slop_ratio=0.0,
        locomo=None,
        opts=Options(),
    )
    assert r.comprehension_tokens is None
    assert r.context_windows_200k is None and r.gpu_hours is None


def test_team_costs():
    r = compute(
        md_words=0,
        comment_lines=0,
        sloc=15_200,
        cognitive_total=0,
        slop_ratio=0.5,
        locomo=None,
        opts=Options(),
    )
    assert [n for n, _pm, _c in r.team_costs] == list(TEAM_SIZES)
    one_pm = r.team_costs[0][1]
    assert abs(one_pm - r.person_months) < 1e-9
    for n, pm, cost in r.team_costs:
        assert abs(pm - n * r.person_months) < 1e-9
        assert abs(cost - n * r.cost) < 1e-6


def test_cost_breakdown_additive():
    r = compute(
        md_words=23_800,
        comment_lines=60,
        sloc=200,
        cognitive_total=100,
        slop_ratio=0.0,
        locomo=None,
        opts=Options(),
    )
    assert set(r.cost_breakdown) == {"docs", "source_code", "data"}
    sc = r.cost_breakdown["source_code"]
    assert set(sc) == {"total", "code", "comments"}
    assert abs(r.cost_breakdown["docs"] + sc["total"] - r.cost) < 1e-6
    assert r.cost_breakdown["data"] is None  # data-файлы не читаем


def test_inf_slop_ratio_edges():
    r = compute(
        md_words=100,
        comment_lines=0,
        sloc=0,
        cognitive_total=0,
        slop_ratio=float("inf"),
        locomo=None,
        opts=Options(),
    )
    assert r.person_months == float("inf")
    assert r.cost == float("inf")
    assert r.therapists == float("inf")
    assert r.therapy_sessions is None  # ∞
    assert r.coffee_cups == 1  # от конечного reading


def test_zero_reading():
    r = compute(
        md_words=0,
        comment_lines=0,
        sloc=0,
        cognitive_total=0,
        slop_ratio=0.0,
        locomo=None,
        opts=Options(),
    )
    assert r.person_months == 0.0 and r.schedule_months == 0.0 and r.therapists == 0.0
    assert r.therapy_sessions == 1  # max(1, ceil(0))
    assert r.coffee_cups == 0


def test_no_therapy_flag():
    r = compute(
        md_words=0,
        comment_lines=0,
        sloc=100,
        cognitive_total=0,
        slop_ratio=0.0,
        locomo=None,
        opts=Options(no_therapy=True),
    )
    assert r.therapy_sessions == 0 and r.therapy_cost == 0.0


def test_coffee_and_therapy():
    r = compute(
        md_words=23_800,
        comment_lines=0,
        sloc=0,
        cognitive_total=100,
        slop_ratio=0.0,
        locomo=None,
        opts=Options(coffee_price=4.0),
    )
    # чтение = 3.83 ч + 0.83 ч = 4.67 ч → 2 чашки
    assert r.coffee_cups == 2
    assert abs(r.coffee_cost - 8.0) < 1e-9


def test_therapists_formula():
    r = compute(
        md_words=0,
        comment_lines=0,
        sloc=15_200,
        cognitive_total=0,
        slop_ratio=0.5,
        locomo=None,
        opts=Options(),
    )
    assert abs(r.therapists - r.person_months / r.schedule_months) < 1e-9


def test_inf_cost_breakdown_no_nan():
    r = compute(
        md_words=100,
        comment_lines=0,
        sloc=0,
        cognitive_total=0,
        slop_ratio=float("inf"),
        locomo=None,
        opts=Options(),
    )
    # нулевые компоненты остаются нулями (0·inf ≠ nan), total корзины — их сумма
    assert r.cost_breakdown == {
        "docs": float("inf"),
        "source_code": {"total": 0.0, "code": 0.0, "comments": 0.0},
        "data": None,
    }
    assert r.cost_breakdown["docs"] + r.cost_breakdown["source_code"]["total"] == float("inf")
