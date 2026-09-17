"""
Роут /health — проверка доступности translator-сервиса.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

import torch

from app.config import Settings, get_settings
from app.models.schemas import HealthResponse
from app.services.model_loader import is_model_loaded

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health(settings: Settings = Depends(get_settings)) -> HealthResponse:
    """Статус сервиса и модели."""
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


@router.get("/health/live", include_in_schema=False)
def live() -> JSONResponse:
    """Liveness probe без обращения к CUDA."""
    return JSONResponse({"status": "alive"})