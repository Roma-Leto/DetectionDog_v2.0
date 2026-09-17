"""
Загрузка NLLB-модели для перевода en→ru.

Singleton с lazy loading: модель грузится при первом запросе /translate.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass

import torch
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

from app.config import Settings

logger = logging.getLogger(__name__)


class ModelLoadError(Exception):
    """Ошибка загрузки модели."""


@dataclass
class LoadedModel:
    """Загруженная модель + метаданные."""

    model: object
    tokenizer: object
    device: str
    dtype: str
    model_id: str
    gpu_name: str | None


_model: LoadedModel | None = None
_load_lock = threading.Lock()


def get_model(settings: Settings) -> LoadedModel:
    """
    Возвращает загруженную модель перевода.

    При первом вызове грузит модель (~600 МБ, 1-3 минуты).
    Потокобезопасно.
    """
    global _model

    if _model is not None:
        return _model

    with _load_lock:
        if _model is not None:
            return _model

        logger.info("Loading translation model: %s", settings.model_id)
        try:
            _model = _load_model(settings)
        except Exception as e:
            logger.exception("Failed to load model")
            raise ModelLoadError(str(e)) from e

        logger.info(
            "Model loaded: device=%s dtype=%s gpu=%s",
            _model.device,
            _model.dtype,
            _model.gpu_name,
        )
        return _model


def is_model_loaded() -> bool:
    """True, если модель уже загружена."""
    return _model is not None


def unload_model() -> None:
    """Освобождает память."""
    global _model
    with _load_lock:
        if _model is not None:
            del _model.model
            del _model.tokenizer
            _model = None
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            logger.info("Model unloaded")


def _load_model(settings: Settings) -> LoadedModel:
    """Загружает NLLB с HuggingFace."""
    device, gpu_name = _resolve_device(settings.device)
    torch_dtype = _resolve_dtype(settings.dtype, device)
    dtype_str = str(torch_dtype).replace("torch.", "")

    cache_dir = settings.model_cache_dir
    cache_dir.mkdir(parents=True, exist_ok=True)

    try:
        tokenizer = AutoTokenizer.from_pretrained(
            settings.model_id,
            cache_dir=str(cache_dir),
        )

        model = AutoModelForSeq2SeqLM.from_pretrained(
            settings.model_id,
            torch_dtype=torch_dtype,
            cache_dir=str(cache_dir),
        )

        try:
            model = model.to(device)
        except RuntimeError as e:
            if "out of memory" in str(e).lower():
                logger.warning("CUDA OOM, falling back to CPU")
                device = "cpu"
                dtype_str = "float32"
                model = model.to("cpu").to(torch.float32)
            else:
                raise

        model.eval()

    except Exception as e:
        raise ModelLoadError(f"Failed to load {settings.model_id}: {e}") from e

    return LoadedModel(
        model=model,
        tokenizer=tokenizer,
        device=device,
        dtype=dtype_str,
        model_id=settings.model_id,
        gpu_name=gpu_name,
    )


def _resolve_device(requested: str) -> tuple[str, str | None]:
    """Определяет устройство."""
    cuda_available = torch.cuda.is_available()

    if requested == "cuda":
        if not cuda_available:
            raise ModelLoadError("device=cuda, но CUDA недоступна")
        return "cuda:0", torch.cuda.get_device_name(0)

    if requested == "cpu":
        return "cpu", None

    if cuda_available:
        gpu_name = torch.cuda.get_device_name(0)
        logger.info("Auto-selected CUDA: %s", gpu_name)
        return "cuda:0", gpu_name

    logger.warning("CUDA не доступна, fallback на CPU")
    return "cpu", None


def _resolve_dtype(requested: str, device: str) -> torch.dtype:
    """Определяет dtype."""
    if device == "cpu":
        return torch.float32
    if requested == "float16":
        return torch.float16
    if requested == "float32":
        return torch.float32
    if requested == "bfloat16":
        if _cuda_supports_bfloat16():
            return torch.bfloat16
        return torch.float16
    return torch.float16


def _cuda_supports_bfloat16() -> bool:
    """bfloat16 требует compute capability 8.0+."""
    if not torch.cuda.is_available():
        return False
    return torch.cuda.get_device_capability(0)[0] >= 8