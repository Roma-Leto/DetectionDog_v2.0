"""
Blueprint аутентификации: вход, выход, управление пользователями.

Все маршруты доступны по префиксу /auth (задаётся при регистрации
blueprint'а в app/__init__.py).
"""

from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app.extensions import db
from app.forms.auth_forms import LoginForm, UserCreateForm
from app.models.user import User

# Blueprint с именем "auth" — все url_for("auth.login") и т.п.
auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """
    Вход в систему.

    GET — показать форму.
    POST — проверить учётные данные и создать сессию.
    """
    # Уже авторизован — нечего делать на странице входа
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    form = LoginForm()

    if form.validate_on_submit():
        user = db.session.scalar(
            db.select(User).where(User.username == form.username.data)
        )

        # Проверяем и существование, и пароль одной веткой
        if user is None or not user.check_password(form.password.data):
            flash("Неверное имя пользователя или пароль.", "danger")
            return redirect(url_for("auth.login"))

        login_user(user, remember=form.remember_me.data)
        flash(f"Добро пожаловать, {user.username}!", "success")

        # Безопасный редирект на «next» (если пришёл от login_required)
        next_page = request.args.get("next")
        # Защита от open redirect: разрешаем только относительные пути
        if next_page and next_page.startswith("/") and not next_page.startswith("//"):
            return redirect(next_page)
        return redirect(url_for("main.dashboard"))

    return render_template("auth/login.html", form=form)


@auth_bp.route("/logout")
@login_required
def logout():
    """Выход из системы."""
    logout_user()
    flash("Вы вышли из системы.", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route("/users", methods=["GET", "POST"])
@login_required
def users_list():
    """
    Список пользователей + форма создания нового (только для админа).

    Обычный пользователь видит только список без формы.
    """
    if not current_user.is_admin:
        flash("Доступ только для администратора.", "danger")
        return redirect(url_for("main.dashboard"))

    form = UserCreateForm()

    if form.validate_on_submit():
        # Проверка на дубликат имени
        existing = db.session.scalar(
            db.select(User).where(User.username == form.username.data)
        )
        if existing:
            flash(f"Пользователь {form.username.data!r} уже существует.", "danger")
        else:
            new_user = User(
                username=form.username.data,
                is_admin=form.is_admin.data,
            )
            new_user.set_password(form.password.data)
            db.session.add(new_user)
            db.session.commit()
            flash(f"Пользователь {new_user.username!r} создан.", "success")
            return redirect(url_for("auth.users_list"))

    users = db.session.scalars(db.select(User).order_by(User.id)).all()
    return render_template("auth/users.html", users=users, form=form)