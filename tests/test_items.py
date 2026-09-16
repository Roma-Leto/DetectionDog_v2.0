"""
Тесты роутов предметов: список, создание, редактирование, удаление,
кнопки «Это и ещё» / «И на главную».
"""

from __future__ import annotations

import io

import pytest
from PIL import Image

from app.extensions import db
from app.models.item import Category, Condition, Item
from app.models.location import Box, Location


# ============================================================
# Вспомогательные фикстуры
# ============================================================


@pytest.fixture
def base_refs(db):
    """Создаёт минимальный набор справочников для создания предмета."""
    cat = Category(name="Инструменты")
    cond = Condition(name="б/у")
    loc = Location(name="Кладовая")
    db.session.add_all([cat, cond, loc])
    db.session.commit()
    return {"category": cat, "condition": cond, "location": loc}


def _image_bytes(size=(400, 300)) -> bytes:
    """Готовит маленькое JPEG-изображение для теста."""
    img = Image.new("RGB", size, (180, 200, 220))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


# ============================================================
# Список
# ============================================================


def test_list_items_empty(auth_client, html_text):
    response = auth_client.get("/items/")
    assert response.status_code == 200
    assert "Предметов пока нет" in html_text(response.data)


def test_list_items_shows_item(auth_client, base_refs, html_text):
    item = Item(
        name="Молоток",
        quantity=1,
        category_id=base_refs["category"].id,
        condition_id=base_refs["condition"].id,
        location_id=base_refs["location"].id,
    )
    db.session.add(item)
    db.session.commit()

    response = auth_client.get("/items/")
    assert response.status_code == 200
    assert "Молоток" in html_text(response.data)


def test_list_items_filter_by_category(auth_client, base_refs, html_text):
    """Фильтр по категории показывает только нужные предметы."""
    cat2 = Category(name="Одежда")
    db.session.add(cat2)
    db.session.commit()

    item1 = Item(
        name="Молоток",
        category_id=base_refs["category"].id,
        condition_id=base_refs["condition"].id,
        location_id=base_refs["location"].id,
    )
    item2 = Item(
        name="Футболка",
        category_id=cat2.id,
        condition_id=base_refs["condition"].id,
        location_id=base_refs["location"].id,
    )
    db.session.add_all([item1, item2])
    db.session.commit()

    response = auth_client.get(f"/items/?category={base_refs['category'].id}")
    text = html_text(response.data)
    assert "Молоток" in text
    assert "Футболка" not in text


# ============================================================
# Создание
# ============================================================


def test_create_item_minimal(auth_client, base_refs, db, html_text):
    """Создание предмета без фото."""
    response = auth_client.post(
        "/items/create",
        data={
            "name": "Молоток",
            "description": "Слесарный",
            "quantity": 2,
            "category_id": base_refs["category"].id,
            "condition_id": base_refs["condition"].id,
            "location_id": base_refs["location"].id,
            "box_id": 0,
            "packaging_id": 0,
            "action": "home",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Предмет 'Молоток' сохранён" in html_text(response.data)

    item = db.session.scalar(db.select(Item).where(Item.name == "Молоток"))
    assert item is not None
    assert item.quantity == 2
    assert item.box_id is None
    assert item.packaging_id is None
    assert item.photo_path is None


def test_create_item_with_photo(auth_client, base_refs, db, app, html_text):
    """Создание предмета с фото: файлы появляются на диске."""
    from pathlib import Path

    image_data = _image_bytes()

    response = auth_client.post(
        "/items/create",
        data={
            "name": "С фото",
            "quantity": 1,
            "category_id": base_refs["category"].id,
            "condition_id": base_refs["condition"].id,
            "location_id": base_refs["location"].id,
            "box_id": 0,
            "packaging_id": 0,
            "action": "home",
            "photo": (io.BytesIO(image_data), "photo.jpg"),
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert response.status_code == 200

    item = db.session.scalar(db.select(Item).where(Item.name == "С фото"))
    assert item is not None
    assert item.photo_path is not None
    assert item.photo_thumbnail_path is not None

    upload = Path(app.config["UPLOAD_FOLDER"])
    assert (upload / item.photo_path).exists()
    assert (upload / item.photo_thumbnail_path).exists()

    # Cleanup
    (upload / item.photo_path).unlink()
    (upload / item.photo_thumbnail_path).unlink()


def test_create_item_action_again_redirects_with_from_item(
    auth_client, base_refs, db, html_text
):
    """Кнопка «Это и ещё» редиректит на форму с from_item."""
    response = auth_client.post(
        "/items/create",
        data={
            "name": "Первый",
            "quantity": 1,
            "category_id": base_refs["category"].id,
            "condition_id": base_refs["condition"].id,
            "location_id": base_refs["location"].id,
            "box_id": 0,
            "packaging_id": 0,
            "action": "again",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert "/items/create?from_item=" in response.headers["Location"]

    # После follow_redirects — форма открыта, есть плашка о предзаполнении
    response2 = auth_client.get(response.headers["Location"])
    text2 = html_text(response2.data)
    assert "Предзаполнено из" in text2


def test_create_item_validation_requires_name(auth_client, base_refs, html_text):
    """Без имени форма не проходит валидацию."""
    response = auth_client.post(
        "/items/create",
        data={
            "name": "",
            "quantity": 1,
            "category_id": base_refs["category"].id,
            "condition_id": base_refs["condition"].id,
            "location_id": base_refs["location"].id,
            "box_id": 0,
            "packaging_id": 0,
            "action": "home",
        },
        follow_redirects=True,
    )
    assert "Введите название предмета" in html_text(response.data)


# ============================================================
# Просмотр
# ============================================================


def test_detail_item(auth_client, base_refs, db, html_text):
    item = Item(
        name="Молоток",
        quantity=3,
        category_id=base_refs["category"].id,
        condition_id=base_refs["condition"].id,
        location_id=base_refs["location"].id,
    )
    db.session.add(item)
    db.session.commit()

    response = auth_client.get(f"/items/{item.id}")
    assert response.status_code == 200
    text = html_text(response.data)
    assert "Молоток" in text
    assert "3 шт." in text


def test_detail_deleted_item_shows_restore(auth_client, base_refs, db, html_text):
    """Удалённый предмет открывается и показывает кнопку восстановления."""
    item = Item(
        name="Удалённый",
        category_id=base_refs["category"].id,
        condition_id=base_refs["condition"].id,
        location_id=base_refs["location"].id,
    )
    db.session.add(item)
    db.session.commit()
    item.soft_delete()
    db.session.commit()

    response = auth_client.get(f"/items/{item.id}")
    text = html_text(response.data)
    assert "Предмет удалён" in text
    assert "Восстановить" in text


# ============================================================
# Редактирование
# ============================================================


def test_edit_item(auth_client, base_refs, db, html_text):
    item = Item(
        name="Старое",
        category_id=base_refs["category"].id,
        condition_id=base_refs["condition"].id,
        location_id=base_refs["location"].id,
    )
    db.session.add(item)
    db.session.commit()

    response = auth_client.post(
        f"/items/{item.id}/edit",
        data={
            "name": "Новое",
            "quantity": 5,
            "category_id": base_refs["category"].id,
            "condition_id": base_refs["condition"].id,
            "location_id": base_refs["location"].id,
            "box_id": 0,
            "packaging_id": 0,
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "обновлён" in html_text(response.data)

    db.session.refresh(item)
    assert item.name == "Новое"
    assert item.quantity == 5


# ============================================================
# Удаление и восстановление
# ============================================================


def test_delete_item_soft(auth_client, base_refs, db, html_text):
    item = Item(
        name="Удаляемый",
        category_id=base_refs["category"].id,
        condition_id=base_refs["condition"].id,
        location_id=base_refs["location"].id,
    )
    db.session.add(item)
    db.session.commit()
    item_id = item.id

    response = auth_client.post(
        f"/items/{item_id}/delete",
        follow_redirects=True,
    )
    assert "удалён" in html_text(response.data)

    fetched = db.session.get(Item, item_id)
    assert fetched is not None
    assert fetched.is_deleted is True


def test_restore_item(auth_client, base_refs, db, html_text):
    item = Item(
        name="Восстанавливаемый",
        category_id=base_refs["category"].id,
        condition_id=base_refs["condition"].id,
        location_id=base_refs["location"].id,
    )
    db.session.add(item)
    db.session.commit()
    item.soft_delete()
    db.session.commit()

    response = auth_client.post(
        f"/items/{item.id}/restore",
        follow_redirects=True,
    )
    assert "восстановлен" in html_text(response.data)

    db.session.refresh(item)
    assert item.is_deleted is False