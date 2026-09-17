"""
Blueprint secnot — личные заметки.

Доступ только по прямому URL /secnot (нет ссылок в навигации).
Требуется авторизация.

Заметки хранятся в JSON-файле secnot.json в корне проекта.
Файл не коммитится (см. .gitignore).
"""

from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, url_for
from flask_login import login_required

from app.forms.secnot_form import NoteForm
from app.services import secnot_service

secnot_bp = Blueprint("secnot", __name__, url_prefix="/secnot")


@secnot_bp.route("/")
@login_required
def list_notes():
    """Список заметок."""
    notes = secnot_service.list_notes()
    return render_template("secnot/list.html", notes=notes)


@secnot_bp.route("/create", methods=["GET", "POST"])
@login_required
def create_note():
    """Создание заметки."""
    form = NoteForm()
    if form.validate_on_submit():
        note = secnot_service.create_note(
            title=form.title.data or "",
            content=form.content.data,
        )
        flash(f"Заметка {'«' + note['title'] + '»' if note['title'] else 'без названия'} создана.", "success")
        return redirect(url_for("secnot.list_notes"))

    return render_template("secnot/create.html", form=form)


@secnot_bp.route("/<note_id>/edit", methods=["GET", "POST"])
@login_required
def edit_note(note_id: str):
    """Редактирование заметки."""
    note = secnot_service.get_note(note_id)
    if not note:
        flash("Заметка не найдена.", "warning")
        return redirect(url_for("secnot.list_notes"))

    form = NoteForm(data={
        "title": note.get("title", ""),
        "content": note.get("content", ""),
    })

    if form.validate_on_submit():
        updated = secnot_service.update_note(
            note_id=note_id,
            title=form.title.data or "",
            content=form.content.data,
        )
        if updated:
            flash("Заметка обновлена.", "success")
        else:
            flash("Не удалось обновить заметку.", "danger")
        return redirect(url_for("secnot.list_notes"))

    return render_template("secnot/edit.html", form=form, note=note)


@secnot_bp.route("/<note_id>/delete", methods=["POST"])
@login_required
def delete_note(note_id: str):
    """Удаление заметки."""
    if secnot_service.delete_note(note_id):
        flash("Заметка удалена.", "info")
    else:
        flash("Заметка не найдена.", "warning")

    return redirect(url_for("secnot.list_notes"))