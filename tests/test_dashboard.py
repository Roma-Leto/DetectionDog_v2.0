"""
Тесты дашборда, быстрого поиска, «Мне повезёт!» и расширенного поиска.
"""

from __future__ import annotations

import pytest

from app.extensions import db
from app.models.item import Category, Condition, Item
from app.models.location import Location


@pytest.fixture
def seeded_db(db):
    """Создаёт справочники и несколько предметов для тестов дашборда."""
    cat = Category(name="Инструменты")
    cond = Condition(name="б/у")
    loc = Location(name="Кладовая")
    db.session.add_all([cat, cond, loc])
    db.session.commit()

    items = [
        Item(name="Молоток", quantity=1, category_id=cat.id, condition_id=cond.id, location_id=loc.id),
        Item(name="Отвёртка", quantity=3, category_id=cat.id, condition_id=cond.id, location_id=loc.id),
        Item(name="Футболка", quantity=2, category_id=cat.id, condition_id=cond.id, location_id=loc.id),
    ]
    db.session.add_all(items)
    db.session.commit()
    return {"cat": cat, "cond": cond, "loc": loc, "items": items}


# ============================================================
# Дашборд
# ============================================================


def test_dashboard_requires_login(client):
    """Дашборд требует входа."""
    response = client.get("/")
    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]


def test_dashboard_empty(auth_client, html_text):
    """Пустой дашборд отображается без ошибок."""
    response = auth_client.get("/")
    assert response.status_code == 200
    text = html_text(response.data)
    assert "DetectionDog" in text
    assert "В наличии" in text
    assert "Мне повезёт!" in text


def test_dashboard_shows_stats(auth_client, seeded_db, html_text):
    """Дашборд показывает правильные числа."""
    response = auth_client.get("/")
    text = html_text(response.data)

    # Всего активных: 3
    assert "3" in text
    # Сумма quantity: 1 + 3 + 2 = 6
    assert "6" in text
    # Категория и локация
    assert "Инструменты" in text
    assert "Кладовая" in text
    # Самые старые/новые
    assert "Молоток" in text or "Отвёртка" in text or "Футболка" in text


# ============================================================
# Быстрый поиск
# ============================================================


def test_quick_search_finds_item(auth_client, seeded_db, html_text):
    """?q=молот находит Молоток."""
    response = auth_client.get("/quick-search?q=молот")
    assert response.status_code == 200
    text = html_text(response.data)
    assert "Молоток" in text
    # Не должно быть Отвёртки и Футболки
    assert "Отвёртка" not in text
    assert "Футболка" not in text


def test_quick_search_empty_shows_all(auth_client, seeded_db, html_text):
    """Пустой q показывает все активные."""
    response = auth_client.get("/quick-search?q=")
    text = html_text(response.data)
    assert "Молоток" in text
    assert "Отвёртка" in text
    assert "Футболка" in text


def test_quick_search_no_results(auth_client, seeded_db, html_text):
    """Несуществующий запрос даёт «Ничего не найдено»."""
    response = auth_client.get("/quick-search?q=несуществующий_xyz")
    text = html_text(response.data)
    assert "Ничего не найдено" in text


# ============================================================
# «Мне повезёт!»
# ============================================================


def test_lucky_redirects_to_item(auth_client, seeded_db):
    """«Мне повезёт!» редиректит на карточку предмета."""
    response = auth_client.get("/lucky")
    assert response.status_code == 302
    assert "/items/" in response.headers["Location"]

    # Проверяем, что открывается карточка
    response2 = auth_client.get(response.headers["Location"])
    assert response2.status_code == 200


def test_lucky_empty_db(auth_client, html_text):
    """При пустой БД — flash и редирект на дашборд."""
    response = auth_client.get("/lucky", follow_redirects=True)
    assert response.status_code == 200
    text = html_text(response.data)
    assert "В базе пока нет предметов" in text


# ============================================================
# Расширенный поиск
# ============================================================


def test_search_empty_form(auth_client, seeded_db, html_text):
    """/search без фильтров показывает все."""
    response = auth_client.get("/search")
    assert response.status_code == 200
    text = html_text(response.data)
    assert "Найдено:" in text
    assert "Молоток" in text
    assert "Отвёртка" in text


def test_search_by_category(auth_client, seeded_db, html_text):
    """/search?category_id=<id> фильтрует по категории."""
    cat_id = seeded_db["cat"].id
    response = auth_client.get(f"/search?category_id={cat_id}")
    text = html_text(response.data)
    assert "Молоток" in text
    assert "Отвёртка" in text


def test_search_by_query(auth_client, seeded_db, html_text):
    """/search?q=отвёрт находит Отвёртку."""
    response = auth_client.get("/search?q=отвёрт")
    text = html_text(response.data)
    assert "Отвёртка" in text
    assert "Молоток" not in text


def test_search_has_photo_filter(auth_client, seeded_db, html_text):
    """Фильтр «только с фото» отсекает предметы без photo_path."""
    response = auth_client.get("/search?has_photo=y")
    text = html_text(response.data)
    # У наших предметов нет фото — «Ничего не найдено»
    assert "Ничего не найдено" in text