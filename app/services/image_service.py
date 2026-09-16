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


def process_and_save_image(file_storage, temp: bool = False) -> tuple[str, str]:
    """
    Обрабатывает загруженное изображение: сжимает, создаёт thumbnail,
    сохраняет оба файла на диск.

    :param file_storage: werkzeug.datastructures.FileStorage (из формы)
    :param temp: если True — сохранить во временную папку temp/
                 (для фото, отправленных на распознавание).
                 Потом temp-файлы перемещаются в основную папку
                 при сабмите формы.
    :return: (photo_path, thumbnail_path) — относительные пути от UPLOAD_FOLDER.
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
        img.load()
    except UnidentifiedImageError as e:
        raise ImageProcessingError(
            "Файл не является изображением или формат не поддерживается."
        ) from e
    except Exception as e:
        raise ImageProcessingError(f"Ошибка открытия изображения: {e}") from e

    # Применяем EXIF-поворот
    img = ImageOps.exif_transpose(img)

    # Конвертируем в RGB
    if img.mode != "RGB":
        if img.mode in ("RGBA", "LA", "P"):
            background = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode == "P":
                img = img.convert("RGBA")
            background.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
            img = background
        else:
            img = img.convert("RGB")

    # Готовим пути
    photo_rel, thumb_rel, photo_abs, thumb_abs = _generate_paths(temp=temp)
    photo_abs.parent.mkdir(parents=True, exist_ok=True)
    thumb_abs.parent.mkdir(parents=True, exist_ok=True)

    # --- Основное фото ---
    max_dim = current_app.config["IMAGE_MAX_DIMENSION"]
    quality = current_app.config["IMAGE_JPEG_QUALITY"]

    main_img = img.copy()
    main_img.thumbnail((max_dim, max_dim), Image.LANCZOS)
    main_img.save(photo_abs, format="JPEG", quality=quality, optimize=True, progressive=True)

    # --- Thumbnail ---
    thumb_size = current_app.config["THUMBNAIL_SIZE"]
    thumb_img = img.copy()
    thumb_img.thumbnail((thumb_size, thumb_size), Image.LANCZOS)
    thumb_img.save(thumb_abs, format="JPEG", quality=80, optimize=True)

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

def move_temp_images(
    temp_photo_path: str,
    temp_thumb_path: str,
) -> tuple[str, str]:
    """
    Перемещает временные фото из photos/temp/ в постоянную папку
    photos/YYYY/MM/.

    Вызывается при сохранении предмета, если фото было предзагружено
    через /items/analyze.

    Если временный файл отсутствует (например, уже перемещён) —
    возвращает исходные пути.

    :return: (photo_path, thumb_path) — новые относительные пути.
    """
    if not temp_photo_path or not temp_thumb_path:
        return temp_photo_path, temp_thumb_path

    upload_folder = Path(current_app.config["UPLOAD_FOLDER"])
    temp_photo_abs = upload_folder / temp_photo_path
    temp_thumb_abs = upload_folder / temp_thumb_path

    # Если файл уже не в temp/ — значит, уже перемещён
    if "/temp/" not in temp_photo_path:
        return temp_photo_path, temp_thumb_path

    if not temp_photo_abs.exists():
        return temp_photo_path, temp_thumb_path

    # Готовим целевые пути
    now = datetime.now()
    filename = temp_photo_abs.name  # <token>.jpg
    new_photo_rel = f"photos/{now:%Y}/{now:%m}/{filename}"
    new_thumb_rel = f"thumbnails/{now:%Y}/{now:%m}/{filename}"

    new_photo_abs = upload_folder / new_photo_rel
    new_thumb_abs = upload_folder / new_thumb_rel

    new_photo_abs.parent.mkdir(parents=True, exist_ok=True)
    new_thumb_abs.parent.mkdir(parents=True, exist_ok=True)

    # Перемещаем
    temp_photo_abs.rename(new_photo_abs)
    if temp_thumb_abs.exists():
        temp_thumb_abs.rename(new_thumb_abs)

    return new_photo_rel, new_thumb_rel


# ============================================================
# Приватные функции
# ============================================================


def _generate_paths(temp: bool = False) -> tuple[str, str, Path, Path]:
    """
    Генерирует уникальные относительные и абсолютные пути для фото.

    Структура:
    - temp=False: photos/YYYY/MM/<token>.jpg + thumbnails/YYYY/MM/<token>.jpg
    - temp=True:  photos/temp/<token>.jpg   + thumbnails/temp/<token>.jpg

    Временные файлы перемещаются в photos/YYYY/MM/ при сабмите формы
    (см. move_temp_images).
    """
    upload_folder = Path(current_app.config["UPLOAD_FOLDER"])
    now = datetime.now()

    token = secrets.token_hex(8)
    filename = f"{token}.jpg"

    if temp:
        photo_rel = f"photos/temp/{filename}"
        thumb_rel = f"thumbnails/temp/{filename}"
    else:
        photo_rel = f"photos/{now:%Y}/{now:%m}/{filename}"
        thumb_rel = f"thumbnails/{now:%Y}/{now:%m}/{filename}"

    photo_abs = upload_folder / photo_rel
    thumb_abs = upload_folder / thumb_rel

    return photo_rel, thumb_rel, photo_abs, thumb_abs