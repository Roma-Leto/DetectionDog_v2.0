"""
Пакет сервисов приложения.

- image_service — сжатие, thumbnail, сохранение изображений
- vision_client — HTTP-клиент к vision-сервису на ПК
"""

from app.services.image_service import (
    ImageProcessingError,
    delete_item_images,
    process_and_save_image,
)
from app.services.vision_client import VisionClient, get_vision_client

__all__ = [
    "ImageProcessingError",
    "process_and_save_image",
    "delete_item_images",
    "VisionClient",
    "get_vision_client",
]