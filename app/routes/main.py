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
from app.forms import BulkActionForm
from app.models.location import Box
from app.extensions import db
from app.forms import AdvancedSearchForm
from app.models.item import Category, Condition, Item
from app.models.location import Location
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
    """
    Главная страница со статистикой и строкой поиска.

    Считает:
    - Стандартные счётчики (stats из stats_service).
    - Возраст приложения в днях — от даты первого предмета в БД
      (или от текущей даты, если предметов нет).
    """
    from datetime import datetime, timezone

    stats = get_dashboard_stats()

    # Возраст приложения — от даты создания самого старого предмета
    # (включая удалённые). Если предметов нет — от текущей даты (0 дней).
    oldest_stmt = db.select(db.func.min(Item.created_at))
    oldest_dt = db.session.scalar(oldest_stmt)

    if oldest_dt is not None:
        # Приводим к timezone-aware для корректного вычитания
        if oldest_dt.tzinfo is None:
            oldest_dt = oldest_dt.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        age_days = (now - oldest_dt).days
    else:
        age_days = 0

    return render_template(
        "main/dashboard.html",
        stats=stats,
        age_days=age_days,
    )


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
    Форма массовых операций доступна — пользователь может отметить
    найденные предметы и применить действие.

    Пагинация сохраняет ?q= через extra_args.
    """
    query = request.args.get("q", "", type=str)
    stmt = quick_search(query)
    page = paginate(stmt)

    # Форма массовых операций — нужна для чекбоксов и панели внизу
    bulk_form = BulkActionForm()
    _populate_bulk_choices(bulk_form)

    return render_template(
        "main/search.html",
        page=page,
        form=None,
        bulk_form=bulk_form,
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
    Расширенный поиск с фильтрами и панелью массовых операций.

    GET-форма с параметрами в query-string. CSRF отключён
    для этой формы (Meta.csrf = False в AdvancedSearchForm).

    Поддерживает предзаполнение цели массового переноса через
    ?target_location=N или ?target_box=M (кнопки «Переместить сюда»
    на страницах локации/бокса).
    """
    form = AdvancedSearchForm(request.args, meta={"csrf": False})
    _populate_search_choices(form)

    # Отделяем параметры пагинации от фильтров поиска
    data = _extract_search_params(form)
    per_page = data.pop("per_page", 20)

    # Строим запрос
    stmt = advanced_search(**data)
    stmt = stmt.order_by(Item.created_at.desc())
    page = paginate(stmt, per_page=per_page)

    # --- Форма массовых операций ---
    bulk_form = BulkActionForm()
    _populate_bulk_choices(bulk_form)

    # Предзаполнение цели переноса из URL
    target_location = request.args.get("target_location", type=int)
    target_box = request.args.get("target_box", type=int)

    if target_box:
        # Если задан бокс — подтягиваем его локацию
        box = db.session.get(Box, target_box)
        if box and not box.is_deleted:
            bulk_form.action.data = "move"
            bulk_form.target_box_id.data = box.id
            bulk_form.target_location_id.data = box.location_id
            flash(
                f"Режим переноса: выбранные предметы переедут в "
                f"«{box.location.name} / {box.name}».",
                "info",
            )
    elif target_location:
        loc = db.session.get(Location, target_location)
        if loc and not loc.is_deleted:
            bulk_form.action.data = "move"
            bulk_form.target_location_id.data = loc.id
            flash(
                f"Режим переноса: выбранные предметы переедут в «{loc.name}».",
                "info",
            )

    # Готовим аргументы для пагинации без ?page=
    extra_args = {k: v for k, v in request.args.items() if k != "page"}

    return render_template(
        "main/search.html",
        page=page,
        form=form,
        bulk_form=bulk_form,
        quick_query=None,
        results_count=page.total,
        extra_args=extra_args,
    )


# ============================================================
# Вспомогательные функции
# ============================================================


def _populate_search_choices(form: AdvancedSearchForm) -> None:
    """
    Заполняет SelectField формы поиска актуальными справочниками.
    Фильтр по упаковке убран, добавлен фильтр по боксу.
    """
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
    form.box_id.choices = [(0, "— все боксы —")] + [
        (b.id, f"{b.location.name} / {b.name}")
        for b in db.session.scalars(
            db.select(Box)
            .where(Box.is_deleted.is_(False))
            .order_by(Box.location_id, Box.name)
        ).all()
    ]


def _populate_bulk_choices(form: BulkActionForm) -> None:
    """
    Заполняет SelectField формы массовых операций актуальными
    локациями и боксами.
    """
    form.target_location_id.choices = [(0, "— не менять локацию —")] + [
        (l.id, l.name)
        for l in db.session.scalars(
            db.select(Location)
            .where(Location.is_deleted.is_(False))
            .order_by(Location.name)
        ).all()
    ]
    form.target_box_id.choices = [(0, "— не менять бокс —")] + [
        (b.id, f"{b.location.name} / {b.name}")
        for b in db.session.scalars(
            db.select(Box)
            .where(Box.is_deleted.is_(False))
            .order_by(Box.location_id, Box.name)
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
        "box_id": _id_or_none(form.box_id.data),
        "has_photo": bool(form.has_photo.data),
        "case_sensitive": bool(form.case_sensitive.data),
        "include_deleted": False,
        "per_page": form.per_page.data or 20,
    }