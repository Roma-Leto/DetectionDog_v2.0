"""
Тесты моделей: soft delete, пароли, связи.
"""

from __future__ import annotations

from app.extensions import db
from app.models.item import Category
from app.models.location import Box, Packaging
from app.models.user import User


def test_user_password_hashing(db):
    """Пароль хешируется и проверяется."""
    user = User(username="test")
    user.set_password("secret123")
    db.session.add(user)
    db.session.commit()

    assert user.password_hash != "secret123"
    assert user.check_password("secret123") is True
    assert user.check_password("wrong") is False


def test_soft_delete_category(db):
    """soft_delete помечает запись, но не удаляет из БД."""
    cat = Category(name="Тест")
    db.session.add(cat)
    db.session.commit()
    cat_id = cat.id

    cat.soft_delete()
    db.session.commit()

    fetched = db.session.get(Category, cat_id)
    assert fetched is not None
    assert fetched.is_deleted is True
    assert fetched.deleted_at is not None

    active = db.session.scalars(
        db.select(Category).where(Category.is_deleted.is_(False))
    ).all()
    assert cat_id not in [c.id for c in active]


def test_soft_delete_restore(db):
    """restore отменяет мягкое удаление."""
    cat = Category(name="Тест")
    db.session.add(cat)
    db.session.commit()

    cat.soft_delete()
    db.session.commit()
    assert cat.is_deleted is True

    cat.restore()
    db.session.commit()
    assert cat.is_deleted is False
    assert cat.deleted_at is None


def test_box_requires_location(db, sample_location):
    """Бокс привязан к локации через FK."""
    box = Box(name="Коробка", location_id=sample_location.id)
    db.session.add(box)
    db.session.commit()

    assert box.location.id == sample_location.id
    assert box.location.name == "Кладовая"


def test_packaging_standalone(db):
    """Упаковка не привязана к локациям."""
    pack = Packaging(name="Плёнка")
    db.session.add(pack)
    db.session.commit()

    assert pack.id is not None
    assert pack.name == "Плёнка"