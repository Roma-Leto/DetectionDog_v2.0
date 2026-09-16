"""
Blueprint главных страниц: дашборд, поиск, «Мне повезёт!».

Маршруты:
- GET /                    — дашборд со статистикой
- GET /search              — расширенный поиск с фильтрами
- GET /lucky               — «Мне повезёт!» (случайный предмет)
- GET /quick-search        — быстрый поиск (переход из строки на дашборде)
"""

from __future__ import annotations

from flask import (
    Blueprint,
    abort,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import login_required

from app.extensions import db
from app.forms import AdvancedSearchForm
from app.models.item import Category, Condition, Item
from app.models.location import Location, Packaging
from app.services import (
    advanced_search,
    get_dashboard_stats,
    quick_search,
    random_item,
)
from app.utils import paginate

main_bp = Blueprint("main", __name__)


# ============================================================
# Дашборд
# ============================================================


@main_bp.route("/")
@login_required
def dashboard():
    """Главная страница со статистикой и строкой поиска."""
    stats = get_dashboard_stats()
    return render_template("main/dashboard.html", stats=stats)


# ============================================================
# Быстрый поиск (переход из строки на дашборде)
# ============================================================


@main_bp.route("/quick-search")
@login_required
def quick_search_view():
    """
    Быстрый поиск: принимает ?q=<строка>, показывает результаты
    в том же шаблоне, что и расширенный поиск.

    Отличие от /search: нет формы с фильтрами, только результаты.
    """
    query = request.args.get("q", "", type=str)
    stmt = quick_search(query)
    page = paginate(stmt)

    return render_template(
        "main/search.html",
        page=page,
        form=None,
        quick_query=query,
        results_count=page.total,
        extra_args={"q": query},
    )


# ============================================================
# «Мне повезёт!»
# ============================================================


@main_bp.route("/lucky")
@login_required
def lucky():
    """
    Открывает карточку случайного активного предмета.

    Если предметов нет — flash и редирект на дашборд.
    """
    item = random_item()
    if item is None:
        flash("В базе пока нет предметов.", "info")
        return redirect(url_for("main.dashboard"))

    return redirect(url_for("items.detail", item_id=item.id))


# ============================================================
# Расширенный поиск
# ============================================================


@main_bp.route("/search", methods=["GET"])
@login_required
def search():
    """
    Расширенный поиск с фильтрами.

    GET-форма с параметрами в query-string. CSRF отключён
    для этой формы (Meta.csrf = False в AdvancedSearchForm).
    """
    form = AdvancedSearchForm(request.args, meta={"csrf": False})
    _populate_search_choices(form)

    # Извлекаем данные (form.validate() не вызываем — все поля опциональны)
    data = _extract_search_params(form)

    # Отделяем параметры пагинации от фильтров поиска
    per_page = data.pop("per_page", 20)


    # Сортировка и пагинация
    stmt = advanced_search(**data)
    stmt = stmt.order_by(Item.created_at.desc())
    page = paginate(stmt, per_page=per_page)

    # Готовим аргументы для пагинации без ?page=
    extra_args = {k: v for k, v in request.args.items() if k != "page"}

    return render_template(
        "main/search.html",
        page=page,
        form=form,
        quick_query=None,
        results_count=page.total,
        extra_args=extra_args,
    )


# ============================================================
# Вспомогательные функции
# ============================================================


def _populate_search_choices(form: AdvancedSearchForm) -> None:
    """Заполняет SelectField формы поиска актуальными справочниками."""
    form.category_id.choices = [(0, "— все категории —")] + [
        (c.id, c.name)
        for c in db.session.scalars(
            db.select(Category)
            .where(Category.is_deleted.is_(False))
            .order_by(Category.name)
        ).all()
    ]
    form.condition_id.choices = [(0, "— все состояния —")] + [
        (c.id, c.name)
        for c in db.session.scalars(
            db.select(Condition)
            .where(Condition.is_deleted.is_(False))
            .order_by(Condition.name)
        ).all()
    ]
    form.location_id.choices = [(0, "— все локации —")] + [
        (l.id, l.name)
        for l in db.session.scalars(
            db.select(Location)
            .where(Location.is_deleted.is_(False))
            .order_by(Location.name)
        ).all()
    ]
    form.packaging_id.choices = [(0, "— все упаковки —")] + [
        (p.id, p.name)
        for p in db.session.scalars(
            db.select(Packaging)
            .where(Packaging.is_deleted.is_(False))
            .order_by(Packaging.name)
        ).all()
    ]


def _extract_search_params(form: AdvancedSearchForm) -> dict:
    """
    Извлекает параметры поиска из формы.

    Пустые/нулевые значения конвертируются в None — сервис
    их пропустит.
    """
    def _id_or_none(value: int | None) -> int | None:
        return value if value else None

    return {
        "q": form.q.data or None,
        "date_from": form.date_from.data,
        "date_to": form.date_to.data,
        "category_id": _id_or_none(form.category_id.data),
        "condition_id": _id_or_none(form.condition_id.data),
        "location_id": _id_or_none(form.location_id.data),
        "packaging_id": _id_or_none(form.packaging_id.data),
        "has_photo": bool(form.has_photo.data),
        "case_sensitive": bool(form.case_sensitive.data),
        "include_deleted": False,  # пока не даём пользователю этот флаг
        "per_page": form.per_page.data or 20,
    }