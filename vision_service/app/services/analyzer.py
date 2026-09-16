"""
Анализатор изображений через Moondream.

Логика (3 запроса вместо 4):
1. title — «что это за предмет?», 2-5 слов.
2. description — общее описание сцены.
3. condition — состояние предмета.
4. quantity — количество.

Категория НЕ определяется: модель путается на списке из 20+,
всегда отвечает первой категорией. Пользователь выбирает в форме.
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


def analyze_image(
    image: Image.Image,
    settings: Settings,
) -> AnalyzeResponse:
    """Анализирует изображение и возвращает структурированный результат."""
    t0 = time.time()
    loaded = get_model(settings)

    raw = _collect_raw_answers(image, loaded, settings)
    result = _postprocess(raw)

    elapsed = time.time() - t0
    logger.info(
        "Analysis done in %.2fs (device=%s, gpu=%s)",
        elapsed,
        loaded.device,
        loaded.gpu_name or "n/a",
    )

    return result


def _collect_raw_answers(
    image: Image.Image,
    loaded: LoadedModel,
    settings: Settings,
) -> RawAnalysis:
    """
    Делает 4 запроса к Moondream.

    API Moondream2 (rev 2024-08-26, transformers 4.49):
    - model.caption([image], tokenizer=..., length="short") → ['строка']
    - embeds = model.encode_image(image) → torch.Tensor
    - model.answer_question(embeds, question, tokenizer) → 'строка'
    """
    raw = RawAnalysis()
    tokenizer = loaded.tokenizer

    # Кодируем изображение один раз
    try:
        image_embeds = loaded.model.encode_image(image)
    except Exception as e:
        logger.warning("encode_image failed: %s", e)
        return raw

    # 1. Title — простой вопрос про объект в центре
    try:
        result = loaded.model.answer_question(
            image_embeds, settings.prompt_title, tokenizer
        )
        raw.title_raw = _extract_text(result)
    except Exception as e:
        logger.warning("Title query failed: %s", e)

    # 2. Description — через caption (даёт богатое описание)
    try:
        result = loaded.model.caption([image], tokenizer=tokenizer,
                                      length="normal")
        raw.caption = _extract_text(result)
    except Exception as e:
        logger.warning("Caption failed: %s", e)

    # 3. Condition
    try:
        result = loaded.model.answer_question(
            image_embeds, settings.prompt_condition, tokenizer
        )
        raw.condition_raw = _extract_text(result)
    except Exception as e:
        logger.warning("Condition query failed: %s", e)

    # 4. Quantity
    try:
        result = loaded.model.answer_question(
            image_embeds, settings.prompt_quantity, tokenizer
        )
        raw.quantity_raw = _extract_text(result)
    except Exception as e:
        logger.warning("Quantity query failed: %s", e)

    return raw


def _postprocess(raw: RawAnalysis) -> AnalyzeResponse:
    """Постобработка сырых ответов."""
    logger.info(
        "Raw answers: title=%r, caption=%r, condition=%r, quantity=%r",
        raw.title_raw,
        raw.caption,
        raw.condition_raw,
        raw.quantity_raw,
    )

    # 1. Title
    title = cm.clean_title(raw.title_raw) or cm.clean_title(raw.caption)

    # 2. Condition
    condition_hint = cm.match_condition(raw.condition_raw)

    # 3. Quantity
    quantity = cm.parse_quantity(raw.quantity_raw, default=1)

    # 4. Description — из структурированных полей + полный caption
    labels = cm.extract_labels(raw.caption) if raw.caption else []
    description = cm.build_short_description(
        quantity=quantity,
        title=title,
        labels=labels,
        full_caption=raw.caption,
    )

    # 5. Category — матчинг по title, fallback на description
    category_hint = cm.match_category_by_title(
        title=title,
        description=raw.caption,
    )

    # 6. Confidence — теперь category_hint уже определён
    confidence = _estimate_confidence(
        title=title,
        description=description,
        condition_hint=condition_hint,
        category_hint=category_hint,
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
    title: str | None,
    description: str | None,
    condition_hint: str | None,
    category_hint: str | None = None,
) -> float:
    """
    Эвристика уверенности:
    - title:      +0.3
    - description:+0.2
    - condition:  +0.2
    - category:   +0.3
    """
    score = 0.0
    if title and title.strip():
        score += 0.3
    if description and description.strip():
        score += 0.2
    if condition_hint:
        score += 0.2
    if category_hint:
        score += 0.3
    return round(min(1.0, score), 2)


def _extract_text(result) -> str | None:
    """
    Извлекает текст из ответа Moondream.

    Поддерживает: str, list[str], list[dict], dict с ключами
    caption/answer/text.
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