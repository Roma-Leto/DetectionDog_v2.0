"""
Конфигурация Flask-приложения DetectionDog v2.0.

Используется паттерн «класс на окружение»: базовый класс содержит
общие настройки, а наследники переопределяют специфичные.
Активный класс выбирается в фабрике приложения через переменную
окружения FLASK_ENV.
"""

from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

# Загружаем переменные из .env в os.environ.
# override=False — не перезаписываем уже установленные переменные
# (важно для продакшена, где значения могут приходить из systemd).
load_dotenv(override=False)

# Корень проекта: .../detectiondog
BASE_DIR = Path(__file__).resolve().parent.parent


class BaseConfig:
    """Общие настройки для всех окружений."""

    # --- Flask core ---
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret-change-me")
    DEBUG: bool = False
    TESTING: bool = False

    # --- Database ---
    SQLALCHEMY_DATABASE_URI: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://dd_user:dd_password@localhost:5432/detectiondog",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS: bool = False
    SQLALCHEMY_ENGINE_OPTIONS: dict = {
        # Небольшой пул — нагрузка 3 пользователя
        "pool_size": 5,
        "max_overflow": 10,
        "pool_pre_ping": True,   # проверка живости соединения перед выдачей
        "pool_recycle": 3600,    # пересоздавать соединения раз в час
    }

    # --- Uploads ---
    UPLOAD_FOLDER: Path = BASE_DIR / os.getenv("UPLOAD_FOLDER", "app/static/uploads")
    MAX_CONTENT_LENGTH: int = int(os.getenv("MAX_CONTENT_LENGTH", 16 * 1024 * 1024))
    IMAGE_MAX_DIMENSION: int = int(os.getenv("IMAGE_MAX_DIMENSION", 1920))
    IMAGE_JPEG_QUALITY: int = int(os.getenv("IMAGE_JPEG_QUALITY", 85))
    THUMBNAIL_SIZE: int = int(os.getenv("THUMBNAIL_SIZE", 300))
    ALLOWED_IMAGE_EXTENSIONS: set[str] = {"jpg", "jpeg", "png", "webp", "heic"}

    # --- Vision service (ПК в локальной сети) ---
    VISION_SERVICE_URL: str = os.getenv("VISION_SERVICE_URL", "http://192.168.1.20:5001")
    VISION_HEALTH_TIMEOUT: int = int(os.getenv("VISION_HEALTH_TIMEOUT", 3))
    VISION_ANALYZE_TIMEOUT: int = int(os.getenv("VISION_ANALYZE_TIMEOUT", 30))

    # --- Pagination ---
    ITEMS_PER_PAGE: int = int(os.getenv("ITEMS_PER_PAGE", 20))

    # --- Session ---
    SESSION_COOKIE_HTTPONLY: bool = True
    SESSION_COOKIE_SAMESITE: str = "Lax"
    SESSION_COOKIE_SECURE: bool = False  # True только при HTTPS
    PERMANENT_SESSION_LIFETIME: timedelta = timedelta(
        seconds=int(os.getenv("PERMANENT_SESSION_LIFETIME", 86400))
    )

    # --- WTForms ---
    WTF_CSRF_ENABLED: bool = True
    WTF_CSRF_TIME_LIMIT: int | None = None  # токен живёт столько же, сколько сессия


class DevelopmentConfig(BaseConfig):
    """Настройки для локальной разработки на ПК."""

    DEBUG: bool = True
    # Для отладки удобнее видеть SQL-запросы
    SQLALCHEMY_ECHO: bool = False  # включайте True, если нужно видеть SQL


class ProductionConfig(BaseConfig):
    """Настройки для продакшена на нетбуке."""

    DEBUG: bool = False


class TestingConfig(BaseConfig):
    """Настройки для тестов (pytest)."""

    TESTING: bool = True
    WTF_CSRF_ENABLED: bool = False  # отключаем CSRF для удобства тестов
    SQLALCHEMY_DATABASE_URI: str = os.getenv(
        "TEST_DATABASE_URL",
        "postgresql+psycopg://dd_user:dd_password@localhost:5432/detectiondog_test",
    )


# Реестр конфигураций — используется в фабрике приложения
CONFIG_MAP: dict[str, type[BaseConfig]] = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}


def get_config() -> type[BaseConfig]:
    """Возвращает класс конфигурации на основе FLASK_ENV."""
    env = os.getenv("FLASK_ENV", "development").lower()
    return CONFIG_MAP.get(env, DevelopmentConfig)