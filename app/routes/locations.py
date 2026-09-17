"""
Blueprint справочника локаций, боксов и упаковок.

- Location — места хранения
- Box — боксы внутри локаций
- Packaging — упаковки (не привязаны к локациям)

После создания записи поддерживается редирект обратно в форму
предмета через ?return_to=items.create (см. app/utils/redirects.py).
"""

from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, url_for
from flask_login import login_required

from app.extensions import db
from app.forms import BoxForm, LocationForm, PackagingForm
from app.models.item import Item
from app.models.location import Box, Location, Packaging
from app.utils import paginate
from app.utils.redirects import redirect_after_create
from app.services import ImageProcessingError, process_and_save_image

locations_bp = Blueprint("locations", __name__, url_prefix="/locations")


# ============================================================
# Локации
# ============================================================


@locations_bp.route("/")
@login_required
def list_locations():
    """Список мест хранения."""
    stmt = (
        db.select(Location)
        .where(Location.is_deleted.is_(False))
        .order_by(Location.name)
    )
    page = paginate(stmt)
    return render_template("locations/list.html", page=page)


@locations_bp.route("/<int:location_id>")
@login_required
def detail_location(location_id: int):
    """
    Содержимое локации:
    - боксы в этой локации (с количеством предметов)
    - предметы прямо в локации (не в боксах)

    Оба списка — с пагинацией по ITEMS_PER_PAGE (20 по умолчанию).
    Для каждого бокса подгружается количество предметов одним
    запросом с GROUP BY (без N+1).
    """
    location = db.get_or_404(Location, location_id)
    if location.is_deleted:
        flash("Локация удалена.", "warning")
        return redirect(url_for("locations.list_locations"))

    # --- Боксы в локации (с пагинацией) ---
    boxes_stmt = (
        db.select(Box)
        .where(
            Box.location_id == location.id,
            Box.is_deleted.is_(False),
        )
        .order_by(Box.name)
    )
    boxes_page = paginate(boxes_stmt)

    # Количество предметов по каждому боксу — один запрос с GROUP BY.
    # Считаем только по боксам, которые видны на текущей странице.
    box_item_counts: dict[int, int] = {}
    if boxes_page.items:
        box_ids = [b.id for b in boxes_page.items]
        counts = db.session.execute(
            db.select(Item.box_id, db.func.count(Item.id))
            .where(
                Item.box_id.in_(box_ids),
                Item.is_deleted.is_(False),
            )
            .group_by(Item.box_id)
        ).all()
        box_item_counts = {box_id: cnt for box_id, cnt in counts}

    # --- Предметы прямо в локации (без бокса, с пагинацией) ---
    items_stmt = (
        db.select(Item)
        .where(
            Item.location_id == location.id,
            Item.box_id.is_(None),
            Item.is_deleted.is_(False),
        )
        .order_by(Item.created_at.desc())
    )
    items_page = paginate(items_stmt)

    return render_template(
        "locations/detail.html",
        location=location,
        boxes_page=boxes_page,
        box_item_counts=box_item_counts,
        items_page=items_page,
    )


@locations_bp.route("/create", methods=["GET", "POST"])
@login_required
def create_location():
    """Создание локации."""
    form = LocationForm()
    if form.validate_on_submit():
        existing = db.session.scalar(
            db.select(Location).where(
                Location.name == form.name.data,
                Location.is_deleted.is_(False),
            )
        )
        if existing:
            flash(f"Локация {form.name.data!r} уже существует.", "danger")
        else:
            location = Location(
                name=form.name.data,
                description=form.description.data or None,
            )
            db.session.add(location)
            db.session.commit()
            flash(f"Локация {location.name!r} создана.", "success")
            return redirect_after_create("locations.list_locations")

    return render_template("locations/create.html", form=form)


@locations_bp.route("/<int:location_id>/edit", methods=["GET", "POST"])
@login_required
def edit_location(location_id: int):
    """Редактирование локации."""
    location = db.get_or_404(Location, location_id)
    if location.is_deleted:
        flash("Локация удалена и не может быть изменена.", "warning")
        return redirect(url_for("locations.list_locations"))

    form = LocationForm(obj=location)
    if form.validate_on_submit():
        existing = db.session.scalar(
            db.select(Location).where(
                Location.name == form.name.data,
                Location.id != location.id,
                Location.is_deleted.is_(False),
            )
        )
        if existing:
            flash(f"Локация {form.name.data!r} уже существует.", "danger")
        else:
            location.name = form.name.data
            location.description = form.description.data or None
            db.session.commit()
            flash(f"Локация {location.name!r} обновлена.", "success")
            return redirect(url_for("locations.list_locations"))

    return render_template("locations/edit.html", form=form, location=location)


@locations_bp.route("/<int:location_id>/delete", methods=["POST"])
@login_required
def delete_location(location_id: int):
    """Мягкое удаление локации (с проверкой привязок)."""
    location = db.get_or_404(Location, location_id)

    boxes_count = db.session.scalar(
        db.select(db.func.count(Box.id)).where(
            Box.location_id == location.id,
            Box.is_deleted.is_(False),
        )
    )
    items_count = db.session.scalar(
        db.select(db.func.count(Item.id)).where(
            Item.location_id == location.id,
            Item.is_deleted.is_(False),
        )
    )

    if boxes_count > 0 or items_count > 0:
        flash(
            f"Нельзя удалить локацию {location.name!r}: "
            f"боксов — {boxes_count}, предметов — {items_count}.",
            "warning",
        )
        return redirect(url_for("locations.list_locations"))

    location.soft_delete()
    db.session.commit()
    flash(f"Локация {location.name!r} удалена.", "info")
    return redirect(url_for("locations.list_locations"))


# ============================================================
# Боксы
# ============================================================


@locations_bp.route("/boxes/")
@login_required
def list_boxes():
    """Список боксов."""
    stmt = (
        db.select(Box)
        .where(Box.is_deleted.is_(False))
        .order_by(Box.location_id, Box.name)
    )
    page = paginate(stmt)
    return render_template("locations/boxes_list.html", page=page)


@locations_bp.route("/boxes/<int:box_id>")
@login_required
def detail_box(box_id: int):
    """
    Содержимое бокса: предметы с коротким описанием.
    Пагинация по 20.
    """
    box = db.get_or_404(Box, box_id)
    if box.is_deleted:
        flash("Бокс удалён.", "warning")
        return redirect(url_for("locations.list_boxes"))

    items_stmt = (
        db.select(Item)
        .where(
            Item.box_id == box.id,
            Item.is_deleted.is_(False),
        )
        .order_by(Item.created_at.desc())
    )
    items_page = paginate(items_stmt)

    return render_template(
        "locations/box_detail.html",
        box=box,
        location=box.location,
        items_page=items_page,
    )


@locations_bp.route("/boxes/create", methods=["GET", "POST"])
@login_required
def create_box():
    """Создание бокса с опциональным фото."""
    form = BoxForm()
    form.location_id.choices = _location_choices()

    if form.validate_on_submit():
        existing = db.session.scalar(
            db.select(Box).where(
                Box.name == form.name.data,
                Box.location_id == form.location_id.data,
                Box.is_deleted.is_(False),
            )
        )
        if existing:
            flash(
                f"Бокс {form.name.data!r} уже существует в этой локации.",
                "danger",
            )
        else:
            # Обработка фото (если загружено)
            photo_rel = None
            thumb_rel = None
            if form.photo.data:
                try:
                    photo_rel, thumb_rel = process_and_save_image(form.photo.data)
                except ImageProcessingError as e:
                    flash(f"Ошибка обработки фото: {e}", "danger")
                    return render_template("locations/box_create.html", form=form)

            box = Box(
                name=form.name.data,
                description=form.description.data or None,
                location_id=form.location_id.data,
                photo_path=photo_rel,
                photo_thumbnail_path=thumb_rel,
            )
            db.session.add(box)
            db.session.commit()
            flash(f"Бокс {box.name!r} создан.", "success")
            return redirect_after_create("locations.list_boxes")

    return render_template("locations/box_create.html", form=form)


@locations_bp.route("/boxes/<int:box_id>/edit", methods=["GET", "POST"])
@login_required
def edit_box(box_id: int):
    """Редактирование бокса с опциональной заменой фото."""
    box = db.get_or_404(Box, box_id)
    if box.is_deleted:
        flash("Бокс удалён и не может быть изменён.", "warning")
        return redirect(url_for("locations.list_boxes"))

    form = BoxForm(obj=box)
    form.location_id.choices = _location_choices()

    if form.validate_on_submit():
        existing = db.session.scalar(
            db.select(Box).where(
                Box.name == form.name.data,
                Box.location_id == form.location_id.data,
                Box.id != box.id,
                Box.is_deleted.is_(False),
            )
        )
        if existing:
            flash(
                f"Бокс {form.name.data!r} уже существует в этой локации.",
                "danger",
            )
        else:
            box.name = form.name.data
            box.description = form.description.data or None
            box.location_id = form.location_id.data

            # Замена фото (если загружено новое)
            if form.photo.data:
                try:
                    new_photo, new_thumb = process_and_save_image(form.photo.data)
                    box.photo_path = new_photo
                    box.photo_thumbnail_path = new_thumb
                except ImageProcessingError as e:
                    flash(f"Ошибка обработки фото: {e}", "danger")
                    return render_template(
                        "locations/box_edit.html", form=form, box=box
                    )

            db.session.commit()
            flash(f"Бокс {box.name!r} обновлён.", "success")
            return redirect(url_for("locations.list_boxes"))

    return render_template("locations/box_edit.html", form=form, box=box)


@locations_bp.route("/boxes/<int:box_id>/delete", methods=["POST"])
@login_required
def delete_box(box_id: int):
    """Мягкое удаление бокса (с проверкой предметов)."""
    box = db.get_or_404(Box, box_id)

    items_count = db.session.scalar(
        db.select(db.func.count(Item.id)).where(
            Item.box_id == box.id,
            Item.is_deleted.is_(False),
        )
    )
    if items_count > 0:
        flash(
            f"Нельзя удалить бокс {box.name!r}: "
            f"в нём {items_count} предмет(ов).",
            "warning",
        )
        return redirect(url_for("locations.list_boxes"))

    box.soft_delete()
    db.session.commit()
    flash(f"Бокс {box.name!r} удалён.", "info")
    return redirect(url_for("locations.list_boxes"))


# ============================================================
# Упаковки
# ============================================================


@locations_bp.route("/packagings/")
@login_required
def list_packagings():
    """Список упаковок."""
    stmt = (
        db.select(Packaging)
        .where(Packaging.is_deleted.is_(False))
        .order_by(Packaging.name)
    )
    page = paginate(stmt)
    return render_template("locations/packagings_list.html", page=page)


@locations_bp.route("/packagings/create", methods=["GET", "POST"])
@login_required
def create_packaging():
    """Создание упаковки."""
    form = PackagingForm()
    if form.validate_on_submit():
        existing = db.session.scalar(
            db.select(Packaging).where(
                Packaging.name == form.name.data,
                Packaging.is_deleted.is_(False),
            )
        )
        if existing:
            flash(f"Упаковка {form.name.data!r} уже существует.", "danger")
        else:
            packaging = Packaging(
                name=form.name.data,
                description=form.description.data or None,
            )
            db.session.add(packaging)
            db.session.commit()
            flash(f"Упаковка {packaging.name!r} создана.", "success")
            return redirect_after_create("locations.list_packagings")

    return render_template("locations/packaging_create.html", form=form)


@locations_bp.route("/packagings/<int:packaging_id>/edit", methods=["GET", "POST"])
@login_required
def edit_packaging(packaging_id: int):
    """Редактирование упаковки."""
    packaging = db.get_or_404(Packaging, packaging_id)
    if packaging.is_deleted:
        flash("Упаковка удалена и не может быть изменена.", "warning")
        return redirect(url_for("locations.list_packagings"))

    form = PackagingForm(obj=packaging)
    if form.validate_on_submit():
        existing = db.session.scalar(
            db.select(Packaging).where(
                Packaging.name == form.name.data,
                Packaging.id != packaging.id,
                Packaging.is_deleted.is_(False),
            )
        )
        if existing:
            flash(f"Упаковка {form.name.data!r} уже существует.", "danger")
        else:
            packaging.name = form.name.data
            packaging.description = form.description.data or None
            db.session.commit()
            flash(f"Упаковка {packaging.name!r} обновлена.", "success")
            return redirect(url_for("locations.list_packagings"))

    return render_template(
        "locations/packaging_edit.html", form=form, packaging=packaging
    )


@locations_bp.route("/packagings/<int:packaging_id>/delete", methods=["POST"])
@login_required
def delete_packaging(packaging_id: int):
    """Мягкое удаление упаковки (с проверкой предметов)."""
    packaging = db.get_or_404(Packaging, packaging_id)

    items_count = db.session.scalar(
        db.select(db.func.count(Item.id)).where(
            Item.packaging_id == packaging.id,
            Item.is_deleted.is_(False),
        )
    )
    if items_count > 0:
        flash(
            f"Нельзя удалить упаковку {packaging.name!r}: "
            f"к ней привязано {items_count} предмет(ов).",
            "warning",
        )
        return redirect(url_for("locations.list_packagings"))

    packaging.soft_delete()
    db.session.commit()
    flash(f"Упаковка {packaging.name!r} удалена.", "info")
    return redirect(url_for("locations.list_packagings"))


# ============================================================
# Вспомогательные функции
# ============================================================


def _location_choices() -> list[tuple[int, str]]:
    """
    Формирует список (id, name) активных локаций для SelectField.

    Вызывается в роутах create_box / edit_box при каждом запросе —
    так список всегда актуален.
    """
    locations = db.session.scalars(
        db.select(Location)
        .where(Location.is_deleted.is_(False))
        .order_by(Location.name)
    ).all()
    return [(loc.id, loc.name) for loc in locations]