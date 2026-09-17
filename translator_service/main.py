"""
Точка входа FastAPI translator-сервиса.

Запуск:
    uv run python main.py
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.routers import health, translate


def _setup_logging(level: str) -> None:
    logging.basicConfig(
        level=level.upper(),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup: логирование конфига. Модель НЕ грузится —
    lazy loading при первом /translate.
    Shutdown: освобождение модели.
    """
    settings = get_settings()
    _setup_logging(settings.log_level)

    logger = logging.getLogger(__name__)
    logger.info("Starting DetectionDog Translator Service")
    logger.info("Model: %s", settings.model_id)
    logger.info("Languages: %s → %s", settings.source_lang, settings.target_lang)
    logger.info("Device: %s, dtype: %s", settings.device, settings.dtype)

    yield

    from app.services.model_loader import is_model_loaded, unload_model

    if is_model_loaded():
        logger.info("Unloading model on shutdown")
        unload_model()

    logger.info("Shutdown complete")


app = FastAPI(
    title="DetectionDog Translator Service",
    description="Перевод en→ru через NLLB-200 для DetectionDog v2.0",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(health.router)
app.include_router(translate.router)


@app.get("/", include_in_schema=False)
def root() -> JSONResponse:
    return JSONResponse({
        "service": "DetectionDog Translator Service",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
    })


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level,
        reload=False,
    )