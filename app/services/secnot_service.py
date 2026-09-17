"""
Сервис заметок secnot.

Заметки хранятся в JSON-файле в корне проекта (secnot.json).
Файл не коммитится в git — это личные заметки разработчика.

Структура файла:
{
    "notes": [
        {
            "id": "uuid-строка",
            "title": "Заголовок",
            "content": "Содержимое",
            "created_at": "ISO-8601",
            "updated_at": "ISO-8601"
        }
    ]
}

Все операции атомарны: сначала пишем во временный файл,
потом переименовываем. Это защищает от потери данных при
сбое во время записи.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from flask import current_app

# Корень проекта (родитель папки app)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_SECNOT_FILE = _PROJECT_ROOT / "secnot.json"


def _read_notes() -> list[dict[str, Any]]:
    """
    Читает JSON-файл. Если файла нет — возвращает пустой список.

    Не падает при невалидном JSON: логирует ошибку и возвращает [].
    """
    if not _SECNOT_FILE.exists():
        return []

    try:
        with _SECNOT_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        current_app.logger.error("Failed to read secnot.json: %s", e)
        return []

    if isinstance(data, dict) and isinstance(data.get("notes"), list):
        return data["notes"]

    return []


def _write_notes(notes: list[dict[str, Any]]) -> None:
    """
    Атомарно записывает JSON-файл.

    1. Пишем во временный файл .secnot.json.tmp
    2. Заменяем оригинал через rename (атомарно на одной ФС).
    """
    payload = {"notes": notes}
    tmp_file = _SECNOT_FILE.with_suffix(".json.tmp")

    with tmp_file.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    # Атомарная замена
    tmp_file.replace(_SECNOT_FILE)


# ============================================================
# Публичные функции
# ============================================================


def list_notes() -> list[dict[str, Any]]:
    """
    Возвращает список заметок, отсортированный по updated_at DESC
    (последние изменённые — сверху).
    """
    notes = _read_notes()
    notes.sort(key=lambda n: n.get("updated_at", ""), reverse=True)
    return notes


def get_note(note_id: str) -> dict[str, Any] | None:
    """Возвращает заметку по ID или None."""
    for note in _read_notes():
        if note.get("id") == note_id:
            return note
    return None


def create_note(title: str, content: str) -> dict[str, Any]:
    """
    Создаёт новую заметку. Возвращает её словарь.

    :param title: заголовок (может быть пустым)
    :param content: содержимое (обязательно)
    """
    now = datetime.now().isoformat(timespec="seconds")
    note = {
        "id": str(uuid.uuid4()),
        "title": title.strip(),
        "content": content.strip(),
        "created_at": now,
        "updated_at": now,
    }

    notes = _read_notes()
    notes.append(note)
    _write_notes(notes)
    return note


def update_note(note_id: str, title: str, content: str) -> dict[str, Any] | None:
    """
    Обновляет существующую заметку. Возвращает обновлённую
    или None, если не найдена.
    """
    notes = _read_notes()
    updated = None

    for note in notes:
        if note.get("id") == note_id:
            note["title"] = title.strip()
            note["content"] = content.strip()
            note["updated_at"] = datetime.now().isoformat(timespec="seconds")
            updated = note
            break

    if updated:
        _write_notes(notes)
    return updated


def delete_note(note_id: str) -> bool:
    """
    Удаляет заметку по ID. Возвращает True, если удалена,
    False — если не найдена.
    """
    notes = _read_notes()
    filtered = [n for n in notes if n.get("id") != note_id]

    if len(filtered) == len(notes):
        return False

    _write_notes(filtered)
    return True