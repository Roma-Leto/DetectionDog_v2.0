"""
Тесты HTTP-маршрутов: аутентификация, CRUD, права доступа.

Все проверки текста идут через фикстуру `html_text`, которая
парсит HTML и декодирует сущности (&#39; -> '). Это важно, потому
что Jinja2 экранирует апострофы в flash-сообщениях.
"""

from __future__ import annotations

from app.extensions import db
from app.models.item import Category, Condition
from app.models.location import Location


# ============================================================
# Аутентификация
# ============================================================


def test_login_page_available(client, html_text):
    """Форма входа доступна анонимному пользователю."""
    response = client.get("/auth/login")
    assert response.status_code == 200
    assert "Вход в систему" in html_text(response.data)


def test_dashboard_requires_login(client):
    """Главная страница требует входа — редирект на /auth/login."""
    response = client.get("/")
    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]


def test_login_with_valid_credentials(client, admin_user, html_text):
    """Вход с правильными данными."""
    response = client.post(
        "/auth/login",
        data={"username": "admin", "password": "admin"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Главная" in html_text(response.data)


def test_login_with_invalid_credentials(client, admin_user, html_text):
    """Вход с неправильным паролем не пускает."""
    response = client.post(
        "/auth/login",
        data={"username": "admin", "password": "wrong"},
        follow_redirects=True,
    )
    assert "Неверное имя пользователя" in html_text(response.data)


def test_regular_user_cannot_access_users_list(client, regular_user, html_text):
    """Обычный пользователь не видит раздел 'Пользователи'."""
    client.post(
        "/auth/login",
        data={"username": "user", "password": "user12345"},
    )
    response = client.get("/auth/users", follow_redirects=True)
    assert "Доступ только для администратора" in html_text(response.data)


# ============================================================
# CRUD категорий
# ============================================================


def test_list_categories_empty(auth_client, html_text):
    """Пустой список категорий."""
    response = auth_client.get("/categories/")
    assert response.status_code == 200
    assert "Категорий пока нет" in html_text(response.data)


def test_create_category(auth_client, db, html_text):
    """Создание категории через POST."""
    response = auth_client.post(
        "/categories/create",
        data={"name": "Одежда", "description": "Футболки и рубашки"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Категория 'Одежда' создана" in html_text(response.data)

    cat = db.session.scalar(db.select(Category).where(Category.name == "Одежда"))
    assert cat is not None
    assert cat.description == "Футболки и рубашки"


def test_create_category_duplicate(auth_client, sample_category, html_text):
    """Дубликат по имени не создаётся."""
    response = auth_client.post(
        "/categories/create",
        data={"name": "Тестовая категория", "description": "Другое"},
        follow_redirects=True,
    )
    assert "уже существует" in html_text(response.data)


def test_edit_category(auth_client, sample_category, db, html_text):
    """Редактирование категории."""
    response = auth_client.post(
        f"/categories/{sample_category.id}/edit",
        data={"name": "Изменённая", "description": "Новое описание"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "обновлена" in html_text(response.data)

    db.session.refresh(sample_category)
    assert sample_category.name == "Изменённая"
    assert sample_category.description == "Новое описание"


def test_delete_category_soft(auth_client, sample_category, db, html_text):
    """Удаление категории — мягкое, запись остаётся в БД."""
    cat_id = sample_category.id
    response = auth_client.post(
        f"/categories/{cat_id}/delete",
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "удалена" in html_text(response.data)

    # Запись в БД, но is_deleted=True
    fetched = db.session.get(Category, cat_id)
    assert fetched is not None
    assert fetched.is_deleted is True


# ============================================================
# CRUD локаций
# ============================================================


def test_create_location(auth_client, db, html_text):
    """Создание локации."""
    response = auth_client.post(
        "/locations/create",
        data={"name": "Кладовая", "description": "Под замком"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Локация 'Кладовая' создана" in html_text(response.data)

    loc = db.session.scalar(db.select(Location).where(Location.name == "Кладовая"))
    assert loc is not None
    assert loc.description == "Под замком"


def test_delete_location_with_box_blocked(auth_client, sample_box, db, html_text):
    """Нельзя удалить локацию, если в ней есть активные боксы."""
    loc_id = sample_box.location_id
    response = auth_client.post(
        f"/locations/{loc_id}/delete",
        follow_redirects=True,
    )
    assert "Нельзя удалить локацию" in html_text(response.data)

    # Локация НЕ удалена
    loc = db.session.get(Location, loc_id)
    assert loc.is_deleted is False


# ============================================================
# CRUD состояний
# ============================================================


def test_create_condition(auth_client, db, html_text):
    """Создание состояния."""
    response = auth_client.post(
        "/categories/conditions/create",
        data={"name": "сломанный", "description": "Требует ремонта"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Состояние 'сломанный' создано" in html_text(response.data)

    cond = db.session.scalar(
        db.select(Condition).where(Condition.name == "сломанный")
    )
    assert cond is not None
    assert cond.description == "Требует ремонта"