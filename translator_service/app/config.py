"""
Конфигурация translator-сервиса.

Использует pydantic-settings: автоматически читает переменные
окружения и .env.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Настройки translator-сервиса."""

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- HTTP-сервер ---
    host: str = "0.0.0.0"
    port: int = 5002
    log_level: Literal["debug", "info", "warning", "error"] = "info"

    # --- Модель ---
    # NLLB-200-distilled-600M — качественная многоязычная модель.
    # Для меньшего размера: "Helsinki-NLP/opus-mt-en-ru" (~300 МБ).
    model_id: str = "facebook/nllb-200-distilled-600M"

    # Языковые коды NLLB (ISO-639-3 + script)
    source_lang: str = "eng_Latn"
    target_lang: str = "rus_Cyrl"

    # --- Устройство ---
    device: Literal["auto", "cuda", "cpu"] = "auto"
    dtype: Literal["float16", "bfloat16", "float32"] = "float16"

    # --- Лимиты ---
    max_text_length: int = Field(default=2000)
    inference_timeout: int = Field(default=30)

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