"""
WSGI-обёртка для продакшена.

Flask работает по префиксу /ddog/.
Запуск в Gunicorn: gunicorn --bind 127.0.0.1:8000 wsgi:application
"""

from __future__ import annotations

from app import create_app


class PrefixMiddleware:
    """
    Middleware: устанавливает SCRIPT_NAME = '/ddog',
    чтобы Flask генерировал правильные URL через url_for().

    Запросы к /ddog/... «раздеваются» — Flask видит /...,
    а url_for() сгенерирует /ddog/....
    """

    def __init__(self, app, prefix: str):
        self.app = app
        self.prefix = prefix.rstrip("/")

    def __call__(self, environ, start_response):
        path = environ.get("PATH_INFO", "")

        # /ddog (без слэша) → редирект на /ddog/
        if path == self.prefix:
            start_response("301 Moved Permanently", [
                ("Location", self.prefix + "/"),
                ("Content-Type", "text/plain; charset=utf-8"),
            ])
            return [b"Redirecting to /ddog/"]

        # Пути вне /ddog/ — 404
        if not path.startswith(self.prefix + "/"):
            start_response("404 Not Found", [
                ("Content-Type", "text/plain; charset=utf-8"),
            ])
            return [b"Not Found. Try /ddog/"]

        # Обрезаем префикс: /ddog/items → /items
        environ["SCRIPT_NAME"] = self.prefix
        environ["PATH_INFO"] = path[len(self.prefix):]

        return self.app(environ, start_response)


flask_app = create_app()
application = PrefixMiddleware(flask_app, "/ddog")