"""
Логика перевода текста en→ru через NLLB.

Простые операции: принимает строку, возвращает строку.
После перевода применяется постобработка — словарь замен
частых ошибок NLLB.
"""

from __future__ import annotations

import logging
import re
import time

from app.config import Settings
from app.services.model_loader import get_model

logger = logging.getLogger(__name__)


# ============================================================
# Словарь постобработки — замены частых ошибок NLLB
# ============================================================
# Ключ — что модель написала (в нижнем регистре).
# Значение — правильное слово (в нижнем регистре).
# Замена регистронезависимая, регистр сохраняется по образцу.
#
# Формируется по мере наблюдений: увидели ошибку → добавили.
# ============================================================

POSTPROCESS_REPLACEMENTS: dict[str, str] = {
    # Зажигалка — NLLB пишет «запалка»
    "запалка": "зажигалка",
    "запалки": "зажигалки",
    "запалку": "зажигалку",
    "запалке": "зажигалке",
    "запалкой": "зажигалкой",
    "запалок": "зажигалок",
    "запалкам": "зажигалкам",
    "запалками": "зажигалками",
    "запалках": "зажигалках",
    "запачками": "зажигалками",

    # Щелочные — NLLB пишет «алкальные»
    "алкальная": "щелочная",
    "алкальной": "щелочной",
    "алкальную": "щелочную",
    "алкальные": "щелочные",
    "алкальных": "щелочных",
    "алкальным": "щелочным",
    "алкальными": "щелочными",
    "алкальный": "щелочной",
    "алкального": "щелочного",
    "алкальному": "щелочному",
}


def translate(
    text: str,
    settings: Settings,
    source_lang: str | None = None,
    target_lang: str | None = None,
) -> str:
    """
    Переводит текст en→ru.

    :param text: исходный текст (en)
    :param settings: настройки
    :param source_lang: код исходного языка (по умолчанию eng_Latn)
    :param target_lang: код целевого языка (по умолчанию rus_Cyrl)
    :return: переведённый текст с постобработкой
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
    import torch
    with torch.no_grad():
        generated = model.generate(
            **inputs,
            forced_bos_token_id=target_lang_id,
            max_length=512,
            num_beams=5,  # beam search с 5 лучами
            length_penalty=1.0,
            no_repeat_ngram_size=3,  # не повторять 3-граммы
            repetition_penalty=1.2,  # штраф за повторы
            early_stopping=True,
        )

    # Декодирование
    translated = tokenizer.batch_decode(generated, skip_special_tokens=True)[0]
    translated = translated.strip()

    # --- Постобработка ---
    translated = _postprocess(translated)

    elapsed = time.time() - t0
    logger.info(
        "Translated %d chars → %d chars in %.2fs",
        len(text),
        len(translated),
        elapsed,
    )

    return translated


def _postprocess(text: str) -> str:
    """
    Применяет словарь замен к переведённому тексту.

    Замены выполняются по границам слов (не затрагивают части слов),
    регистронезависимо с сохранением регистра.
    """
    if not text:
        return text

    def _replace_word(match: re.Match) -> str:
        word = match.group(0)
        replacement = POSTPROCESS_REPLACEMENTS.get(word.lower())
        if not replacement:
            return word

        # Сохраняем регистр первой буквы
        if word[0].isupper():
            return replacement.capitalize()
        return replacement

    # \b — граница слова в regex
    # \w+ — буквы/цифры/подчёркивание
    # Русские буквы входят в \w в Python 3 (Unicode-aware)
    return re.sub(r"\b\w+\b", _replace_word, text)