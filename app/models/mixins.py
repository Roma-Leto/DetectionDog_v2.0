"""
Переиспользуемые миксины для моделей SQLAlchemy.

Миксин — это класс, который добавляет набор колонок и методов
в другие модели через множественное наследование.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column


class TimestampMixin:
    """
    Добавляет колонку created_at с автоматической установкой
    серверного времени PostgreSQL при вставке записи.

    server_default=func.now() означает, что значение подставляет
    сама СУБД, а не Python. Это защищает от рассинхронизации
    часов между приложением и БД.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )


class SoftDeleteMixin:
    """
    Мягкое удаление: запись остаётся в БД, но помечается флагом.

    Все запросы к «активным» записям должны добавлять фильтр
    `Model.is_deleted == False`. Это реализовано в методах
    каждого репозитория/сервиса.
    """

    is_deleted: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
        nullable=False,
        index=True,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    def soft_delete(self) -> None:
        """Помечает запись как удалённую и фиксирует время."""
        self.is_deleted = True
        self.deleted_at = datetime.now()

    def restore(self) -> None:
        """Отменяет мягкое удаление."""
        self.is_deleted = False
        self.deleted_at = None