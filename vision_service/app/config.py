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

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Настройки vision-сервиса."""

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- HTTP-сервер ---
    host: str = "0.0.0.0"
    port: int = 5001
    log_level: Literal["debug", "info", "warning", "error"] = "info"

    # --- Модель ---
    model_id: str = "vikhyatk/moondream2"
    model_revision: str = "2024-08-26"

    # --- Устройство ---
    device: Literal["auto", "cuda", "cpu"] = "auto"
    dtype: Literal["float16", "bfloat16", "float32"] = "float16"

    # --- Ограничения ---
    max_image_size: int = Field(default=16 * 1024 * 1024)
    inference_timeout: int = Field(default=60)

    # ============================================================
    # Промпты
    # ============================================================
    # Все промпты на английском — Moondream обучен на английском
    # и игнорирует просьбы «answer in Russian».
    #
    # Стратегия:
    # 1. title — просим короткое НАЗВАНИЕ предмета (2-5 слов).
    #    Не описание сцены — именно «что это за предмет».
    # 2. description — общее описание сцены (для деталей).
    # 3. condition — состояние предмета.
    # 4. quantity — количество одинаковых.
    #
    # Категорию НЕ спрашиваем: модель путается на списке из 20+,
    # всегда отвечает «Строительные инструменты» или похожим.
    # Пользователь выбирает категорию вручную в форме.

    prompt_title: str = (
        "What type of object is shown in this photo? "
        "Answer with a generic object name, 2 to 4 words. "
        "Do NOT use brand names or text from the packaging. "
        "Do NOT describe the scene or background. "
        "Examples: 'hammer', 'medicine box', 'cigarette pack', 'book', 'shoes'."
    )

    prompt_description: str = (
        "Describe everything you see in this photo in one or two sentences. "
        "Mention objects, their colors, materials, and any readable text. "
        "Be specific and factual."
    )

    prompt_condition: str = (
        "Look at the main object in this photo. "
        "Is it new, used, or broken? "
        "Answer with exactly one word: 'new', 'used', or 'broken'."
    )

    prompt_quantity: str = (
        "Count the identical objects of the same type in this photo. "
        "Answer with a single number. "
        "If unsure, answer '1'."
    )

    @property
    def model_cache_dir(self) -> Path:
        return BASE_DIR / "models"

    @property
    def log_dir(self) -> Path:
        return BASE_DIR / "logs"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Singleton настроек."""
    return Settings()