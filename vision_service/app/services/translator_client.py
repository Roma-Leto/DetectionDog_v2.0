"""
HTTP-клиент к translator-сервису на ПК (порт 5002).

Используется vision-сервисом для перевода title и caption
с английского на русский.

Graceful degradation: если translator недоступен —
возвращает оригинал без перевода.
"""

from __future__ import annotations

import logging

import requests

logger = logging.getLogger(__name__)


class TranslatorClient:
    """Клиент translator-сервиса."""

    def __init__(
        self,
        base_url: str,
        health_timeout: int = 3,
        translate_timeout: int = 30,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.health_timeout = health_timeout
        self.translate_timeout = translate_timeout

    def is_available(self) -> bool:
        """Быстрая проверка доступности translator."""
        try:
            r = requests.get(
                f"{self.base_url}/health",
                timeout=self.health_timeout,
            )
            if r.status_code != 200:
                return False
            data = r.json()
            return data.get("status") == "ok"
        except requests.RequestException as e:
            logger.debug("Translator unavailable: %s", e)
            return False
        except ValueError:
            return False

    def translate(self, text: str) -> str | None:
        """Переводит текст en→ru. None при ошибке."""
        if not text or not text.strip():
            return ""

        if not self.is_available():
            return None

        try:
            r = requests.post(
                f"{self.base_url}/translate",
                json={"text": text},
                timeout=self.translate_timeout,
            )
            r.raise_for_status()
            data = r.json()
            translated = data.get("translated")
            return translated if translated else None
        except requests.RequestException as e:
            logger.warning("Translation request failed: %s", e)
            return None
        except ValueError:
            logger.warning("Translator returned non-JSON")
            return None


# ============================================================
# Singleton
# ============================================================


_translator_client: TranslatorClient | None = None


def get_translator_client(settings) -> TranslatorClient:
    """
    Возвращает singleton-клиент.

    :param settings: Settings из app.config
    """
    global _translator_client
    if _translator_client is None:
        _translator_client = TranslatorClient(
            base_url=settings.translator_service_url,
            health_timeout=settings.translator_health_timeout,
            translate_timeout=settings.translator_translate_timeout,
        )
    return _translator_client


def reset_translator_client() -> None:
    """Сброс singleton (для тестов)."""
    global _translator_client
    _translator_client = None