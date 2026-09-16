"""
Конфигурация vision-сервиса.

Использует pydantic-settings: автоматически читает переменные
окружения и .env. Все значения типизированы и валидируются
при старте приложения.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Корень проекта (папка vision_service)
BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """
    Настройки vision-сервиса.

    Значения по умолчанию рассчитаны на локальный запуск на ПК.
    Переопределяются через переменные окружения или .env.
    """

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # игнорировать неизвестные переменные
    )

    # --- HTTP-сервер ---
    host: str = "0.0.0.0"
    port: int = 5001
    log_level: Literal["debug", "info", "warning", "error"] = "info"

    # --- Модель ---
    model_id: str = "vikhyatk/moondream2"
    model_revision: str = "2024-08-26"

    # --- Устройство и точность ---
    # auto  — GPU если доступно, иначе CPU
    # cuda  — только GPU (ошибка, если нет)
    # cpu   — только CPU
    device: Literal["auto", "cuda", "cpu"] = "auto"

    # float16 — быстро на GPU (GTX 1080 поддерживает)
    # bfloat16 — только для Ampere+ (GTX 1080 не поддерживает!)
    # float32 — медленно, но безопасно
    dtype: Literal["float16", "bfloat16", "float32"] = "float16"

    # --- Ограничения ---
    max_image_size: int = Field(default=16 * 1024 * 1024)  # 16 МБ
    inference_timeout: int = Field(default=60)  # секунд

    # --- Промпты (для улучшения качества ответов) ---
    # Можно переопределить в .env без правки кода
    prompt_caption: str = (
        "Describe the main object in this photo in one short sentence "
        "in Russian. Be specific: what it is, its material, size, "
        "and any readable text on it."
    )
    prompt_category: str = (
        "Answer in Russian with ONE word or short phrase. "
        "Which category from this list best describes the object? "
        "Categories: Строительные инструменты, Строительные материалы, "
        "Праздничный, Схемотехника, Одежда, Обувь, Инструменты, Документы, "
        "Канцелярия, Бытовые, Интерьерные, Растения/Животные, Развлечения, "
        "Разное, Химия, Медицинское, Для изделий из кожи, Музыкальные, "
        "Музыка, Аптечка/Медицина. Answer only the category name."
    )
    prompt_condition: str = (
        "Answer in Russian with ONE word. Is the object on this photo "
        "new, used, or broken? Answer: 'новый', 'б/у', or 'сломанный'."
    )
    prompt_quantity: str = (
        "Answer with a single number. How many identical objects "
        "of the same type are on this photo? "
        "If unsure, answer '1'."
    )

    @property
    def model_cache_dir(self) -> Path:
        """Директория для кэша модели HuggingFace."""
        return BASE_DIR / "models"

    @property
    def log_dir(self) -> Path:
        """Директория для логов."""
        return BASE_DIR / "logs"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Возвращает singleton настроек.

    lru_cache гарантирует, что Settings создаётся один раз
    за время жизни процесса.
    """
    return Settings()