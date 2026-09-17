"""
WSGI-обёртка для продакшена.

Оборачивает Flask-приложение в DispatcherMiddleware, чтобы оно
могло работать по префиксу /ddog/.

Запуск в Gunicorn:
    gunicorn --bind 127.0.0.1:8000 wsgi:application

Flask внутри считает, что приложение живёт в /ddog/:
- url_for('main.dashboard') → /ddog/
- url_for('auth.login')    → /ddog/auth/login
- статика → /ddog/static/...
"""

from __future__ import annotations

from werkzeug.middleware.dispatcher import DispatcherMiddleware
from werkzeug.wrappers import Response

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
        # Проверяем, что запрос начинается с нашего префикса
        path = environ.get("PATH_INFO", "")
        if not path.startswith(self.prefix):
            return Response("Not Found", status=404)(environ, start_response)

        # Обрезаем префикс из PATH_INFO и добавляем в SCRIPT_NAME
        environ["SCRIPT_NAME"] = self.prefix
        environ["PATH_INFO"] = path[len(self.prefix):] or "/"

        return self.app(environ, start_response)


flask_app = create_app()
application = PrefixMiddleware(flask_app, "/ddog"))