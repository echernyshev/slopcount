import math

from slopcount.detectors.perplexity import PerplexityDetector, available
from slopcount.evidence import Category
from slopcount.scanner import ScannedFile


class FakeTok:
    def __call__(self, text, return_tensors=None):
        return {"input_ids": [[1, 2, 3]]}


class FakeModel:
    def __call__(self, input_ids=None):
        class L:  # равномерные логиты → перплексия = vocab_size
            logits = [[[0.0] * 50 for _ in range(3)]]
        return L()


# Три предложения длиннее 30 символов: иначе guard «< 3 предложений» вернёт []
SMOOTH = ("One perfectly smooth generated sentence right here. "
          "Another perfectly smooth generated sentence follows it. "
          "A third perfectly smooth generated sentence closes the text.")


def _mock_detector(ppl: float) -> PerplexityDetector:
    det = PerplexityDetector.__new__(PerplexityDetector)  # без __init__/transformers
    det._tok, det._model, det._max_ppl, det._max_burst = FakeTok(), FakeModel(), 35.0, 0.3
    # _ppls возвращает натуральные лог-перплексии (mean NLL) по предложениям
    det._ppls = lambda s: [math.log(ppl)] * len(s)
    return det


def test_available_false_without_extras():
    assert available() in (True, False)  # не падает на голом окружении


def test_smooth_text_flagged_with_fake_model():
    det = _mock_detector(20.0)           # ppl 20 < 35, burst 0 < 0.3 → слоп
    sf = ScannedFile("doc.md", None, "markdown", 0)
    evs = det.detect(sf, SMOOTH)
    assert evs and all(e.category is Category.PROSE for e in evs)
    assert all(e.description.startswith("suspiciously smooth prose") for e in evs)


def test_rough_text_not_flagged_with_fake_model():
    det = _mock_detector(50.0)           # ppl 50 ≥ 35 → «человеческий» текст
    sf = ScannedFile("doc.md", None, "markdown", 0)
    assert det.detect(sf, SMOOTH) == []


def test_too_few_long_sentences_skipped():
    det = _mock_detector(20.0)
    sf = ScannedFile("doc.md", None, "markdown", 0)
    assert det.detect(sf, "Only one long enough sentence here to evaluate now.") == []


def test_overlong_chunks_skipped():
    """Чанки длиннее контекстного окна модели (gpt2: 1024 токена) не должны
    доходить до модели — иначе IndexError в position embeddings (wpe)."""
    from types import SimpleNamespace

    class SmallWindowTok:
        model_max_length = 10

        def __call__(self, text, return_tensors=None):
            # ~1 токен на 2 символа: предложения фикстуры (~50 симв.) → ~25 токенов > 10
            return SimpleNamespace(input_ids=SimpleNamespace(
                shape=(1, max(2, len(text) // 2))))

    class SentinelModel:
        def __call__(self, input_ids=None):
            raise AssertionError("model called with an overlong input")

    import contextlib

    det = PerplexityDetector.__new__(PerplexityDetector)
    det._tok, det._model = SmallWindowTok(), SentinelModel()
    det._max_ppl, det._max_burst = 35.0, 0.3
    det._torch = SimpleNamespace(no_grad=contextlib.nullcontext)
    evs = det.detect(ScannedFile("doc.md", None, "markdown", 0), SMOOTH)
    assert evs == []  # все чанки длиннее окна → ничего не измеряем, но и не падаем


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
            "Token indices sequence length is longer than the maximum (1344 > 1024)")
        test_logger.warning("Some other legit warning")

    messages = [r.message for r in caplog.records]
    assert not any("Token indices sequence length" in m for m in messages)
    assert any("Some other legit warning" in m for m in messages)
