from __future__ import annotations

import logging
import math

from slopcount.evidence import Category, Evidence
from slopcount.scanner import ScannedFile

MODEL_NAME = "gpt2"
MAX_PPL = 35.0     # ниже — «слишком гладкая» проза
MAX_BURST = 0.3    # коэффициент вариации перплексии ниже — монотонный слоп
_OVERLONG_MSG = "Token indices sequence length"


def _silence_overlong_tokenizer_warning() -> None:
    """Токенизатор transformers предупреждает о последовательностях длиннее
    model_max_length; такие чанки мы осознанно пропускаем сами — предупреждение
    только пугает. Хирургический фильтр на конкретный логгер: глушится только
    это сообщение, остальные предупреждения и ошибки проходят."""
    try:
        from transformers.utils import logging as hf_logging
    except ImportError:
        return
    lg = hf_logging.get_logger("transformers.tokenization_utils_base")
    if any(getattr(f, "_slopcount_overlong", False) for f in lg.filters):
        return

    def _drop_overlong(record: logging.LogRecord) -> bool:
        return _OVERLONG_MSG not in record.getMessage()

    _drop_overlong._slopcount_overlong = True  # type: ignore[attr-defined]
    lg.addFilter(_drop_overlong)


def available() -> bool:
    """True, если установлены extras (transformers + torch)."""
    try:
        import transformers  # noqa: F401
        import torch  # noqa: F401
    except ImportError:
        return False
    return True


class PerplexityDetector:
    """GPTZero-стиль: низкая средняя перплексия + низкий burstiness = слоп.
    Требует extras: pipx install 'slopcount[perplexity]' и
    python -m slopcount.download_model (gpt2, ~500 МБ)."""

    category = Category.PROSE

    def __init__(self, model_name: str = MODEL_NAME):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        self._torch = torch
        self._tok = AutoTokenizer.from_pretrained(model_name)
        self._model = AutoModelForCausalLM.from_pretrained(model_name)
        self._model.eval()
        self._max_ppl = MAX_PPL
        self._max_burst = MAX_BURST
        _silence_overlong_tokenizer_warning()

    def _ppls(self, sentences: list[str]) -> list[float]:
        """Натуральные лог-перплексии (mean NLL) по предложениям.
        Предложения из одного токена пропускаем: предсказывать нечего.
        Чанки длиннее контекстного окна модели (gpt2: 1024 токена) тоже
        пропускаем — иначе IndexError в position embeddings."""
        max_len = int(getattr(self._tok, "model_max_length", 1024) or 1024)
        nlls: list[float] = []
        for s in sentences:
            ids = self._tok(s, return_tensors="pt").input_ids
            if ids.shape[1] < 2:
                continue
            if ids.shape[1] > max_len:
                continue
            with self._torch.no_grad():
                logits = self._model(ids).logits
            logp = self._torch.log_softmax(logits[:, :-1], dim=-1)
            tgt = ids[:, 1:]
            nll = -self._torch.gather(logp, 2, tgt.unsqueeze(-1)).mean().item()
            nlls.append(nll)
        return nlls

    def detect(self, sf: ScannedFile, text: str) -> list[Evidence]:
        sentences = [s.strip() for s in text.replace("\n", " ").split(". ")
                     if len(s.strip()) > 30]
        if len(sentences) < 3:   # burstiness не имеет смысла на 1-2 точках
            return []
        nlls = self._ppls(sentences)
        if not nlls:
            return []
        ppls = [math.exp(n) for n in nlls]
        mean = sum(ppls) / len(ppls)
        var = sum((p - mean) ** 2 for p in ppls) / len(ppls)
        burst = math.sqrt(var) / mean if mean else 0.0
        if mean >= self._max_ppl or burst >= self._max_burst:
            return []
        return [Evidence(sf.path, 0, self.category, 2,
                         f"suspiciously smooth prose "
                         f"(ppl≈{mean:.0f}, burst≈{burst:.2f})")]
