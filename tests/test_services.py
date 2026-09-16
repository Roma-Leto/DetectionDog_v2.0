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