"""
Формы справочника локаций, боксов и упаковок.

- LocationForm — место хранения (комната, шкаф, полка)
- BoxForm — бокс/коробка (привязан к локации)
- PackagingForm — упаковка (не привязана к иерархии)
"""

from __future__ import annotations

from wtforms import SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, Optional
from flask_wtf.file import FileAllowed, FileField
from flask_wtf import FlaskForm


class LocationForm(FlaskForm):
    """Форма места хранения."""

    name = StringField(
        "Название",
        validators=[
            DataRequired(message="Введите название места."),
            Length(min=1, max=255),
        ],
    )
    description = TextAreaField(
        "Описание",
        validators=[Optional(), Length(max=2000)],
    )
    submit = SubmitField("Сохранить")


class BoxForm(FlaskForm):
    """
    Форма бокса.

    Поле location_id — SelectField, заполняется в роуте
    (choices задаются динамически, в зависимости от того,
    создаём мы новый бокс или редактируем существующий).

    Поле photo — опциональная загрузка фото бокса.
    """

    name = StringField(
        "Название",
        validators=[
            DataRequired(message="Введите название бокса."),
            Length(min=1, max=255),
        ],
    )
    description = TextAreaField(
        "Описание",
        validators=[Optional(), Length(max=2000)],
    )
    location_id = SelectField(
        "Место хранения",
        coerce=int,
        validators=[DataRequired(message="Выберите место хранения.")],
        choices=[],
    )
    photo = FileField(
        "Фотография бокса",
        validators=[
            Optional(),
            FileAllowed(
                ["jpg", "jpeg", "png", "webp", "heic"],
                message="Только изображения: JPG, PNG, WEBP, HEIC.",
            ),
        ],
    )
    submit = SubmitField("Сохранить")


class PackagingForm(FlaskForm):
    """Форма упаковки."""

    name = StringField(
        "Название",
        validators=[
            DataRequired(message="Введите название упаковки."),
            Length(min=1, max=255),
        ],
    )
    description = TextAreaField(
        "Описание",
        validators=[Optional(), Length(max=2000)],
    )
    submit = SubmitField("Сохранить")