"""
Роут /translate — перевод текста en→ru.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from app.config import Settings, get_settings
from app.models.schemas import ErrorResponse, TranslateRequest, TranslateResponse
from app.services.model_loader import ModelLoadError
from app.services.translator import translate

logger = logging.getLogger(__name__)

router = APIRouter(tags=["translate"])


@router.post(
    "/translate",
    response_model=TranslateResponse,
    responses={
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
def translate_endpoint(
    request: TranslateRequest,
    settings: Settings = Depends(get_settings),
) -> TranslateResponse:
    """
    Переводит текст с английского на русский.

    NLLB-200 — многоязычная модель. По умолчанию:
    - source_lang = eng_Latn
    - target_lang = rus_Cyrl
    """
    if not request.text or not request.text.strip():
        raise HTTPException(status_code=400, detail="Пустой текст")

    source_lang = request.source_lang or settings.source_lang
    target_lang = request.target_lang or settings.target_lang

    try:
        translated = translate(
            text=request.text,
            settings=settings,
            source_lang=source_lang,
            target_lang=target_lang,
        )
    except ModelLoadError as e:
        logger.exception("Model load failed")
        raise HTTPException(status_code=500, detail=f"Model load failed: {e}")
    except Exception as e:
        logger.exception("Translation failed")
        raise HTTPException(status_code=500, detail=f"Translation failed: {e}")

    return TranslateResponse(
        translated=translated,
        source_lang=source_lang,
        target_lang=target_lang,
        model=settings.model_id,
    )