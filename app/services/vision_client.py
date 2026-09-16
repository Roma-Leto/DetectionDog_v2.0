"""
HTTP-клиент к vision-сервису на ПК (FastAPI + Moondream).

Ключевые требования:
1. Graceful degradation: если ПК выключен или недоступен — вернуть None,
   чтобы роут формы продолжил работу без автозаполнения.
2. Быстрый healthcheck: таймаут 3 секунды, чтобы не блокировать форму.
3. Не падать на сетевых ошибках: любые исключения requests ловим и логируем.
4. Клиент — singleton на процесс, создаётся через get_vision_client().

Контракт vision-сервиса (см. docs/api_vision.md):

    GET  /health   → 200 {"status": "ok", "model": "moondream", ...}
    POST /analyze  → 200 {
        "title": str,
        "description": str,
        "category_hint": str,       # имя категории из списка
        "condition_hint": str,      # "новый" | "б/у" | "сломанный"
        "quantity": int,
        "confidence": float,        # 0.0 .. 1.0
    }

    При ошибке разбора: 200 с полями None / 0.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import requests
from flask import current_app

logger = logging.getLogger(__name__)


# ============================================================
# Датакласс результата анализа
# ============================================================


@dataclass
class VisionResult:
    """
    Результат анализа изображения.

    Все поля опциональны: если модель не смогла распознать —
    поле будет None (или 0 для quantity).
    Роут формы решает, что подставлять в форму.
    """

    title: str | None = None
    description: str | None = None
    category_hint: str | None = None
    condition_hint: str | None = None
    quantity: int = 1
    confidence: float = 0.0

    def is_empty(self) -> bool:
        """True, если модель не заполнила ни одного осмысленного поля."""
        return (
            not self.title
            and not self.description
            and not self.category_hint
            and not self.condition_hint
        )


# ============================================================
# Клиент
# ============================================================


class VisionClient:
    """
    HTTP-клиент к vision-сервису на ПК в LAN.

    Все методы возвращают результат или None — исключений наружу
    не пробрасывает. Это сделано специально: пользователь должен
    иметь возможность добавить предмет даже без работающего ПК.
    """

    def __init__(
        self,
        base_url: str,
        health_timeout: int = 3,
        analyze_timeout: int = 30,
    ) -> None:
        # Убираем trailing slash
        self.base_url = base_url.rstrip("/")
        self.health_timeout = health_timeout
        self.analyze_timeout = analyze_timeout

    # --- Публичные методы ---

    def is_available(self) -> bool:
        """
        Быстрая проверка доступности vision-сервиса.

        Возвращает True только если:
        - TCP-соединение установилось;
        - HTTP-статус 200;
        - тело содержит {"status": "ok"}.

        Таймаут — health_timeout секунд (по умолчанию 3).
        Никогда не бросает исключение.
        """
        try:
            response = requests.get(
                f"{self.base_url}/health",
                timeout=self.health_timeout,
            )
            if response.status_code != 200:
                return False
            data = response.json()
            return data.get("status") == "ok"
        except requests.RequestException as e:
            logger.debug(f"Vision service unavailable: {e}")
            return False
        except ValueError:
            # Невалидный JSON
            logger.warning("Vision service returned non-JSON /health response")
            return False

    def analyze_image(self, image_bytes: bytes) -> VisionResult | None:
        """
        Отправляет изображение на анализ.

        :param image_bytes: сырые байты изображения (JPEG, PNG).
        :return: VisionResult или None, если сервис недоступен / вернул ошибку.
        """
        # Сначала healthcheck — если ПК выключен, не ждём 30 секунд
        if not self.is_available():
            return None

        try:
            files = {
                "image": ("photo.jpg", image_bytes, "image/jpeg"),
            }
            response = requests.post(
                f"{self.base_url}/analyze",
                files=files,
                timeout=self.analyze_timeout,
            )
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as e:
            logger.warning(f"Vision analyze request failed: {e}")
            return None
        except ValueError:
            logger.warning("Vision service returned non-JSON /analyze response")
            return None

        return self._parse_result(data)

    # --- Приватные методы ---

    @staticmethod
    def _parse_result(data: dict[str, Any]) -> VisionResult:
        """
        Извлекает поля из JSON-ответа. Устойчив к отсутствию полей
        и неверным типам.
        """
        def _str_or_none(value: Any) -> str | None:
            if value is None:
                return None
            s = str(value).strip()
            return s or None

        def _int_or_default(value: Any, default: int = 1) -> int:
            try:
                n = int(value)
                return n if n > 0 else default
            except (TypeError, ValueError):
                return default

        def _float_or_zero(value: Any) -> float:
            try:
                f = float(value)
                # Ограничиваем диапазон 0..1
                return max(0.0, min(1.0, f))
            except (TypeError, ValueError):
                return 0.0

        return VisionResult(
            title=_str_or_none(data.get("title")),
            description=_str_or_none(data.get("description")),
            category_hint=_str_or_none(data.get("category_hint")),
            condition_hint=_str_or_none(data.get("condition_hint")),
            quantity=_int_or_default(data.get("quantity"), default=1),
            confidence=_float_or_zero(data.get("confidence")),
        )


# ============================================================
# Singleton
# ============================================================


_vision_client: VisionClient | None = None


def get_vision_client() -> VisionClient:
    """
    Возвращает singleton-клиент, созданный из текущей конфигурации Flask.

    Singleton привязан к процессу; в тестах можно подменить через
    app.config["VISION_SERVICE_URL"] перед первым вызовом.
    """
    global _vision_client
    if _vision_client is None:
        _vision_client = VisionClient(
            base_url=current_app.config["VISION_SERVICE_URL"],
            health_timeout=current_app.config["VISION_HEALTH_TIMEOUT"],
            analyze_timeout=current_app.config["VISION_ANALYZE_TIMEOUT"],
        )
    return _vision_client


def reset_vision_client() -> None:
    """
    Сбрасывает singleton. Используется в тестах, чтобы подменить
    клиент на мок.
    """
    global _vision_client
    _vision_client = None