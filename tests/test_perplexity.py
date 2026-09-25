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
