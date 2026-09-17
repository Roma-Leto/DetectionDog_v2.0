"""
Логика перевода текста en→ru через NLLB.

Простой интерфейс: принимает строку, возвращает строку.
"""

from __future__ import annotations

import logging
import time

from app.config import Settings
from app.services.model_loader import get_model

logger = logging.getLogger(__name__)


def translate(
    text: str,
    settings: Settings,
    source_lang: str | None = None,
    target_lang: str | None = None,
) -> str:
    """
    Переводит текст.

    :param text: исходный текст (en)
    :param settings: настройки
    :param source_lang: код исходного языка (по умолчанию eng_Latn)
    :param target_lang: код целевого языка (по умолчанию rus_Cyrl)
    :return: переведённый текст
    """
    if not text or not text.strip():
        return ""

    # Обрезаем слишком длинный текст
    text = text.strip()
    if len(text) > settings.max_text_length:
        text = text[:settings.max_text_length]

    src = source_lang or settings.source_lang
    tgt = target_lang or settings.target_lang

    loaded = get_model(settings)
    tokenizer = loaded.tokenizer
    model = loaded.model

    t0 = time.time()

    # Устанавливаем язык в токенизаторе (NLLB-специфично)
    tokenizer.src_lang = src

    # Токенизация
    inputs = tokenizer(text, return_tensors="pt", padding=True, truncation=True)
    inputs = {k: v.to(model.device) for k, v in inputs.items()}

    # ID целевого языка
    target_lang_id = tokenizer.convert_tokens_to_ids(tgt)

    # Генерация
    with __import__("torch").no_grad():
        generated = model.generate(
            **inputs,
            forced_bos_token_id=target_lang_id,
            max_length=512,
            num_beams=1,           # жадный поиск — быстро, качество приемлемое
            early_stopping=True,
        )

    # Декодирование
    translated = tokenizer.batch_decode(generated, skip_special_tokens=True)[0]

    elapsed = time.time() - t0
    logger.info(
        "Translated %d chars → %d chars in %.2fs",
        len(text),
        len(translated),
        elapsed,
    )

    return translated.strip()