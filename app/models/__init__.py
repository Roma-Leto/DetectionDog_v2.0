"""
Пакет моделей. Импортирует все модели, чтобы Alembic
и SQLAlchemy видели их при автогенерации миграций.
"""

from app.models.item import Category, Condition, Item
from app.models.location import Box, Location, Packaging
from app.models.user import User

__all__ = [
    "User",
    "Category",
    "Condition",
    "Item",
    "Location",
    "Box",
    "Packaging",
]