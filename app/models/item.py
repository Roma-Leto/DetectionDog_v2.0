"""
Модели Category, Condition и Item — центральные сущности системы.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db
from app.models.mixins import SoftDeleteMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.location import Box, Location, Packaging


class Category(TimestampMixin, SoftDeleteMixin, db.Model):
    """
    Категория предмета (Одежда, Инструменты, Химия и т.п.).

    Предустановленный список загружается при первом запуске
    через сид-скрипт (см. scripts/seed_data.py, добавим позже).
    """

    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    items: Mapped[list["Item"]] = relationship(back_populates="category", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Category {self.id} {self.name!r}>"


class Condition(TimestampMixin, SoftDeleteMixin, db.Model):
    """
    Состояние предмета: новый, б/у, сломанный и т.п.

    По умолчанию для нового Item выбирается запись с
    именем «б/у» (создаётся сид-скриптом).
    """

    __tablename__ = "conditions"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    items: Mapped[list["Item"]] = relationship(back_populates="condition", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Condition {self.id} {self.name!r}>"


class Item(TimestampMixin, SoftDeleteMixin, db.Model):
    """
    Инвентаризируемый предмет.

    Обязательные поля: name, location_id, category_id, condition_id.
    Опциональные: description, box_id, packaging_id, photo_path.
    """

    __tablename__ = "items"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # --- Внешние ключи ---
    category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    condition_id: Mapped[int] = mapped_column(
        ForeignKey("conditions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    location_id: Mapped[int] = mapped_column(
        ForeignKey("locations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    box_id: Mapped[int | None] = mapped_column(
        ForeignKey("boxes.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    packaging_id: Mapped[int | None] = mapped_column(
        ForeignKey("packagings.id", ondelete="SET NULL"),
        nullable=True,
    )

    # --- Фото ---
    photo_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    photo_thumbnail_path: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # --- Связи ---
    category: Mapped["Category"] = relationship(back_populates="items", lazy="joined")
    condition: Mapped["Condition"] = relationship(back_populates="items", lazy="joined")
    location: Mapped["Location"] = relationship(back_populates="items", lazy="joined")
    box: Mapped["Box | None"] = relationship(back_populates="items", lazy="joined")
    packaging: Mapped["Packaging | None"] = relationship(lazy="joined")

    def __repr__(self) -> str:
        return f"<Item {self.id} {self.name!r} qty={self.quantity}>"