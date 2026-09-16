"""
Анализатор изображений через Moondream.

Логика:
1. Принимает PIL.Image.
2. Делает несколько запросов к модели:
   - caption (описание)
   - query: категория
   - query: состояние
   - query: количество
3. Постобрабатывает ответы через category_matcher.
4. Возвращает AnalyzeResponse.

Почему несколько запросов, а не один составной:
Moondream — не instruction-tuned под сложные запросы. Простые
вопросы («what is this?», «how many?») дают более стабильный
результат, чем составные инструкции.
"""

from __future__ import annotations

import logging
import time
from PIL import Image

from app.config import Settings
from app.models.schemas import AnalyzeResponse, RawAnalysis
from app.services import category_matcher as cm
from app.services.model_loader import LoadedModel, get_model

logger = logging.getLogger(__name__)


# ============================================================
# Основная функция
# ============================================================


def analyze_image(
    image: Image.Image,
    settings: Settings,
) -> AnalyzeResponse:
    """
    Анализирует изображение и возвращает структурированный результат.

    :param image: PIL.Image в RGB (не RGBA — конвертируйте заранее)
    :param settings: настройки приложения
    :return: AnalyzeResponse с заполненными полями
    """
    t0 = time.time()
    loaded = get_model(settings)

    # --- Собираем «сырые» ответы от модели ---
    raw = _collect_raw_answers(image, loaded, settings)

    # --- Постобработка ---
    result = _postprocess(raw)

    elapsed = time.time() - t0
    logger.info(
        "Analysis done in %.2fs (device=%s, gpu=%s)",
        elapsed,
        loaded.device,
        loaded.gpu_name or "n/a",
    )

    return result


# ============================================================
# Сбор ответов
# ============================================================


def _collect_raw_answers(
    image: Image.Image,
    loaded: LoadedModel,
    settings: Settings,
) -> RawAnalysis:
    """
    Делает 4 запроса к Moondream и собирает сырые ответы.

    API Moondream2 (revision 2024-08-26, transformers 4.49):
    - model.caption([image], tokenizer=..., length="short")
        → ['строка']  (список строк — по элементу на изображение)
    - embeds = model.encode_image(image) → torch.Tensor
    - model.answer_question(embeds, question, tokenizer)
        → 'строка'    (просто текст, не dict)

    Кодируем изображение один раз, переиспользуем embeds
    для всех 3 VQA-запросов.
    """
    raw = RawAnalysis()
    tokenizer = loaded.tokenizer

    # --- Кодируем изображение один раз (самая тяжёлая часть) ---
    try:
        image_embeds = loaded.model.encode_image(image)
    except Exception as e:
        logger.warning("encode_image failed: %s", e)
        return raw

    # --- 1. Caption ---
    try:
        result = loaded.model.caption([image], tokenizer=tokenizer, length="short")
        raw.caption = _extract_text(result)
    except Exception as e:
        logger.warning("Caption failed: %s", e)

    # --- 2. Категория ---
    try:
        result = loaded.model.answer_question(
            image_embeds, settings.prompt_category, tokenizer
        )
        raw.category_raw = _extract_text(result)
    except Exception as e:
        logger.warning("Category query failed: %s", e)

    # --- 3. Состояние ---
    try:
        result = loaded.model.answer_question(
            image_embeds, settings.prompt_condition, tokenizer
        )
        raw.condition_raw = _extract_text(result)
    except Exception as e:
        logger.warning("Condition query failed: %s", e)

    # --- 4. Количество ---
    try:
        result = loaded.model.answer_question(
            image_embeds, settings.prompt_quantity, tokenizer
        )
        raw.quantity_raw = _extract_text(result)
    except Exception as e:
        logger.warning("Quantity query failed: %s", e)

    return raw


def _extract_text(result) -> str | None:
    """
    Универсальный извлекатель текста из ответа Moondream.

    Поддерживает все известные форматы:
    - str            → сам текст
    - list[str]      → первый элемент (caption возвращает список)
    - list[dict]     → первый элемент + ключ "caption"/"answer"
    - dict           → значение по ключу "caption"/"answer"
    """
    if result is None:
        return None

    if isinstance(result, str):
        return result.strip() or None

    if isinstance(result, list):
        if not result:
            return None
        return _extract_text(result[0])

    if isinstance(result, dict):
        for key in ("caption", "answer", "text"):
            value = result.get(key)
            if isinstance(value, str):
                return value.strip() or None
        return None

    return None


# ============================================================
# Постобработка
# ============================================================


def _postprocess(raw: RawAnalysis) -> AnalyzeResponse:
    """
    Преобразует сырые ответы в AnalyzeResponse:

    1. title — из caption, обрезаем до 5 слов
    2. description — из caption (полный текст), обрезаем 2000 символов
    3. category_hint — матчим на список категорий
    4. condition_hint — матчим на список состояний
    5. quantity — парсим число
    6. confidence — эвристика (см. _estimate_confidence)
    """

    # --- Логируем сырые ответы для отладки ---
    logger.info(
        "Raw answers: caption=%r, category=%r, condition=%r, quantity=%r",
        raw.caption,
        raw.category_raw,
        raw.condition_raw,
        raw.quantity_raw,
    )

    # --- Title и description из caption ---
    title = cm.clean_title(raw.caption)
    description = cm.clean_description(raw.caption)

    # --- Категория ---
    category_hint = cm.match_category(raw.category_raw)

    # --- Состояние ---
    condition_hint = cm.match_condition(raw.condition_raw)

    # --- Количество ---
    quantity = cm.parse_quantity(raw.quantity_raw, default=1)

    # --- Уверенность ---
    confidence = _estimate_confidence(
        caption=raw.caption,
        category_hint=category_hint,
        condition_hint=condition_hint,
    )

    return AnalyzeResponse(
        title=title,
        description=description,
        category_hint=category_hint,
        condition_hint=condition_hint,
        quantity=quantity,
        confidence=confidence,
    )


def _estimate_confidence(
    *,
    caption: str | None,
    category_hint: str | None,
    condition_hint: str | None,
) -> float:
    """
    Эвристическая оценка уверенности.

    Мы не имеем доступа к logits Moondream (его API их не возвращает),
    поэтому оцениваем косвенно:

    - caption не пустой: +0.4
    - category найден:   +0.3
    - condition найден:  +0.3

    Итог в диапазоне [0, 1].
    """
    score = 0.0

    if caption and caption.strip():
        score += 0.4
    if category_hint:
        score += 0.3
    if condition_hint:
        score += 0.3

    return round(min(1.0, score), 2)