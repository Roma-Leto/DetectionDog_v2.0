"""FastAPI-роуты vision-сервиса."""

from app.routers import analyze, health

__all__ = ["analyze", "health"]