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

def _register_cli(app: Flask) -> None:
    """Регистрирует кастомные CLI-команды."""
    import click

    from app.extensions import db
    from app.models.user import User

    @app.cli.command("create-admin")
    @click.option("--username", default="admin", help="Имя администратора")
    @click.option("--password", default="admin", help="Пароль (смените после первого входа!)")
    def create_admin(username: str, password: str) -> None:
        """
        Создаёт администратора по умолчанию (admin/admin).

        Идемпотентно: если пользователь с таким именем уже есть —
        команда не падает, а сообщает об этом.
        """
        existing = db.session.scalar(db.select(User).where(User.username == username))
        if existing:
            click.echo(f"Пользователь {username!r} уже существует.")
            return

        user = User(username=username, is_admin=True)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        click.echo(f"Администратор {username!r} создан.")

    @app.cli.command("create-user")
    @click.option("--username", required=True, help="Имя пользователя")
    @click.option("--password", required=True, help="Пароль")
    @click.option("--admin/--no-admin", default=False, help="Права администратора")
    def create_user(username: str, password: str, admin: bool) -> None:
        """Создаёт пользователя с указанными параметрами."""
        existing = db.session.scalar(db.select(User).where(User.username == username))
        if existing:
            click.echo(f"Пользователь {username!r} уже существует.", err=True)
            return

        user = User(username=username, is_admin=admin)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        click.echo(f"Пользователь {username!r} создан (admin={admin}).")

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
    _register_cli(app)

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
    """Регистрирует blueprints."""
    from app.routes import auth_bp, categories_bp, locations_bp, main_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    # У categories_bp и locations_bp уже есть свои url_prefix
    app.register_blueprint(categories_bp)
    app.register_blueprint(locations_bp)

