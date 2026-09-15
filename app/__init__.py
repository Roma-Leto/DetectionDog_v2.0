"""
Фабрика Flask-приложения DetectionDog v2.0.

create_app() — единственная точка входа. Она:
1. Создаёт Flask-приложение.
2. Загружает конфигурацию.
3. Инициализирует расширения (db, login, csrf, migrate).
4. Регистрирует blueprints (маршруты).
"""

from __future__ import annotations

from flask import Flask

from app.config import get_config
from app.extensions import csrf, db, login_manager, migrate


def create_app(config_class=None) -> Flask:
    """
    Создаёт и настраивает экземпляр Flask-приложения.

    :param config_class: явный класс конфигурации (для тестов).
                         Если None — выбирается по FLASK_ENV.
    """
    app = Flask(__name__, instance_relative_config=False)

    if config_class is None:
        config_class = get_config()
    app.config.from_object(config_class)

    _init_extensions(app)
    _register_blueprints(app)

    return app


def _init_extensions(app: Flask) -> None:
    """Привязывает расширения к приложению."""
    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    login_manager.init_app(app)

    # Импортируем модели, чтобы SQLAlchemy их «увидел»
    # до первой миграции.
    with app.app_context():
        from app import models  # noqa: F401


def _register_blueprints(app: Flask) -> None:
    """
    Регистрирует blueprints. Пока — пусто, наполним на этапах 2-3.
    """
    # Пример для будущего:
    # from app.routes.main import main_bp
    # app.register_blueprint(main_bp)
    pass