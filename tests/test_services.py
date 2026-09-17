"""
Тесты сервисов: image_service, vision_client.

Важно: на Windows нельзя удалить файл, пока он открыт через Image.open.
Поэтому все проверки размеров оборачиваем в `with Image.open(...) as img:`,
чтобы хэндл закрывался до unlink().
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from PIL import Image
from werkzeug.datastructures import FileStorage

from app.services import (
    ImageProcessingError,
    VisionClient,
    delete_item_images,
    process_and_save_image,
)


# ============================================================
# Вспомогательные функции
# ============================================================


def _make_image_bytes(
    width: int = 3000,
    height: int = 2000,
    fmt: str = "JPEG",
    mode: str = "RGB",
) -> bytes:
    """Создаёт тестовое изображение и возвращает его байты."""
    if mode == "RGBA":
        img = Image.new("RGBA", (width, height), (255, 0, 0, 128))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    img = Image.new("RGB", (width, height), (200, 220, 240))
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


def _wrap_filestorage(data: bytes, filename: str = "test.jpg") -> FileStorage:
    """Оборачивает байты в FileStorage, как это делает Flask."""
    return FileStorage(stream=io.BytesIO(data), filename=filename)


def _cleanup_files(*paths: Path) -> None:
    """
    Безопасно удаляет файлы. Пропускает отсутствующие.
    Не падает, если файл занят (маловероятно после `with Image.open`).
    """
    for p in paths:
        try:
            if p.exists():
                p.unlink()
        except OSError:
            pass


# ============================================================
# image_service: process_and_save_image
# ============================================================


def test_process_saves_photo_and_thumbnail(app):
    """process_and_save_image сохраняет два файла и корректно сжимает."""
    data = _make_image_bytes(3000, 2000, "JPEG")
    fs = _wrap_filestorage(data, "test.jpg")

    with app.app_context():
        photo_rel, thumb_rel = process_and_save_image(fs)

        assert photo_rel.startswith("photos/")
        assert photo_rel.endswith(".jpg")
        assert thumb_rel.startswith("thumbnails/")
        assert thumb_rel.endswith(".jpg")

        upload_folder = Path(app.config["UPLOAD_FOLDER"])
        photo_abs = upload_folder / photo_rel
        thumb_abs = upload_folder / thumb_rel

        try:
            assert photo_abs.exists()
            assert thumb_abs.exists()

            # Проверяем размеры внутри `with` — хэндл закроется после блока
            with Image.open(photo_abs) as photo:
                assert max(photo.size) <= 1920
                assert photo.format == "JPEG"

            with Image.open(thumb_abs) as thumb:
                assert max(thumb.size) <= 300
                assert thumb.format == "JPEG"
        finally:
            _cleanup_files(photo_abs, thumb_abs)


def test_process_keeps_small_image_size(app):
    """Маленькое фото не апскейлится."""
    data = _make_image_bytes(400, 300, "JPEG")
    fs = _wrap_filestorage(data, "small.jpg")

    with app.app_context():
        photo_rel, thumb_rel = process_and_save_image(fs)
        upload_folder = Path(app.config["UPLOAD_FOLDER"])
        photo_abs = upload_folder / photo_rel
        thumb_abs = upload_folder / thumb_rel

        try:
            with Image.open(photo_abs) as photo:
                assert photo.size == (400, 300)
        finally:
            _cleanup_files(photo_abs, thumb_abs)


def test_process_converts_rgba_to_rgb(app):
    """PNG с альфа-каналом конвертируется в RGB без ошибок."""
    data = _make_image_bytes(500, 500, "PNG", mode="RGBA")
    fs = _wrap_filestorage(data, "rgba.png")

    with app.app_context():
        photo_rel, thumb_rel = process_and_save_image(fs)
        upload_folder = Path(app.config["UPLOAD_FOLDER"])
        photo_abs = upload_folder / photo_rel
        thumb_abs = upload_folder / thumb_rel

        try:
            with Image.open(photo_abs) as photo:
                assert photo.mode == "RGB"
        finally:
            _cleanup_files(photo_abs, thumb_abs)


def test_process_rejects_non_image(app):
    """Не-изображение вызывает ImageProcessingError."""
    fake_data = b"this is not an image, just text"
    fs = _wrap_filestorage(fake_data, "fake.jpg")

    with app.app_context():
        with pytest.raises(ImageProcessingError):
            process_and_save_image(fs)


def test_process_rejects_empty_file(app):
    """Пустой файл вызывает ImageProcessingError."""
    fs = _wrap_filestorage(b"", "empty.jpg")

    with app.app_context():
        with pytest.raises(ImageProcessingError):
            process_and_save_image(fs)


def test_delete_item_images_removes_files(app):
    """delete_item_images удаляет файлы, не падает на None/отсутствующих."""
    data = _make_image_bytes(500, 500, "JPEG")
    fs = _wrap_filestorage(data)

    with app.app_context():
        photo_rel, thumb_rel = process_and_save_image(fs)
        upload = Path(app.config["UPLOAD_FOLDER"])
        photo_abs = upload / photo_rel
        thumb_abs = upload / thumb_rel

        assert photo_abs.exists()
        assert thumb_abs.exists()

        delete_item_images(photo_rel, thumb_rel)

        assert not photo_abs.exists()
        assert not thumb_abs.exists()

        # Повторный вызов не падает
        delete_item_images(photo_rel, thumb_rel)
        delete_item_images(None, None)


# ============================================================
# vision_client
# ============================================================


def test_vision_client_unavailable_returns_false():
    """Недоступный сервис — is_available() == False, analyze == None."""
    client = VisionClient(
        base_url="http://127.0.0.1:1",  # порт 1 заведомо закрыт
        health_timeout=1,
        analyze_timeout=1,
    )
    assert client.is_available() is False
    assert client.analyze_image(b"fake") is None


def test_vision_client_parse_result_handles_missing_fields():
    """_parse_result устойчив к пустому словарю."""
    result = VisionClient._parse_result({})
    assert result.title is None
    assert result.description is None
    assert result.category_hint is None
    assert result.condition_hint is None
    assert result.quantity == 1
    assert result.confidence == 0.0
    assert result.is_empty() is True


def test_vision_client_parse_result_handles_wrong_types():
    """_parse_result не падает на мусорных типах."""
    result = VisionClient._parse_result(
        {
            "title": "  Test Item  ",
            "description": "",
            "quantity": "abc",
            "confidence": "not-a-float",
        }
    )
    assert result.title == "Test Item"
    assert result.description is None
    assert result.quantity == 1
    assert result.confidence == 0.0


def test_vision_client_parse_result_clamps_confidence():
    """confidence обрезается до 0..1."""
    r1 = VisionClient._parse_result({"confidence": 1.5})
    assert r1.confidence == 1.0

    r2 = VisionClient._parse_result({"confidence": -0.5})
    assert r2.confidence == 0.0




# ============================================================
# stats_service
# ============================================================


def test_stats_empty_db(app, db):
    """Пустая БД — нули во всех полях, None в экстремумах."""
    from app.services import get_dashboard_stats

    with app.app_context():
        stats = get_dashboard_stats()

        assert stats.total_items == 0
        assert stats.active_items == 0
        assert stats.deleted_items == 0
        assert stats.total_quantity_active == 0
        assert stats.by_category == []
        assert stats.by_location == []
        assert stats.oldest_active is None
        assert stats.latest_added is None
        assert stats.latest_deleted is None


def test_stats_counts(app, db):
    """Проверяет счётчики: total, active, deleted, quantity."""
    from app.extensions import db as _db
    from app.models.item import Category, Condition, Item
    from app.models.location import Location
    from app.services import get_dashboard_stats

    with app.app_context():
        cat = Category(name="Инструменты")
        cond = Condition(name="б/у")
        loc = Location(name="Кладовая")
        _db.session.add_all([cat, cond, loc])
        _db.session.commit()

        # 3 активных (сумма quantity = 5) + 1 удалённый (qty=1)
        items = [
            Item(name="A", quantity=1, category_id=cat.id, condition_id=cond.id, location_id=loc.id),
            Item(name="B", quantity=2, category_id=cat.id, condition_id=cond.id, location_id=loc.id),
            Item(name="C", quantity=2, category_id=cat.id, condition_id=cond.id, location_id=loc.id),
            Item(name="D", quantity=1, category_id=cat.id, condition_id=cond.id, location_id=loc.id),
        ]
        _db.session.add_all(items)
        _db.session.commit()
        items[3].soft_delete()
        _db.session.commit()

        stats = get_dashboard_stats()

        assert stats.total_items == 4
        assert stats.active_items == 3
        assert stats.deleted_items == 1
        assert stats.total_quantity_active == 5  # 1+2+2, без удалённого

        # Агрегация по категориям: теперь (id, name, count)
        assert stats.by_category == [(cat.id, "Инструменты", 3)]
        # Агрегация по локациям: теперь (id, name, count)
        assert stats.by_location == [(loc.id, "Кладовая", 3)]


def test_stats_extremes(app, db):
    """oldest_active, latest_added, latest_deleted."""
    from datetime import datetime, timedelta
    from app.extensions import db as _db
    from app.models.item import Category, Condition, Item
    from app.models.location import Location
    from app.services import get_dashboard_stats

    with app.app_context():
        cat = Category(name="C")
        cond = Condition(name="б/у")
        loc = Location(name="L")
        _db.session.add_all([cat, cond, loc])
        _db.session.commit()

        now = datetime.now()

        # Три предмета с разными created_at (переопределяем вручную)
        item_old = Item(
            name="Старый", category_id=cat.id, condition_id=cond.id, location_id=loc.id
        )
        item_new = Item(
            name="Новый", category_id=cat.id, condition_id=cond.id, location_id=loc.id
        )
        _db.session.add_all([item_old, item_new])
        _db.session.commit()

        item_old.created_at = now - timedelta(days=10)
        item_new.created_at = now
        _db.session.commit()

        # Удалённый
        item_del = Item(
            name="Удалённый", category_id=cat.id, condition_id=cond.id, location_id=loc.id
        )
        _db.session.add(item_del)
        _db.session.commit()
        item_del.soft_delete()
        _db.session.commit()

        stats = get_dashboard_stats()

        assert stats.oldest_active.name == "Старый"
        assert stats.latest_added.name == "Новый"
        assert stats.latest_deleted.name == "Удалённый"


# ============================================================
# search_service
# ============================================================


def _make_item(db_module, name: str, **kwargs):
    """Хелпер: создаёт предмет с минимальными FK."""
    from app.models.item import Item

    item = Item(name=name, **kwargs)
    db_module.session.add(item)
    db_module.session.commit()
    return item


def test_quick_search_by_name(app, db):
    """Быстрый поиск по подстроке в имени."""
    from app.extensions import db as _db
    from app.models.item import Category, Condition, Item
    from app.models.location import Location
    from app.services import quick_search

    with app.app_context():
        cat = Category(name="Инструменты")
        cond = Condition(name="б/у")
        loc = Location(name="Кладовая")
        _db.session.add_all([cat, cond, loc])
        _db.session.commit()

        _db.session.add_all([
            Item(name="Молоток", category_id=cat.id, condition_id=cond.id, location_id=loc.id),
            Item(name="Отвёртка", category_id=cat.id, condition_id=cond.id, location_id=loc.id),
            Item(name="Молоток-гвоздодёр", category_id=cat.id, condition_id=cond.id, location_id=loc.id),
        ])
        _db.session.commit()

        results = _db.session.scalars(quick_search("молот")).all()
        assert len(results) == 2
        names = {r.name for r in results}
        assert names == {"Молоток", "Молоток-гвоздодёр"}


def test_quick_search_empty_returns_all(app, db):
    """Пустой запрос возвращает все активные."""
    from app.extensions import db as _db
    from app.models.item import Category, Condition, Item
    from app.models.location import Location
    from app.services import quick_search

    with app.app_context():
        cat = Category(name="C")
        cond = Condition(name="б/у")
        loc = Location(name="L")
        _db.session.add_all([cat, cond, loc])
        _db.session.commit()

        _db.session.add_all([
            Item(name="A", category_id=cat.id, condition_id=cond.id, location_id=loc.id),
            Item(name="B", category_id=cat.id, condition_id=cond.id, location_id=loc.id),
        ])
        _db.session.commit()

        results = _db.session.scalars(quick_search("")).all()
        assert len(results) == 2


def test_advanced_search_filters(app, db):
    """Расширенный поиск: фильтр по категории и наличию фото."""
    from app.extensions import db as _db
    from app.models.item import Category, Condition, Item
    from app.models.location import Location
    from app.services import advanced_search

    with app.app_context():
        cat1 = Category(name="Инструменты")
        cat2 = Category(name="Одежда")
        cond = Condition(name="б/у")
        loc = Location(name="L")
        _db.session.add_all([cat1, cat2, cond, loc])
        _db.session.commit()

        _db.session.add_all([
            Item(name="Молоток", category_id=cat1.id, condition_id=cond.id, location_id=loc.id),
            Item(name="Отвёртка", category_id=cat1.id, condition_id=cond.id, location_id=loc.id),
            Item(name="Футболка", category_id=cat2.id, condition_id=cond.id, location_id=loc.id),
        ])
        _db.session.commit()

        results = _db.session.scalars(
            advanced_search(category_id=cat1.id)
        ).all()
        assert len(results) == 2
        assert {r.name for r in results} == {"Молоток", "Отвёртка"}


def test_random_item_returns_one_or_none(app, db):
    """random_item: None при пустой БД, предмет при наличии."""
    from app.extensions import db as _db
    from app.models.item import Category, Condition, Item
    from app.models.location import Location
    from app.services import random_item

    with app.app_context():
        # Пусто
        assert random_item() is None

        cat = Category(name="C")
        cond = Condition(name="б/у")
        loc = Location(name="L")
        _db.session.add_all([cat, cond, loc])
        _db.session.commit()

        _db.session.add(
            Item(name="Единственный", category_id=cat.id, condition_id=cond.id, location_id=loc.id)
        )
        _db.session.commit()

        item = random_item()
        assert item is not None
        assert item.name == "Единственный"