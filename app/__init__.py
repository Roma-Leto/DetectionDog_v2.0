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

    @app.cli.command("seed")
    @click.option(
        "--reset",
        is_flag=True,
        help="Удалить предустановленные данные и создать заново. "
             "Осторожно: удалит все категории и состояния, "
             "на которые не ссылаются предметы.",
    )
    def seed(reset: bool) -> None:
        """
        Заполняет БД предустановленными категориями и состояниями.

        Идемпотентно: если категория уже существует по имени —
        пропускается. С флагом --reset предустановленные записи
        сначала помечаются как удалённые, потом создаются заново.
        """
        from app.models.item import Category, Condition
        from app.seed_data import DEFAULT_CATEGORIES, DEFAULT_CONDITIONS

        if reset:
            # Мягко удаляем только те категории и состояния,
            # которые совпадают по имени с предустановленными.
            preset_cat_names = [name for name, _ in DEFAULT_CATEGORIES]
            preset_cond_names = [name for name, _ in DEFAULT_CONDITIONS]

            cats_to_reset = db.session.scalars(
                db.select(Category).where(
                    Category.name.in_(preset_cat_names),
                    Category.is_deleted.is_(False),
                )
            ).all()
            conds_to_reset = db.session.scalars(
                db.select(Condition).where(
                    Condition.name.in_(preset_cond_names),
                    Condition.is_deleted.is_(False),
                )
            ).all()

            # Проверяем, что на них не ссылаются предметы.
            # Фильтруем в отдельный список — нельзя удалять
            # элементы из списка во время итерации по нему.
            from app.models.item import Item

            cats_to_reset_filtered = []
            for cat in cats_to_reset:
                count = db.session.scalar(
                    db.select(db.func.count(Item.id)).where(
                        Item.category_id == cat.id,
                        Item.is_deleted.is_(False),
                    )
                )
                if count > 0:
                    click.echo(
                        f"  ⚠ Категория {cat.name!r} используется "
                        f"в {count} предмет(ах) — пропускаю.",
                        err=True,
                    )
                else:
                    cats_to_reset_filtered.append(cat)

            conds_to_reset_filtered = []
            for cond in conds_to_reset:
                count = db.session.scalar(
                    db.select(db.func.count(Item.id)).where(
                        Item.condition_id == cond.id,
                        Item.is_deleted.is_(False),
                    )
                )
                if count > 0:
                    click.echo(
                        f"  ⚠ Состояние {cond.name!r} используется "
                        f"в {count} предмет(ах) — пропускаю.",
                        err=True,
                    )
                else:
                    conds_to_reset_filtered.append(cond)

            for cat in cats_to_reset_filtered:
                cat.soft_delete()
            for cond in conds_to_reset_filtered:
                cond.soft_delete()
            db.session.commit()
            click.echo(
                f"Помечено как удалённые: "
                f"{len(cats_to_reset_filtered)} категорий, "
                f"{len(conds_to_reset_filtered)} состояний."
            )

        # --- Категории ---
        created_cats = 0
        for name, description in DEFAULT_CATEGORIES:
            existing = db.session.scalar(
                db.select(Category).where(
                    Category.name == name,
                    Category.is_deleted.is_(False),
                )
            )
            if existing:
                continue
            db.session.add(Category(name=name, description=description))
            created_cats += 1

        # --- Состояния ---
        created_conds = 0
        for name, description in DEFAULT_CONDITIONS:
            existing = db.session.scalar(
                db.select(Condition).where(
                    Condition.name == name,
                    Condition.is_deleted.is_(False),
                )
            )
            if existing:
                continue
            db.session.add(Condition(name=name, description=description))
            created_conds += 1

        db.session.commit()
        click.echo(
            f"Создано: {created_cats} категорий, {created_conds} состояний."
        )
        if created_cats == 0 and created_conds == 0:
            click.echo("Все предустановленные данные уже в базе.")

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
    from app.routes import (
        auth_bp,
        categories_bp,
        items_bp,
        locations_bp,
        main_bp,
        settings_bp,
    )

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(categories_bp)
    app.register_blueprint(locations_bp)
    app.register_blueprint(items_bp)
    app.register_blueprint(settings_bp)

