"""
Роут /analyze — основной эндпоинт анализа изображений.

Принимает multipart/form-data с полем `image`.
Возвращает AnalyzeResponse (JSON).

Использует PIL для декодирования. Конвертирует в RGB, если нужно
(PNG с альфой, grayscale, HEIC через pillow-heif — пока не подключён).
"""

from __future__ import annotations

import io
import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError

from app.config import Settings, get_settings
from app.models.schemas import AnalyzeResponse, ErrorResponse
from app.services.analyzer import analyze_image
from app.services.model_loader import ModelLoadError

logger = logging.getLogger(__name__)

router = APIRouter(tags=["analyze"])


@router.post(
    "/analyze",
    response_model=AnalyzeResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Невалидное изображение"},
        413: {"model": ErrorResponse, "description": "Файл слишком большой"},
        500: {"model": ErrorResponse, "description": "Ошибка загрузки модели"},
    },
    summary="Анализ изображения предмета",
)
async def analyze(
    image: UploadFile = File(..., description="Изображение предмета"),
    settings: Settings = Depends(get_settings),
) -> AnalyzeResponse:
    """
    Принимает изображение, возвращает структурированный результат.

    Поля ответа:
    - title: краткое название (1-5 слов)
    - description: развёрнутое описание
    - category_hint: подсказка категории из нашего списка
    - condition_hint: 'новый' | 'б/у' | 'сломанный'
    - quantity: количество одинаковых предметов
    - confidence: уверенность 0..1
    """
    # --- 1. Читаем файл с ограничением размера ---
    try:
        raw_bytes = await image.read()
    except Exception as e:
        logger.warning("Failed to read upload: %s", e)
        raise HTTPException(status_code=400, detail="Cannot read uploaded file")

    if not raw_bytes:
        raise HTTPException(status_code=400, detail="Empty file")

    if len(raw_bytes) > settings.max_image_size:
        raise HTTPException(
            status_code=413,
            detail=f"File too large: {len(raw_bytes)} > {settings.max_image_size}",
        )

    # --- 2. Декодируем через PIL ---
    try:
        pil_image = Image.open(io.BytesIO(raw_bytes))
        pil_image.load()
    except UnidentifiedImageError:
        raise HTTPException(
            status_code=400,
            detail="Not a valid image or unsupported format",
        )
    except Exception as e:
        logger.warning("PIL decode error: %s", e)
        raise HTTPException(status_code=400, detail=f"Cannot decode image: {e}")

    # --- 3. Конвертируем в RGB ---
    pil_image = _ensure_rgb(pil_image)

    # --- 4. Анализ ---
    try:
        result = analyze_image(pil_image, settings)
    except ModelLoadError as e:
        logger.exception("Model load failed")
        raise HTTPException(status_code=500, detail=f"Model load failed: {e}")
    except Exception as e:
        logger.exception("Analysis failed")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {e}")

    return result


# ============================================================
# Приватные функции
# ============================================================


def _ensure_rgb(image: Image.Image) -> Image.Image:
    """
    Приводит изображение к RGB:
    - RGBA/LA/P → накладываем на белый фон
    - L (grayscale) → конвертируем в RGB
    - CMYK → конвертируем в RGB
    """
    if image.mode == "RGB":
        return image

    if image.mode in ("RGBA", "LA"):
        background = Image.new("RGB", image.size, (255, 255, 255))
        background.paste(image, mask=image.split()[-1])
        return background

    if image.mode == "P":
        # Палитровое — сначала в RGBA, потом через RGB
        return _ensure_rgb(image.convert("RGBA"))

    # Всё остальное — просто convert
    return image.convert("RGB")