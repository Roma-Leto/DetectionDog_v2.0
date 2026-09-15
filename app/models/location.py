"""
Модели пространственной иерархии:
Location (место) → Box (бокс) → Item (предмет).

Packaging (упаковка) — отдельная сущность, не привязанная
к иерархии мест. Например, «пакет», «вакуумная упаковка»,
«пузырчатая плёнка».
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db
from app.models.mixins import SoftDeleteMixin, TimestampMixin

if TYPE_CHECKING:
    # Импорт только для аннотаций типов — избегаем циклических импортов
    from app.models.item import Item


class Location(TimestampMixin, SoftDeleteMixin, db.Model):
    """
    Место хранения (комната, шкаф, полка, гараж и т.п.).

    Обязательное поле для каждого Item. Может содержать
    боксы и предметы напрямую.
    """

    __tablename__ = "locations"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Связи
    boxes: Mapped[list["Box"]] = relationship(
        back_populates="location",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    items: Mapped[list["Item"]] = relationship(
        back_populates="location",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Location {self.id} {self.name!r}>"


class Box(TimestampMixin, SoftDeleteMixin, db.Model):
    """
    Бокс, коробка, ящик, мешок — контейнер внутри места хранения.

    Опциональное поле для Item: предмет может лежать в локации
    напрямую (на полке), а может быть упакован в бокс.
    """

    __tablename__ = "boxes"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    location_id: Mapped[int] = mapped_column(
        ForeignKey("locations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # Связи
    location: Mapped["Location"] = relationship(
        back_populates="boxes",
        lazy="joined",
    )
    items: Mapped[list["Item"]] = relationship(
        back_populates="box",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Box {self.id} {self.name!r} @ {self.location_id}>"


class Packaging(TimestampMixin, SoftDeleteMixin, db.Model):
    """
    Упаковка предмета: пакет, плёнка, коробка от производителя и т.п.

    Не привязана к иерархии мест — это характеристика предмета.
    """

    __tablename__ = "packagings"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<Packaging {self.id} {self.name!r}>"