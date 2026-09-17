"""
Формы для страницы secnot (личные заметки).
"""

from __future__ import annotations

from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, Optional


class NoteForm(FlaskForm):
    """
    Форма заметки.

    Поле title — опциональное. content — обязательное,
    иначе заметка бессмысленна.
    """

    title = StringField(
        "Заголовок",
        validators=[
            Optional(),
            Length(max=200, message="Не более 200 символов."),
        ],
    )
    content = TextAreaField(
        "Содержимое",
        validators=[
            DataRequired(message="Введите содержимое заметки."),
            Length(max=10000, message="Не более 10000 символов."),
        ],
    )
    submit = SubmitField("Сохранить")