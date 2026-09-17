"""
Сервис поиска предметов.

Два режима:
1. quick_search — поиск по подстроке в name/description без учёта регистра.
   Используется в строке поиска на дашборде.
2. advanced_search — поиск с фильтрами (категория, локация, состояние,
   упаковка, даты, наличие фото, учёт регистра).

Оба возвращают SQLAlchemy Select, готовый для передачи в paginate().
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Select, or_

from app.extensions import db
from app.models.item import Item


def quick_search(query: str) -> Select:
    """
    Быстрый поиск по подстроке в name и description.

    Без учёта регистра. Использует ILIKE (PostgreSQL-специфичный).
    Для поиска по «любому количеству совпадающих подряд символов»
    (по ТЗ п. 9.1) этого достаточно.
    """
    stmt = db.select(Item).where(Item.is_deleted.is_(False))

    if query and query.strip():
        pattern = f"%{query.strip()}%"
        stmt = stmt.where(
            or_(
                Item.name.ilike(pattern),
                Item.description.ilike(pattern),
            )
        )

    return stmt.order_by(Item.created_at.desc())


def advanced_search(
    *,
    q: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    category_id: int | None = None,
    condition_id: int | None = None,
    location_id: int | None = None,
    box_id: int | None = None,
    has_photo: bool = False,
    case_sensitive: bool = False,
    include_deleted: bool = False,
) -> Select:
    """
    Расширенный поиск с фильтрами.

    Все параметры опциональны. Пустые — пропускаются.
    Возвращает Select без сортировки; сортировку задаёт вызывающий код.

    Фильтр по упаковке убран (используется редко).
    Фильтр по боксу добавлен.

    :param include_deleted: включать ли удалённые предметы
    """
    stmt = db.select(Item)

    if not include_deleted:
        stmt = stmt.where(Item.is_deleted.is_(False))

    # --- Поиск по подстроке ---
    if q and q.strip():
        pattern = f"%{q.strip()}%"
        if case_sensitive:
            stmt = stmt.where(
                or_(
                    Item.name.like(pattern),
                    Item.description.like(pattern),
                )
            )
        else:
            stmt = stmt.where(
                or_(
                    Item.name.ilike(pattern),
                    Item.description.ilike(pattern),
                )
            )

    # --- Временной диапазон ---
    if date_from:
        stmt = stmt.where(Item.created_at >= date_from)
    if date_to:
        stmt = stmt.where(Item.created_at <= date_to)

    # --- Фильтры по FK ---
    if category_id:
        stmt = stmt.where(Item.category_id == category_id)
    if condition_id:
        stmt = stmt.where(Item.condition_id == condition_id)
    if location_id:
        stmt = stmt.where(Item.location_id == location_id)
    if box_id:
        stmt = stmt.where(Item.box_id == box_id)

    # --- Только с фото ---
    if has_photo:
        stmt = stmt.where(Item.photo_path.isnot(None))

    return stmt


def random_item() -> Item | None:
    """
    Случайный активный предмет для кнопки «Мне повезёт!».

    Использует ORDER BY RANDOM() LIMIT 1. На объёме до 100 000
    строк работает быстро. Для больших объёмов нужен другой подход
    (tablesample system), но у нас не тот случай.
    """
    return db.session.scalar(
        db.select(Item)
        .where(Item.is_deleted.is_(False))
        .order_by(db.func.random())
        .limit(1)
    )