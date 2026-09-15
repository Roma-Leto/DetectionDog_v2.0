"""
Инициализация расширений Flask.

Расширения создаются здесь без привязки к приложению (паттерн
«application factory»), а привязываются позже через init_app().
Это позволяет использовать один и тот же код для dev/prod/test
с разными настройками.
"""

from __future__ import annotations

from flask_login import LoginManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect

# --- База данных ---
db = SQLAlchemy()

# --- Миграции Alembic ---
migrate = Migrate()

# --- CSRF-защита форм ---
csrf = CSRFProtect()

# --- Аутентификация ---
login_manager = LoginManager()
login_manager.login_view = "auth.login"            # куда редиректить неавторизованных
login_manager.login_message = "Требуется вход в систему."
login_manager.login_message_category = "warning"
login_manager.session_protection = "strong"       # защита от кражи сессии


@login_manager.user_loader
def load_user(user_id: str):
    """
    Callback для Flask-Login: получает пользователя по ID из сессии.

    Импорт внутри функции, чтобы избежать циклической зависимости
    между extensions.py и models/user.py.
    """
    from app.models.user import User

    return db.session.get(User, int(user_id))