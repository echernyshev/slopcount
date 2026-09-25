from slopcount.app import Options
from slopcount.metrics.slocomo import compute


def test_cocomo_parody_numbers():
    res = compute(
        slop=10_000, prose_words=23_800, cognitive_points=100, halstead_secs=0.0, opts=Options()
    )
    # KSLOP=10 → pm = 2.4*10**1.05 = 26.86...
    assert abs(res.person_months - 2.4 * 10**1.05) < 1e-6
    assert abs(res.schedule_months - 2.5 * res.person_months**0.38) < 1e-6
    assert abs(res.therapists - res.person_months / res.schedule_months) < 1e-6
    assert abs(res.cost - res.person_months * 4690.50 * 2.4) < 1e-6
    # чтение: 23800 слов / 238 wpm / 60 * 2.3 = 3.83 часа; когниция: 100*0.5/60
    assert abs(res.reading_hours - (23_800 / 238 / 60 * 2.3 + 100 * 0.5 / 60)) < 1e-6
    assert res.coffee_cups == 2  # ceil(4.667/4) — Coffee = человеко-часы / 4


def test_joke_conversions():
    res = compute(
        slop=1000, prose_words=20_000, cognitive_points=0, halstead_secs=0.0, opts=Options()
    )
    tokens = 20_000 * 1.3
    assert abs(res.context_windows_200k - tokens / 200_000) < 1e-9
    assert abs(res.gpu_hours - tokens / 100 / 3600) < 1e-9
    # KSLOP=1 → pm = 2.4; Therapy = ceil(pm*2) = ceil(4.8) = 5
    assert res.therapy_sessions == 5


def test_no_therapy_flag():
    res = compute(
        slop=1000,
        prose_words=100,
        cognitive_points=0,
        halstead_secs=0.0,
        opts=Options(no_therapy=True),
    )
    assert res.therapy_sessions == 0 and res.therapy_cost == 0.0


def test_one_million_window_and_halstead_term():
    res = compute(
        slop=1000, prose_words=20_000, cognitive_points=0, halstead_secs=0.0, opts=Options()
    )
    assert abs(res.context_windows_1m - 20_000 * 1.3 / 1_000_000) < 1e-9
    res2 = compute(slop=1, prose_words=0, cognitive_points=0, halstead_secs=3600.0, opts=Options())
    assert abs(res2.reading_hours - 1.0) < 1e-9
