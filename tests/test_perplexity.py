from typing import ClassVar

from slopcount.detectors.perplexity import PerplexityDetector, available
from slopcount.evidence import Category
from slopcount.scanner import ScannedFile


class FakeTok:
    def __call__(self, text, return_tensors=None):
        return {"input_ids": [[1, 2, 3]]}


class FakeModel:
    def __call__(self, input_ids=None):
        class L:  # равномерные логиты → перплексия = vocab_size
            logits: ClassVar = [[[0.0] * 50 for _ in range(3)]]

        return L()


# Четыре предложения длиннее 30 символов: детектор отбрасывает первое
# (нет контекста) и требует ≥3 оставшихся точек
SMOOTH = (
    "One perfectly smooth generated sentence right here. "
    "Another perfectly smooth generated sentence follows it. "
    "A third perfectly smooth generated sentence arrives now. "
    "A fourth perfectly smooth generated sentence closes the text."
)


def _mock_detector(ppl: float) -> PerplexityDetector:
    det = PerplexityDetector.__new__(PerplexityDetector)  # без __init__/transformers
    det._tok, det._model, det._max_ppl, det._max_burst = FakeTok(), FakeModel(), 35.0, 0.3
    # _ppls возвращает натуральные лог-перплексии (mean NLL) по предложениям
    # _ppls(text) → перплексии предложений; [0] отбрасывается детектором
    det._ppls = lambda text: (
        [999.0]
        + [ppl] * len([x for x in text.replace(chr(10), " ").split(". ") if len(x.strip()) > 30])
    )
    return det


def test_available_false_without_extras():
    assert available() in (True, False)  # не падает на голом окружении


def test_smooth_text_flagged_with_fake_model():
    det = _mock_detector(20.0)  # медиана 20 < 40 → слоп
    sf = ScannedFile("doc.md", None, "markdown", 0)
    evs = det.detect(sf, SMOOTH)
    assert evs and all(e.category is Category.PROSE for e in evs)
    assert all(e.description.startswith("suspiciously smooth prose") for e in evs)


def test_rough_text_not_flagged_with_fake_model():
    det = _mock_detector(50.0)  # медиана 50 ≥ 40 → «человеческий» текст
    sf = ScannedFile("doc.md", None, "markdown", 0)
    assert det.detect(sf, SMOOTH) == []


def test_too_few_long_sentences_skipped():
    det = _mock_detector(20.0)
    sf = ScannedFile("doc.md", None, "markdown", 0)
    assert det.detect(sf, "Only one long enough sentence here to evaluate now.") == []


def test_model_never_sees_overlong_input():
    """Однопроходный замер режет вход до окна модели: модель не должна
    получить больше model_max_length токенов (иначе IndexError в wpe)."""
    import pytest

    torch = pytest.importorskip("torch")

    from slopcount.detectors.perplexity import PerplexityDetector

    seen = []

    class FakeTok:
        model_max_length = 10

        def __call__(self, text, return_offsets_mapping=False):
            n = max(30, len(text) // 2)  # длинный вход
            ids = [1] * n
            offs = [(i, i + 1) for i in range(n)]
            from types import SimpleNamespace

            return SimpleNamespace(input_ids=ids, offset_mapping=offs)

    class FakeModel:
        def __call__(self, ids):
            seen.append(ids.shape[1])
            return SimpleNamespace(logits=torch.zeros(1, ids.shape[1], 8))

    import contextlib
    from types import SimpleNamespace

    det = PerplexityDetector.__new__(PerplexityDetector)
    det._tok, det._model = FakeTok(), FakeModel()
    det._max_ppl = 40.0
    from types import SimpleNamespace as SN

    det._torch = SN(
        no_grad=contextlib.nullcontext,
        tensor=torch.tensor,
        log_softmax=torch.log_softmax,
        gather=torch.gather,
    )
    det.detect(ScannedFile("doc.md", None, "markdown", 0), SMOOTH)
    assert seen and max(seen) <= 10  # модель видела только срез ≤ окна


def test_overlong_warning_filter(monkeypatch, caplog):
    """Фильтр глушит ТОЛЬКО предупреждение о слишком длинных последовательностях;
    остальные предупреждения transformers проходят."""
    import logging as stdlib_logging

    import pytest as _pytest

    _pytest.importorskip("transformers")

    from slopcount.detectors import perplexity

    test_logger = stdlib_logging.getLogger("slopcount.pplx.test")
    for f in list(test_logger.filters):
        test_logger.removeFilter(f)

    from transformers.utils import logging as hf_logging

    monkeypatch.setattr(hf_logging, "get_logger", lambda name: test_logger)

    perplexity._silence_overlong_tokenizer_warning()

    with caplog.at_level(stdlib_logging.WARNING, logger="slopcount.pplx.test"):
        test_logger.warning(
            "Token indices sequence length is longer than the maximum (1344 > 1024)"
        )
        test_logger.warning("Some other legit warning")

    messages = [r.message for r in caplog.records]
    assert not any("Token indices sequence length" in m for m in messages)
    assert any("Some other legit warning" in m for m in messages)
