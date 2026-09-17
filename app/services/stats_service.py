"""
Сервис статистики для дашборда.

Все запросы оптимизированы: агрегация на стороне PostgreSQL,
никаких N+1. Возвращает готовые к отображению словари/списки.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import func

from app.extensions import db
from app.models.item import Category, Condition, Item
from app.models.location import Location


@dataclass
class DashboardStats:
    """
    Сводная статистика для дашборда.

    Каждое поле — готовый к отображению объект.
    """

    total_items: int = 0
    active_items: int = 0
    deleted_items: int = 0

    total_quantity_active: int = 0

    # Списки (id, name, count), отсортированы по count DESC
    by_category: list[tuple[int, str, int]] = field(default_factory=list)
    by_location: list[tuple[int, str, int]] = field(default_factory=list)

    # Экстремумы
    oldest_active: Item | None = None
    latest_added: Item | None = None
    latest_deleted: Item | None = None


def get_dashboard_stats() -> DashboardStats:
    """
    Собирает всю статистику одним вызовом.

    Делает ~10 SQL-запросов, но все — с агрегацией. На объёме
    до 100 000 предметов работает быстро (<100 мс).
    """
    stats = DashboardStats()

    # --- Общее количество (включая удалённые) ---
    stats.total_items = db.session.scalar(
        db.select(func.count(Item.id))
    ) or 0

    # --- Активные / удалённые ---
    stats.active_items = db.session.scalar(
        db.select(func.count(Item.id)).where(Item.is_deleted.is_(False))
    ) or 0
    stats.deleted_items = stats.total_items - stats.active_items

    # --- Суммарное количество активных предметов ---
    stats.total_quantity_active = db.session.scalar(
        db.select(func.coalesce(func.sum(Item.quantity), 0)).where(
            Item.is_deleted.is_(False)
        )
    ) or 0

    # По категориям: (id, name, count)
    stats.by_category = _group_by_id_name(
        db.select(
            Category.id,
            Category.name,
            func.count(Item.id).label("cnt"),
        )
        .join(Item, Item.category_id == Category.id)
        .where(
            Item.is_deleted.is_(False),
            Category.is_deleted.is_(False),
        )
        .group_by(Category.id, Category.name)
        .order_by(func.count(Item.id).desc(), Category.name)
    )

    # По локациям: (id, name, count)
    stats.by_location = _group_by_id_name(
        db.select(
            Location.id,
            Location.name,
            func.count(Item.id).label("cnt"),
        )
        .join(Item, Item.location_id == Location.id)
        .where(
            Item.is_deleted.is_(False),
            Location.is_deleted.is_(False),
        )
        .group_by(Location.id, Location.name)
        .order_by(func.count(Item.id).desc(), Location.name)
    )

    # --- Самый старый активный предмет ---
    stats.oldest_active = db.session.scalar(
        db.select(Item)
        .where(Item.is_deleted.is_(False))
        .order_by(Item.created_at.asc())
        .limit(1)
    )

    # --- Последний добавленный (активный) ---
    stats.latest_added = db.session.scalar(
        db.select(Item)
        .where(Item.is_deleted.is_(False))
        .order_by(Item.created_at.desc())
        .limit(1)
    )

    # --- Последний удалённый ---
    stats.latest_deleted = db.session.scalar(
        db.select(Item)
        .where(Item.is_deleted.is_(True))
        .order_by(Item.deleted_at.desc())
        .limit(1)
    )

    return stats


# ============================================================
# Приватные функции
# ============================================================


def _group_by_id_name(stmt) -> list[tuple[int, str, int]]:
    """
    Выполняет запрос с тремя колонками (id, name, count).
    Возвращает список кортежей.
    """
    rows = db.session.execute(stmt).all()
    return [(int(row[0]), row[1] or "—", int(row[2])) for row in rows]