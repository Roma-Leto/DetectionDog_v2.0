"""
Blueprint справочника категорий и состояний.

Обе сущности имеют идентичную структуру (name + description),
поэтому CRUD-операции похожи. Объединены в один blueprint.

После создания записи поддерживается редирект обратно в форму
предмета через ?return_to=items.create (см. app/utils/redirects.py).
"""

from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, url_for
from flask_login import login_required

from app.extensions import db
from app.forms import CategoryForm, ConditionForm
from app.models.item import Category, Condition, Item
from app.utils import paginate
from app.utils.redirects import redirect_after_create

categories_bp = Blueprint("categories", __name__, url_prefix="/categories")


# ============================================================
# Категории
# ============================================================


@categories_bp.route("/")
@login_required
def list_categories():
    """Список категорий с пагинацией."""
    stmt = (
        db.select(Category)
        .where(Category.is_deleted.is_(False))
        .order_by(Category.name)
    )
    page = paginate(stmt)
    return render_template("categories/list.html", page=page)


@categories_bp.route("/create", methods=["GET", "POST"])
@login_required
def create_category():
    """
    Создание новой категории.

    При успехе редиректит на items.create, если был ?return_to=items.create,
    иначе — на список категорий.
    """
    form = CategoryForm()
    if form.validate_on_submit():
        existing = db.session.scalar(
            db.select(Category).where(
                Category.name == form.name.data,
                Category.is_deleted.is_(False),
            )
        )
        if existing:
            flash(f"Категория {form.name.data!r} уже существует.", "danger")
        else:
            category = Category(
                name=form.name.data,
                description=form.description.data or None,
            )
            db.session.add(category)
            db.session.commit()
            flash(f"Категория {category.name!r} создана.", "success")
            return redirect_after_create("categories.list_categories")

    return render_template("categories/create.html", form=form)


@categories_bp.route("/<int:category_id>/edit", methods=["GET", "POST"])
@login_required
def edit_category(category_id: int):
    """Редактирование категории."""
    category = db.get_or_404(Category, category_id)
    if category.is_deleted:
        flash("Категория удалена и не может быть изменена.", "warning")
        return redirect(url_for("categories.list_categories"))

    form = CategoryForm(obj=category)
    if form.validate_on_submit():
        existing = db.session.scalar(
            db.select(Category).where(
                Category.name == form.name.data,
                Category.id != category.id,
                Category.is_deleted.is_(False),
            )
        )
        if existing:
            flash(f"Категория {form.name.data!r} уже существует.", "danger")
        else:
            category.name = form.name.data
            category.description = form.description.data or None
            db.session.commit()
            flash(f"Категория {category.name!r} обновлена.", "success")
            return redirect(url_for("categories.list_categories"))

    return render_template("categories/edit.html", form=form, category=category)


@categories_bp.route("/<int:category_id>/delete", methods=["POST"])
@login_required
def delete_category(category_id: int):
    """
    Мягкое удаление категории.

    Не удаляем, если к категории привязаны активные предметы —
    иначе пользователь потеряет доступ к фильтрации.
    """
    category = db.get_or_404(Category, category_id)

    items_count = db.session.scalar(
        db.select(db.func.count(Item.id)).where(
            Item.category_id == category.id,
            Item.is_deleted.is_(False),
        )
    )

    if items_count > 0:
        flash(
            f"Нельзя удалить категорию {category.name!r}: "
            f"к ней привязано {items_count} предмет(ов).",
            "warning",
        )
        return redirect(url_for("categories.list_categories"))

    category.soft_delete()
    db.session.commit()
    flash(f"Категория {category.name!r} удалена.", "info")
    return redirect(url_for("categories.list_categories"))


# ============================================================
# Состояния
# ============================================================


@categories_bp.route("/conditions/")
@login_required
def list_conditions():
    """Список состояний с пагинацией."""
    stmt = (
        db.select(Condition)
        .where(Condition.is_deleted.is_(False))
        .order_by(Condition.name)
    )
    page = paginate(stmt)
    return render_template("categories/conditions_list.html", page=page)


@categories_bp.route("/conditions/create", methods=["GET", "POST"])
@login_required
def create_condition():
    """
    Создание нового состояния.

    При успехе редиректит на items.create, если был ?return_to=items.create,
    иначе — на список состояний.
    """
    form = ConditionForm()
    if form.validate_on_submit():
        existing = db.session.scalar(
            db.select(Condition).where(
                Condition.name == form.name.data,
                Condition.is_deleted.is_(False),
            )
        )
        if existing:
            flash(f"Состояние {form.name.data!r} уже существует.", "danger")
        else:
            condition = Condition(
                name=form.name.data,
                description=form.description.data or None,
            )
            db.session.add(condition)
            db.session.commit()
            flash(f"Состояние {condition.name!r} создано.", "success")
            return redirect_after_create("categories.list_conditions")

    return render_template("categories/condition_create.html", form=form)


@categories_bp.route("/conditions/<int:condition_id>/edit", methods=["GET", "POST"])
@login_required
def edit_condition(condition_id: int):
    """Редактирование состояния."""
    condition = db.get_or_404(Condition, condition_id)
    if condition.is_deleted:
        flash("Состояние удалено и не может быть изменено.", "warning")
        return redirect(url_for("categories.list_conditions"))

    form = ConditionForm(obj=condition)
    if form.validate_on_submit():
        existing = db.session.scalar(
            db.select(Condition).where(
                Condition.name == form.name.data,
                Condition.id != condition.id,
                Condition.is_deleted.is_(False),
            )
        )
        if existing:
            flash(f"Состояние {form.name.data!r} уже существует.", "danger")
        else:
            condition.name = form.name.data
            condition.description = form.description.data or None
            db.session.commit()
            flash(f"Состояние {condition.name!r} обновлено.", "success")
            return redirect(url_for("categories.list_conditions"))

    return render_template("categories/condition_edit.html", form=form, condition=condition)


@categories_bp.route("/conditions/<int:condition_id>/delete", methods=["POST"])
@login_required
def delete_condition(condition_id: int):
    """Мягкое удаление состояния (с проверкой привязки предметов)."""
    condition = db.get_or_404(Condition, condition_id)

    items_count = db.session.scalar(
        db.select(db.func.count(Item.id)).where(
            Item.condition_id == condition.id,
            Item.is_deleted.is_(False),
        )
    )

    if items_count > 0:
        flash(
            f"Нельзя удалить состояние {condition.name!r}: "
            f"к нему привязано {items_count} предмет(ов).",
            "warning",
        )
        return redirect(url_for("categories.list_conditions"))

    condition.soft_delete()
    db.session.commit()
    flash(f"Состояние {condition.name!r} удалено.", "info")
    return redirect(url_for("categories.list_conditions"))