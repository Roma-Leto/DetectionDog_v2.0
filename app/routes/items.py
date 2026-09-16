"""
Blueprint предметов: CRUD, загрузка фото, анализ через vision-сервис.

Основные сценарии:

1. GET  /items/                      — список всех предметов (пагинация)
2. GET  /items/?category=5           — список по категории
3. GET  /items/?location=3           — список по локации
4. GET  /items/?box=7                — список по боксу
5. GET  /items/<id>                  — карточка предмета
6. GET  /items/create                — форма создания
7. POST /items/create                — сохранение (с опциональным фото)
8. POST /items/create?action=again   — сохранить + открыть новую форму
                                       с предзаполнением (кнопка «Это и ещё»)
9. GET  /items/<id>/edit             — форма редактирования
10. POST /items/<id>/edit            — сохранение изменений
11. POST /items/<id>/delete          — soft delete
12. POST /items/<id>/restore         — восстановление
13. POST /items/analyze              — загрузить фото, получить автозаполнение
"""

from __future__ import annotations

from flask import (
    Blueprint,
    abort,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import login_required

from app.extensions import db
from app.forms import ItemForm, ItemPhotoAnalyzeForm
from app.models.item import Category, Condition, Item
from app.models.location import Box, Location, Packaging
from app.services import (
    ImageProcessingError,
    get_vision_client,
    process_and_save_image,
)
from app.utils import paginate

items_bp = Blueprint("items", __name__, url_prefix="/items")


# ============================================================
# Списки
# ============================================================


@items_bp.route("/")
@login_required
def list_items():
    """
    Список предметов с фильтрацией и пагинацией.

    Query-параметры:
        category=<id>  — фильтр по категории
        location=<id>  — фильтр по локации
        box=<id>       — фильтр по боксу
        page=<N>       — номер страницы (по умолчанию 1)
    """
    stmt = (
        db.select(Item)
        .where(Item.is_deleted.is_(False))
        .order_by(Item.created_at.desc())
    )

    category_id = request.args.get("category", type=int)
    location_id = request.args.get("location", type=int)
    box_id = request.args.get("box", type=int)

    filter_label = None

    if category_id:
        category = db.session.get(Category, category_id)
        if not category or category.is_deleted:
            abort(404)
        stmt = stmt.where(Item.category_id == category_id)
        filter_label = f"Категория: {category.name}"

    if location_id:
        location = db.session.get(Location, location_id)
        if not location or location.is_deleted:
            abort(404)
        stmt = stmt.where(Item.location_id == location_id)
        filter_label = f"Локация: {location.name}"

    if box_id:
        box = db.session.get(Box, box_id)
        if not box or box.is_deleted:
            abort(404)
        stmt = stmt.where(Item.box_id == box_id)
        filter_label = f"Бокс: {box.name}"

    page = paginate(stmt)

    extra_args = {}
    if category_id:
        extra_args["category"] = category_id
    if location_id:
        extra_args["location"] = location_id
    if box_id:
        extra_args["box"] = box_id

    return render_template(
        "items/list.html",
        page=page,
        filter_label=filter_label,
        extra_args=extra_args,
    )


# ============================================================
# Просмотр предмета
# ============================================================


@items_bp.route("/<int:item_id>")
@login_required
def detail(item_id: int):
    """Карточка предмета."""
    item = db.get_or_404(Item, item_id)
    return render_template("items/detail.html", item=item)


# ============================================================
# Создание
# ============================================================


@items_bp.route("/create", methods=["GET", "POST"])
@login_required
def create():
    """
    Создание предмета.

    GET:
        - Если в сессии есть vision_result (после /items/analyze) —
          предзаполняем поля из результата распознавания.
        - Иначе если передан ?from_item=<id> — предзаполняем
          category/condition/location/box/packaging из указанного
          предмета (для кнопки «Это и ещё»).
        - Иначе — пустая форма с дефолтами (состояние «б/у», quantity=1).

    POST:
        - Валидируем.
        - Обрабатываем фото (сжатие, thumbnail) через image_service.
        - Создаём Item в БД.
        - В зависимости от action:
            - "again"  → редирект на /items/create?from_item=<id>
            - "home"   → редирект на дашборд
    """
    from_item_id = request.args.get("from_item", type=int)
    source = db.session.get(Item, from_item_id) if from_item_id else None

    form = ItemForm()
    _populate_choices(form)

    if form.validate_on_submit():
        # --- Обработка фото (опционально) ---
        photo_rel = None
        thumb_rel = None

        if form.photo.data:
            try:
                photo_rel, thumb_rel = process_and_save_image(form.photo.data)
            except ImageProcessingError as e:
                flash(f"Ошибка обработки фото: {e}", "danger")
                return render_template(
                    "items/create.html",
                    form=form,
                    analyze_form=ItemPhotoAnalyzeForm(),
                    source_item=source,
                )

        # --- Создание предмета ---
        item = Item(
            name=form.name.data,
            description=form.description.data or None,
            quantity=form.quantity.data,
            category_id=form.category_id.data,
            condition_id=form.condition_id.data,
            location_id=form.location_id.data,
            box_id=form.box_id.data or None,
            packaging_id=form.packaging_id.data or None,
            photo_path=photo_rel,
            photo_thumbnail_path=thumb_rel,
        )
        db.session.add(item)
        db.session.commit()

        flash(f"Предмет '{item.name}' сохранён (ID {item.id}).", "success")

        action = request.form.get("action", "home")

        if action == "again":
            return redirect(url_for("items.create", from_item=item.id))

        return redirect(url_for("main.dashboard"))

    # --- GET: предзаполнение формы ---
    if request.method == "GET":
        # 1. Приоритет — результат vision-анализа из сессии
        vision_result = session.pop("vision_result", None)
        if vision_result:
            _apply_vision_result(form, vision_result)
            if not form.location_id.data:
                _apply_defaults(form)

        # 2. Предзаполнение из существующего предмета («Это и ещё»)
        elif source:
            form.category_id.data = source.category_id
            form.condition_id.data = source.condition_id
            form.location_id.data = source.location_id
            form.box_id.data = source.box_id or 0
            form.packaging_id.data = source.packaging_id or 0
            form.quantity.data = 1

        # 3. Пустая форма — дефолты
        else:
            _apply_defaults(form)

    return render_template(
        "items/create.html",
        form=form,
        analyze_form=ItemPhotoAnalyzeForm(),
        source_item=source,
    )


# ============================================================
# Редактирование
# ============================================================


@items_bp.route("/<int:item_id>/edit", methods=["GET", "POST"])
@login_required
def edit(item_id: int):
    """Редактирование предмета."""
    item = db.get_or_404(Item, item_id)
    if item.is_deleted:
        flash("Предмет удалён и не может быть изменён.", "warning")
        return redirect(url_for("items.list_items"))

    form = ItemForm(obj=item)
    _populate_choices(form)

    if form.validate_on_submit():
        item.name = form.name.data
        item.description = form.description.data or None
        item.quantity = form.quantity.data
        item.category_id = form.category_id.data
        item.condition_id = form.condition_id.data
        item.location_id = form.location_id.data
        item.box_id = form.box_id.data or None
        item.packaging_id = form.packaging_id.data or None

        if form.photo.data:
            try:
                new_photo, new_thumb = process_and_save_image(form.photo.data)
                item.photo_path = new_photo
                item.photo_thumbnail_path = new_thumb
            except ImageProcessingError as e:
                flash(f"Ошибка обработки фото: {e}", "danger")
                return render_template(
                    "items/edit.html", form=form, item=item
                )

        db.session.commit()
        flash(f"Предмет '{item.name}' обновлён.", "success")
        return redirect(url_for("items.detail", item_id=item.id))

    return render_template("items/edit.html", form=form, item=item)


# ============================================================
# Удаление (soft) и восстановление
# ============================================================


@items_bp.route("/<int:item_id>/delete", methods=["POST"])
@login_required
def delete(item_id: int):
    """Мягкое удаление предмета."""
    item = db.get_or_404(Item, item_id)
    if item.is_deleted:
        flash("Предмет уже удалён.", "info")
        return redirect(url_for("items.detail", item_id=item.id))

    item.soft_delete()
    db.session.commit()
    flash(f"Предмет '{item.name}' удалён.", "info")
    return redirect(url_for("items.list_items"))


@items_bp.route("/<int:item_id>/restore", methods=["POST"])
@login_required
def restore(item_id: int):
    """Восстановление мягко удалённого предмета."""
    item = db.get_or_404(Item, item_id)
    if not item.is_deleted:
        flash("Предмет и так активен.", "info")
        return redirect(url_for("items.detail", item_id=item.id))

    item.restore()
    db.session.commit()
    flash(f"Предмет '{item.name}' восстановлен.", "success")
    return redirect(url_for("items.detail", item_id=item.id))


# ============================================================
# Анализ фото (без создания предмета)
# ============================================================


@items_bp.route("/analyze", methods=["POST"])
@login_required
def analyze_photo():
    """
    Принимает фото, отправляет в vision-сервис, возвращает страницу
    создания предмета с автозаполненными полями.
    """
    form = ItemPhotoAnalyzeForm()
    if not form.validate_on_submit():
        for field_errors in form.errors.values():
            for err in field_errors:
                flash(err, "danger")
        return redirect(url_for("items.create"))

    form.photo.data.seek(0)
    photo_bytes = form.photo.data.read()
    form.photo.data.seek(0)

    client = get_vision_client()
    result = client.analyze_image(photo_bytes)

    if result is None:
        flash(
            "Vision-сервис недоступен. Заполните данные вручную.",
            "warning",
        )
        return redirect(url_for("items.create"))

    if result.is_empty():
        flash(
            "Не удалось распознать предмет. Заполните данные вручную.",
            "warning",
        )
        return redirect(url_for("items.create"))

    session["vision_result"] = {
        "title": result.title,
        "description": result.description,
        "category_hint": result.category_hint,
        "condition_hint": result.condition_hint,
        "quantity": result.quantity,
        "confidence": result.confidence,
    }
    flash(
        f"Предмет распознан (уверенность {result.confidence:.0%}). "
        "Проверьте и дополните поля.",
        "success",
    )
    return redirect(url_for("items.create"))


# ============================================================
# Вспомогательные функции
# ============================================================


def _populate_choices(form: ItemForm) -> None:
    """
    Заполняет choices для всех SelectField актуальными данными.

    Вызывается в create/edit ДО validate_on_submit.
    """
    form.category_id.choices = [
        (c.id, c.name)
        for c in db.session.scalars(
            db.select(Category)
            .where(Category.is_deleted.is_(False))
            .order_by(Category.name)
        ).all()
    ]
    form.condition_id.choices = [
        (c.id, c.name)
        for c in db.session.scalars(
            db.select(Condition)
            .where(Condition.is_deleted.is_(False))
            .order_by(Condition.name)
        ).all()
    ]
    form.location_id.choices = [
        (l.id, l.name)
        for l in db.session.scalars(
            db.select(Location)
            .where(Location.is_deleted.is_(False))
            .order_by(Location.name)
        ).all()
    ]
    form.box_id.choices = [(0, "— без бокса —")] + [
        (b.id, f"{b.location.name} / {b.name}")
        for b in db.session.scalars(
            db.select(Box)
            .where(Box.is_deleted.is_(False))
            .order_by(Box.location_id, Box.name)
        ).all()
    ]
    form.packaging_id.choices = [(0, "— без упаковки —")] + [
        (p.id, p.name)
        for p in db.session.scalars(
            db.select(Packaging)
            .where(Packaging.is_deleted.is_(False))
            .order_by(Packaging.name)
        ).all()
    ]


def _apply_defaults(form: ItemForm) -> None:
    """
    Дефолты для новой формы:
    - condition = «б/у» (первый в DEFAULT_CONDITIONS, т.е. минимальный ID)
    - category, location — если в БД только одна активная, выбираем её
    - box, packaging — «без» (0)
    - quantity = 1
    """
    default_condition = db.session.scalar(
        db.select(Condition)
        .where(Condition.is_deleted.is_(False))
        .order_by(Condition.id)
        .limit(1)
    )
    if default_condition:
        form.condition_id.data = default_condition.id

    cats = db.session.scalars(
        db.select(Category).where(Category.is_deleted.is_(False))
    ).all()
    if len(cats) == 1:
        form.category_id.data = cats[0].id

    locs = db.session.scalars(
        db.select(Location).where(Location.is_deleted.is_(False))
    ).all()
    if len(locs) == 1:
        form.location_id.data = locs[0].id

    form.box_id.data = 0
    form.packaging_id.data = 0
    form.quantity.data = 1


def _apply_vision_result(form: ItemForm, vision_result: dict) -> None:
    """
    Заполняет поля формы из результата vision-анализа.

    Vision-сервис возвращает «подсказки» — имена категорий
    и состояний, а не ID. Мы ищем подходящие записи в БД
    через ilike-поиск по подстроке.
    """
    if vision_result.get("title"):
        form.name.data = vision_result["title"]
    if vision_result.get("description"):
        form.description.data = vision_result["description"]
    if vision_result.get("quantity"):
        form.quantity.data = vision_result["quantity"]

    if vision_result.get("category_hint"):
        hint = vision_result["category_hint"]
        cat = db.session.scalar(
            db.select(Category).where(
                Category.name.ilike(f"%{hint}%"),
                Category.is_deleted.is_(False),
            )
        )
        if cat:
            form.category_id.data = cat.id

    if vision_result.get("condition_hint"):
        hint = vision_result["condition_hint"]
        cond = db.session.scalar(
            db.select(Condition).where(
                Condition.name.ilike(f"%{hint}%"),
                Condition.is_deleted.is_(False),
            )
        )
        if cond:
            form.condition_id.data = cond.id