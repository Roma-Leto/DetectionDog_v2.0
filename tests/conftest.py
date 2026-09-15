"""
Фикстуры pytest для DetectionDog v2.0.

Использует отдельную БД detectiondog_test на нетбуке.
Перед каждым тестом схема пересоздаётся: drop_all + create_all.
"""

from __future__ import annotations

import pytest
from flask import Flask

from app import create_app
from app.config import TestingConfig
from app.extensions import db as _db
from app.models.item import Category, Condition
from app.models.location import Box, Location, Packaging
from app.models.user import User


@pytest.fixture(scope="session")
def app() -> Flask:
    """Flask-приложение с тестовой конфигурацией (создаётся раз на сессию)."""
    app = create_app(TestingConfig)
    yield app


@pytest.fixture(scope="function")
def db(app: Flask):
    """Пересоздаёт схему БД перед каждым тестом."""
    with app.app_context():
        _db.drop_all()
        _db.create_all()
        yield _db
        _db.session.remove()


@pytest.fixture
def client(app: Flask, db):
    """Тестовый HTTP-клиент."""
    return app.test_client()


@pytest.fixture
def admin_user(db) -> User:
    """Администратор admin/admin."""
    user = User(username="admin", is_admin=True)
    user.set_password("admin")
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture
def regular_user(db) -> User:
    """Обычный пользователь user/user12345."""
    user = User(username="user", is_admin=False)
    user.set_password("user12345")
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture
def auth_client(client, admin_user):
    """Клиент, авторизованный под admin."""
    response = client.post(
        "/auth/login",
        data={"username": "admin", "password": "admin"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    return client


@pytest.fixture
def sample_category(db) -> Category:
    cat = Category(name="Тестовая категория", description="Для тестов")
    db.session.add(cat)
    db.session.commit()
    return cat


@pytest.fixture
def sample_condition(db) -> Condition:
    cond = Condition(name="б/у", description="Бывший в употреблении")
    db.session.add(cond)
    db.session.commit()
    return cond


@pytest.fixture
def sample_location(db) -> Location:
    loc = Location(name="Кладовая", description="Под замком")
    db.session.add(loc)
    db.session.commit()
    return loc


@pytest.fixture
def sample_box(db, sample_location) -> Box:
    box = Box(name="Коробка №1", location_id=sample_location.id)
    db.session.add(box)
    db.session.commit()
    return box

@pytest.fixture
def html_text():
    """
    Хелпер: извлекает текст из HTML, убирая теги и декодируя сущности.

    Использование:
        assert "Категория 'Одежда' создана" in html_text(response.data)

    Внутри использует html.parser из стандартной библиотеки —
    без внешних зависимостей (bs4, lxml).
    """
    from html.parser import HTMLParser

    class _TextExtractor(HTMLParser):
        def __init__(self):
            super().__init__()
            self.parts: list[str] = []
            self._skip = False

        def handle_starttag(self, tag, attrs):
            # Пропускаем содержимое <script> и <style>
            if tag in ("script", "style"):
                self._skip = True

        def handle_endtag(self, tag):
            if tag in ("script", "style"):
                self._skip = False

        def handle_data(self, data):
            if not self._skip:
                self.parts.append(data)

    def extract(html_bytes: bytes) -> str:
        """Декодирует байты и возвращает «чистый» текст."""
        if isinstance(html_bytes, bytes):
            html_str = html_bytes.decode("utf-8")
        else:
            html_str = html_bytes
        parser = _TextExtractor()
        parser.feed(html_str)
        # Нормализуем пробелы и переносы
        text = "".join(parser.parts)
        return " ".join(text.split())

    return extract