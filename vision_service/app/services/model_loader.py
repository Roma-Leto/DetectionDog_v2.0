"""
Загрузка Moondream.

Особенности:
1. Singleton: модель грузится один раз за жизнь процесса.
2. Lazy loading: при первом запросе /analyze, а не при старте —
   чтобы приложение поднялось быстро.
3. Оптимизация под GTX 1080 (8 ГБ):
   - float16 на GPU (экономит память, ускоряет)
   - device_map="cuda:0" — явно указываем GPU
   - low_cpu_mem_usage=True — не держим модель дважды в RAM
4. Опциональный CPU-fallback: если CUDA недоступна — работаем на CPU.

Moondream API:
    model = AutoModelForCausalLM.from_pretrained(...)
    model.caption(image, length="short")  -> {"caption": str}
    model.query(image, question=...)      -> {"answer": str}
    model.detect(image, object=...)       -> {"objects": [...]}
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from pathlib import Path

import torch
from PIL import Image
from transformers import AutoModelForCausalLM, AutoTokenizer

from app.config import Settings

logger = logging.getLogger(__name__)


# ============================================================
# Исключения
# ============================================================


class ModelLoadError(Exception):
    """Ошибка загрузки модели."""


# ============================================================
# Singleton-контейнер
# ============================================================


@dataclass
class LoadedModel:
    """Загруженная модель + метаданные."""

    model: object  # Moondream (AutoModelForCausalLM)
    tokenizer: object
    device: str  # "cuda:0" или "cpu"
    dtype: str  # "float16" или "float32"
    model_id: str
    gpu_name: str | None


# Глобальный singleton + мьютекс для потокобезопасной загрузки
_model: LoadedModel | None = None
_load_lock = threading.Lock()


# ============================================================
# Публичные функции
# ============================================================


def get_model(settings: Settings) -> LoadedModel:
    """
    Возвращает загруженную модель.

    При первом вызове грузит с диска/HuggingFace (~3 ГБ, может занять
    5-20 минут в зависимости от скорости сети).

    Потокобезопасно: два одновременных вызова не загрузят модель дважды.

    :raises ModelLoadError: если загрузка не удалась.
    """
    global _model

    if _model is not None:
        return _model

    with _load_lock:
        # Двойная проверка после взятия блокировки
        if _model is not None:
            return _model

        logger.info("Loading Moondream model: %s @ %s", settings.model_id, settings.model_revision)
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
    """True, если модель уже загружена в память."""
    return _model is not None


def unload_model() -> None:
    """
    Освобождает память. Полезно в тестах, чтобы не держать
    несколько моделей одновременно.
    """
    global _model
    with _load_lock:
        if _model is not None:
            del _model.model
            del _model.tokenizer
            _model = None
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            logger.info("Model unloaded")


# ============================================================
# Приватные функции
# ============================================================


def _load_model(settings: Settings) -> LoadedModel:
    """
    Загружает Moondream с HuggingFace.

    Логика выбора устройства:
    - device="auto": CUDA если доступна, иначе CPU
    - device="cuda": принудительно CUDA, ошибка если нет
    - device="cpu":  принудительно CPU

    dtype:
    - float16: на CUDA (GTX 1080 поддерживает)
    - float32: на CPU (float16 на CPU медленный)
    """
    # --- Выбор устройства ---
    device, gpu_name = _resolve_device(settings.device)

    # --- Выбор dtype ---
    torch_dtype = _resolve_dtype(settings.dtype, device)
    dtype_str = str(torch_dtype).replace("torch.", "")

    # --- Загрузка ---
    # Гарантируем, что директория для кэша существует
    cache_dir = settings.model_cache_dir
    cache_dir.mkdir(parents=True, exist_ok=True)

    try:
        tokenizer = AutoTokenizer.from_pretrained(
            settings.model_id,
            revision=settings.model_revision,
            cache_dir=str(cache_dir),
        )

        model = AutoModelForCausalLM.from_pretrained(
            settings.model_id,
            revision=settings.model_revision,
            trust_remote_code=True,
            torch_dtype=torch_dtype,
            device_map=device,
            low_cpu_mem_usage=True,
            cache_dir=str(cache_dir),
        )
        model.eval()  # отключаем dropout и прочее для инференса

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
    """
    Определяет устройство и имя GPU.

    :return: (device_str, gpu_name_or_None)
    """
    cuda_available = torch.cuda.is_available()

    if requested == "cuda":
        if not cuda_available:
            raise ModelLoadError("device=cuda requested, but CUDA is not available")
        gpu_name = torch.cuda.get_device_name(0)
        return "cuda:0", gpu_name

    if requested == "cpu":
        return "cpu", None

    # auto
    if cuda_available:
        gpu_name = torch.cuda.get_device_name(0)
        logger.info("Auto-selected CUDA: %s", gpu_name)
        return "cuda:0", gpu_name

    logger.warning("CUDA not available, falling back to CPU (will be slow)")
    return "cpu", None


def _resolve_dtype(requested: str, device: str) -> torch.dtype:
    """
    Определяет torch.dtype.

    На CPU float16 работает медленно, поэтому форсим float32.
    На CUDA — что запрошено.

    bfloat16 не поддерживается GTX 1080 (compute capability 6.1,
    а bfloat16 требует 8.0+). Если пользователь запросил bfloat16
    на неподдерживаемой карте — откатываемся на float16.
    """
    if device == "cpu":
        if requested != "float32":
            logger.warning("CPU device forces float32 (requested %s)", requested)
        return torch.float32

    # device == cuda
    if requested == "float16":
        return torch.float16
    if requested == "float32":
        return torch.float32
    if requested == "bfloat16":
        if _cuda_supports_bfloat16():
            return torch.bfloat16
        logger.warning("bfloat16 not supported on this GPU, falling back to float16")
        return torch.float16

    # fallback
    return torch.float16


def _cuda_supports_bfloat16() -> bool:
    """bfloat16 требует compute capability 8.0+ (Ampere)."""
    if not torch.cuda.is_available():
        return False
    capability = torch.cuda.get_device_capability(0)
    return capability[0] >= 8