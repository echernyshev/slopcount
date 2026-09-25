from __future__ import annotations

import logging
import math

from slopcount.evidence import Category, Evidence
from slopcount.scanner import ScannedFile

MODEL_NAME = "gpt2"
# Калибровка на GPTZero-стиле замера (предложения в контексте файла, медиана
# по предложениям; первое предложение отброшено — нет левого контекста):
# LLM-проза → медиана 15-30; человеческая → 64-151. Burstiness на gpt2
# классы НЕ разделяет (0.6-0.9 у обоих) — убран из правила. gpt2 — слабый
# судья (слоп-слова для него редки), поэтому сигнал точный, но редкий.
# Более сильная/мультиязычная модель: SLOPCOUNT_PPLX_MODEL=Qwen/Qwen2.5-0.5B.
MAX_MEDIAN_PPL = 40.0   # медиана ниже — «слишком гладкая» проза
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

    def __init__(self, model_name: str | None = None):
        import os

        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        model_name = model_name or os.environ.get(
            "SLOPCOUNT_PPLX_MODEL", MODEL_NAME)
        self._torch = torch
        self._tok = AutoTokenizer.from_pretrained(model_name)
        self._model = AutoModelForCausalLM.from_pretrained(model_name)
        self._model.eval()
        self._max_ppl = MAX_MEDIAN_PPL
        _silence_overlong_tokenizer_warning()

    def _ppls(self, text: str) -> list[float]:
        """Перплексии предложений В КОНТЕКСТЕ файла (GPTZero-стиль):
        один проход по всему тексту, пер-токенные NLL, группировка по
        предложениям через offset mapping. Изоляция предложений не работает:
        «холодный старт» каждого (NLL≈10 за первый токен) раздувает перплексию
        в ~10 раз и инвертирует сигнал.

        Файлы длиннее окна модели измеряются по префиксу (первые max_len
        токенов) — предложения за окном отбрасываются автоматически.
        Требует fast-токенизатор (return_offsets_mapping); gpt2 и современные
        модели ему удовлетворяют."""
        flat = text.replace("\n", " ")
        max_len = int(getattr(self._tok, "model_max_length", 1024) or 1024)
        enc = self._tok(flat, return_offsets_mapping=True)
        ids_list = list(enc.input_ids)[:max_len]
        offs = list(enc.offset_mapping)[:max_len]
        if len(ids_list) < 3:
            return []
        ids = self._torch.tensor([ids_list])
        with self._torch.no_grad():
            logits = self._model(ids).logits
        logp = self._torch.log_softmax(logits[:, :-1], dim=-1)
        nll = (-self._torch.gather(logp, 2, ids[:, 1:].unsqueeze(-1))
               .squeeze(-1)[0]).tolist()

        ppls: list[float] = []
        for s in (x.strip() for x in flat.split(". ") if len(x.strip()) > 30):
            a = flat.find(s)
            b = a + len(s)
            toks = [i for i, (s0, e0) in enumerate(offs)
                    if s0 >= a and e0 <= b and i + 1 < len(ids_list)]
            if len(toks) < 2:
                continue
            vals = [nll[i] for i in toks[1:]]   # первый токен — без контекста
            if vals:
                ppls.append(math.exp(sum(vals) / len(vals)))
        return ppls

    def detect(self, sf: ScannedFile, text: str) -> list[Evidence]:
        ppls = self._ppls(text)
        # первое предложение — без левого контекста, всегда выброс: в статистику
        # не идёт (оно остаётся контекстом для остальных)
        ppls = ppls[1:]
        if len(ppls) < 3:
            return []
        ppls_sorted = sorted(ppls)
        median = (ppls_sorted[len(ppls) // 2]
                  if len(ppls) % 2
                  else (ppls_sorted[len(ppls) // 2 - 1]
                        + ppls_sorted[len(ppls) // 2]) / 2)
        if median >= self._max_ppl:
            return []
        return [Evidence(sf.path, 0, self.category, 2,
                         f"suspiciously smooth prose "
                         f"(median ppl≈{median:.0f} over {len(ppls)} sentences)")]
