"""
Blueprint главных страниц: дашборд, поиск, «Мне повезёт».

На Этапе 2 здесь только заглушка дашборда — наполним на Этапе 5.
"""

from __future__ import annotations

from flask import Blueprint, render_template
from flask_login import login_required

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
@login_required
def dashboard():
    """
    Главная страница (дашборд).

    Пока — заглушка. На Этапе 5 добавим статистику, поиск,
    «Мне повезёт», последние действия.
    """
    return render_template("main/dashboard.html")