"""
Роут /health — проверка доступности сервиса.

Нетбук вызывает этот эндпоинт перед отправкой фото на анализ
(см. app/services/vision_client.py на стороне Flask).
Если /health возвращает 200 — ПК доступен.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

import torch

from app.config import Settings, get_settings
from app.models.schemas import HealthResponse
from app.services.model_loader import is_model_loaded

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Проверка доступности сервиса",
)
def health(settings: Settings = Depends(get_settings)) -> HealthResponse:
    """
    Возвращает статус сервиса и информацию о модели.

    Всегда 200, если сервер запущен. Поле status описывает
    состояние (ok / error).
    """
    cuda_available = torch.cuda.is_available()
    gpu_name = torch.cuda.get_device_name(0) if cuda_available else None

    return HealthResponse(
        status="ok",
        model=settings.model_id,
        device=settings.device,
        dtype=settings.dtype,
        cuda_available=cuda_available,
        gpu_name=gpu_name,
        model_loaded=is_model_loaded(),
    )


@router.get(
    "/health/live",
    summary="Liveness probe",
    include_in_schema=False,
)
def live() -> JSONResponse:
    """
    Простой liveness probe без обращения к CUDA.

    Используется для быстрой проверки, что процесс жив,
    до готовности модели. NSSM и мониторинг могут дёргать его.
    """
    return JSONResponse({"status": "alive"})