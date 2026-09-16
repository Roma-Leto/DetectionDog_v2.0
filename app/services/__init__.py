"""
Пакет сервисов приложения.

- image_service — сжатие, thumbnail, сохранение изображений
- vision_client — HTTP-клиент к vision-сервису на ПК
- stats_service — статистика для дашборда
- search_service — поиск (быстрый и расширенный)
"""

from app.services.image_service import (
    ImageProcessingError,
    delete_item_images,
    process_and_save_image,
)
from app.services.search_service import advanced_search, quick_search, random_item
from app.services.stats_service import DashboardStats, get_dashboard_stats
from app.services.vision_client import VisionClient, get_vision_client

__all__ = [
    # image
    "ImageProcessingError",
    "process_and_save_image",
    "delete_item_images",
    # vision
    "VisionClient",
    "get_vision_client",
    # stats
    "DashboardStats",
    "get_dashboard_stats",
    # search
    "quick_search",
    "advanced_search",
    "random_item",
]