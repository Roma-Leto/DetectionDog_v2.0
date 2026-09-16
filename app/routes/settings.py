"""
Blueprint настроек приложения: выбор темы.
"""

from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from flask_login import login_required

settings_bp = Blueprint("settings", __name__, url_prefix="/settings")


# Список доступных тем (совпадает с файлами в static/css/themes/)
AVAILABLE_THEMES: list[dict] = [
    {"id": "green-light", "name": "Зелёная светлая", "colors": ["#2e7d32", "#ffffff"]},
    {"id": "green-dark", "name": "Зелёная тёмная", "colors": ["#4caf50", "#1a1a1a"]},
    {"id": "purple-light", "name": "Фиолетовая светлая", "colors": ["#7b1fa2", "#ffffff"]},
    {"id": "purple-dark", "name": "Фиолетовая тёмная", "colors": ["#ba68c8", "#1a1520"]},
]

DEFAULT_THEME = "green-light"


@settings_bp.route("/theme", methods=["GET", "POST"])
@login_required
def theme():
    """
    Страница выбора темы.

    GET — показать список с текущей активной.
    POST — сохранить выбор в сессию.
    """
    if request.method == "POST":
        selected = request.form.get("theme", "").strip()
        valid_ids = {t["id"] for t in AVAILABLE_THEMES}

        if selected in valid_ids:
            session["theme"] = selected
            flash(f"Тема изменена на «{_theme_name(selected)}».", "success")
        else:
            flash("Неизвестная тема.", "danger")

        return redirect(url_for("settings.theme"))

    current = session.get("theme", DEFAULT_THEME)
    return render_template(
        "settings/theme.html",
        themes=AVAILABLE_THEMES,
        current=current,
    )


def _theme_name(theme_id: str) -> str:
    """Возвращает человекочитаемое имя темы по ID."""
    for t in AVAILABLE_THEMES:
        if t["id"] == theme_id:
            return t["name"]
    return theme_id