"""
Пакет blueprints (маршрутов).

Каждый модуль экспортирует один blueprint-объект.
Регистрация происходит в app/__init__.py.
"""

from app.routes.auth import auth_bp
from app.routes.categories import categories_bp
from app.routes.items import items_bp
from app.routes.locations import locations_bp
from app.routes.main import main_bp
from app.routes.secnot import secnot_bp
from app.routes.settings import settings_bp

__all__ = [
    "auth_bp",
    "categories_bp",
    "items_bp",
    "locations_bp",
    "main_bp",
    "secnot_bp",
    "settings_bp",
]