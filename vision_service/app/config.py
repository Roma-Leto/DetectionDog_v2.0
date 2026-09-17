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

    # --- Translator Service (ПК, порт 5002) ---
    translator_service_url: str = "http://192.168.52.200:5002"
    translator_health_timeout: int = 3
    translator_translate_timeout: int = 30
    translator_enabled: bool = True   # можно отключить перевод

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
    # 1. title — конкретное название предмета (2-5 слов),
    #    включая дескриптор содержимого/назначения, если виден.
    # 2. description — детальное описание ГЛАВНОГО объекта
    #    (не фона), до 6 предложений.
    # 3. condition — новое/б/у/сломанное. Модель часто не может
    #    определить точно; отвечает, если уверена, иначе 'used'.
    # 4. quantity — количество одинаковых предметов.

    # Title: простой прямой вопрос. Moondream не понимает сложных инструкций.
    prompt_title: str = "What object is in the center of this photo?"

    # Description: caption даёт лучшее описание, чем answer_question.
    # Оставляем его для description через model.caption().
    # prompt_description оставляем на случай прямого вызова.
    prompt_description: str = (
        "Describe the main object in the center of this photo. "
        "Mention its color, material, condition, and any readable text on it. "
        "Do not describe the background or surface. "
        "Only quote text in Latin alphabet; ignore any non-Latin text."
    )

    prompt_condition: str = (
        "Is the object in this photo new, used, or broken? "
        "Answer with one word."
    )

    prompt_quantity: str = (
        "How many identical boxes or items of the same type are visible in this photo? "
        "Count carefully. Answer with a single number."
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