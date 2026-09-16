"""
Сервис обработки изображений предметов.

Функции:
- process_and_save_image: сжатие + thumbnail + сохранение на диск
- delete_item_images: удаление файлов при удалении предмета

Формат: JPEG, quality=85, max dimension=1920px.
Thumbnail: 300px по длинной стороне, quality=80.

Этого достаточно для читаемости текста высотой 2 см на фото
(надписи на коробках, маркировка инструментов).
"""

from __future__ import annotations

import io
import secrets
from datetime import datetime
from pathlib import Path

from flask import current_app
from PIL import Image, ImageOps, UnidentifiedImageError

# ============================================================
# Исключения
# ============================================================


class ImageProcessingError(Exception):
    """Ошибка обработки изображения (неверный формат, повреждённый файл)."""


# ============================================================
# Публичные функции
# ============================================================


def process_and_save_image(file_storage) -> tuple[str, str]:
    """
    Обрабатывает загруженное изображение: сжимает, создаёт thumbnail,
    сохраняет оба файла на диск.

    :param file_storage: werkzeug.datastructures.FileStorage (из формы)
    :return: (photo_path, thumbnail_path) — относительные пути от UPLOAD_FOLDER.
             Например: ("photos/2026/09/abc123.jpg", "thumbnails/2026/09/abc123.jpg")
    :raises ImageProcessingError: если файл не является изображением.
    """
    # Читаем файл в память
    try:
        file_storage.seek(0)
        data = file_storage.read()
    except Exception as e:
        raise ImageProcessingError(f"Не удалось прочитать файл: {e}") from e

    if not data:
        raise ImageProcessingError("Файл пуст.")

    # Открываем через Pillow
    try:
        img = Image.open(io.BytesIO(data))
        img.load()  # форсируем декодирование, чтобы поймать повреждённые файлы
    except UnidentifiedImageError as e:
        raise ImageProcessingError(
            "Файл не является изображением или формат не поддерживается."
        ) from e
    except Exception as e:
        raise ImageProcessingError(f"Ошибка открытия изображения: {e}") from e

    # Применяем EXIF-поворот (фото со смартфона часто повёрнуты)
    img = ImageOps.exif_transpose(img)

    # Конвертируем в RGB (для JPEG: PNG с альфа-каналом, HEIC и пр.)
    if img.mode != "RGB":
        # Если есть альфа-канал — накладываем на белый фон
        if img.mode in ("RGBA", "LA", "P"):
            background = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode == "P":
                img = img.convert("RGBA")
            background.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
            img = background
        else:
            img = img.convert("RGB")

    # Готовим пути
    photo_rel, thumb_rel, photo_abs, thumb_abs = _generate_paths()
    photo_abs.parent.mkdir(parents=True, exist_ok=True)
    thumb_abs.parent.mkdir(parents=True, exist_ok=True)

    # --- Основное фото ---
    max_dim = current_app.config["IMAGE_MAX_DIMENSION"]
    quality = current_app.config["IMAGE_JPEG_QUALITY"]

    main_img = img.copy()
    main_img.thumbnail((max_dim, max_dim), Image.LANCZOS)
    main_img.save(
        photo_abs,
        format="JPEG",
        quality=quality,
        optimize=True,
        progressive=True,
    )

    # --- Thumbnail ---
    thumb_size = current_app.config["THUMBNAIL_SIZE"]
    thumb_img = img.copy()
    thumb_img.thumbnail((thumb_size, thumb_size), Image.LANCZOS)
    thumb_img.save(
        thumb_abs,
        format="JPEG",
        quality=80,
        optimize=True,
    )

    return photo_rel, thumb_rel


def delete_item_images(photo_path: str | None, thumb_path: str | None) -> None:
    """
    Удаляет файлы изображений с диска.

    Не падает, если файл уже удалён или путь None.
    Используется при физическом удалении предмета из БД.
    При soft delete файлы НЕ удаляются.
    """
    upload_folder = Path(current_app.config["UPLOAD_FOLDER"])

    for rel_path in (photo_path, thumb_path):
        if not rel_path:
            continue
        abs_path = upload_folder / rel_path
        try:
            if abs_path.exists():
                abs_path.unlink()
        except OSError as e:
            # Логируем, но не падаем — файл могут удалить вручную
            current_app.logger.warning(f"Не удалось удалить {abs_path}: {e}")


# ============================================================
# Приватные функции
# ============================================================


def _generate_paths() -> tuple[str, str, Path, Path]:
    """
    Генерирует уникальные относительные и абсолютные пути для фото.

    Структура: photos/YYYY/MM/<token>.jpg
    Разбивка по годам/месяцам — чтобы не было папок с 100 000 файлов.

    :return: (photo_rel, thumb_rel, photo_abs, thumb_abs)
    """
    upload_folder = Path(current_app.config["UPLOAD_FOLDER"])
    now = datetime.now()

    # Уникальный токен — 16 hex-символов (достаточно, чтобы не пересечься)
    token = secrets.token_hex(8)
    filename = f"{token}.jpg"

    photo_rel = f"photos/{now:%Y}/{now:%m}/{filename}"
    thumb_rel = f"thumbnails/{now:%Y}/{now:%m}/{filename}"

    photo_abs = upload_folder / photo_rel
    thumb_abs = upload_folder / thumb_rel

    return photo_rel, thumb_rel, photo_abs, thumb_abs