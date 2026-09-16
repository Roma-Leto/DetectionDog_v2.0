"""
Точка входа FastAPI-приложения.

Запуск:
    uv run uvicorn main:app --host 0.0.0.0 --port 5001

Или через uvicorn CLI с флагами из .env:
    uv run python main.py
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.routers import analyze, health


# ============================================================
# Логирование
# ============================================================


def _setup_logging(level: str) -> None:
    """Настраивает корневой logger."""
    logging.basicConfig(
        level=level.upper(),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


# ============================================================
# Lifespan (замена @app.on_event)
# ============================================================


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Управление жизненным циклом приложения.

    On startup:
    - загружает настройки
    - НЕ грузит модель (lazy loading при первом /analyze,
      чтобы приложение поднималось мгновенно)

    On shutdown:
    - освобождает память модели, если она была загружена
    """
    settings = get_settings()
    _setup_logging(settings.log_level)

    logger = logging.getLogger(__name__)
    logger.info("Starting DetectionDog Vision Service")
    logger.info("Model: %s @ %s", settings.model_id, settings.model_revision)
    logger.info("Device: %s, dtype: %s", settings.device, settings.dtype)

    yield

    # --- Shutdown ---
    from app.services.model_loader import is_model_loaded, unload_model

    if is_model_loaded():
        logger.info("Unloading model on shutdown")
        unload_model()

    logger.info("Shutdown complete")


# ============================================================
# Приложение
# ============================================================


app = FastAPI(
    title="DetectionDog Vision Service",
    description=(
        "Анализ фото предметов через Moondream. "
        "Используется Flask-приложением DetectionDog на нетбуке."
    ),
    version="1.0.0",
    lifespan=lifespan,
)


# --- Роуты ---
app.include_router(health.router)
app.include_router(analyze.router)


# --- Корень ---
@app.get("/", include_in_schema=False)
def root() -> JSONResponse:
    """Корень: перенаправляет на документацию."""
    return JSONResponse(
        {
            "service": "DetectionDog Vision Service",
            "version": "1.0.0",
            "docs": "/docs",
            "health": "/health",
        }
    )


# ============================================================
# CLI-запуск
# ============================================================


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level,
        reload=False,  # в продакшене — без reload
    )