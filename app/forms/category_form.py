"""
Формы справочника категорий и состояний.

Обе сущности имеют одинаковую структуру (name + description),
поэтому формы почти идентичны. Вынесены в один модуль для
удобства — при желании можно объединить в базовый класс.
"""

from __future__ import annotations

from wtforms import StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, Optional

from flask_wtf import FlaskForm


class CategoryForm(FlaskForm):
    """Форма категории предмета."""

    name = StringField(
        "Название",
        validators=[
            DataRequired(message="Введите название категории."),
            Length(min=1, max=255, message="От 1 до 255 символов."),
        ],
    )
    description = TextAreaField(
        "Описание",
        validators=[
            Optional(),
            Length(max=2000, message="Не более 2000 символов."),
        ],
    )
    submit = SubmitField("Сохранить")


class ConditionForm(FlaskForm):
    """Форма состояния предмета."""

    name = StringField(
        "Название",
        validators=[
            DataRequired(message="Введите название состояния."),
            Length(min=1, max=255),
        ],
    )
    description = TextAreaField(
        "Описание",
        validators=[
            Optional(),
            Length(max=2000),
        ],
    )
    submit = SubmitField("Сохранить")