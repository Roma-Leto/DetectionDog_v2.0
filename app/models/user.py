"""
Модель пользователя.

Пароли хешируются через werkzeug.security (PBKDF2-SHA256
с солью и 600 000 итераций по умолчанию). Это стандарт для
Flask-приложений без внешних зависимостей.
"""

from __future__ import annotations

from datetime import datetime

from flask_login import UserMixin
from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db


class User(UserMixin, db.Model):
    """Пользователь системы. UserMixin даёт is_authenticated, get_id() и т.д."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_admin: Mapped[bool] = mapped_column(default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # --- Пароли ---

    def set_password(self, password: str) -> None:
        """Хеширует и сохраняет пароль."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Проверяет пароль против сохранённого хеша."""
        return check_password_hash(self.password_hash, password)

    # --- Служебное ---

    def __repr__(self) -> str:
        return f"<User {self.username}>"