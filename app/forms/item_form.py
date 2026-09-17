"""
Формы для предметов.

- ItemForm — базовая форма создания/редактирования
- ItemUploadForm — только загрузка фото для анализа (перед основным созданием)
- AdvancedSearchForm — расширенный поиск (используем на Этапе 5)

SelectField для category/condition/location/box/packaging заполняются
в роутах динамически (choices зависят от текущих данных в БД).
"""

from __future__ import annotations

from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField, FileRequired
from wtforms import (
    BooleanField,
    DateTimeLocalField,
    HiddenField,
    IntegerField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import DataRequired, Length, NumberRange, Optional


# ============================================================
# Основная форма предмета
# ============================================================


class ItemForm(FlaskForm):
    """
    Форма создания/редактирования предмета.

    Поля category_id, condition_id, location_id, box_id, packaging_id —
    SelectField с динамическими choices (заполняются в роуте).
    """

    name = StringField(
        "Название",
        validators=[
            DataRequired(message="Введите название предмета."),
            Length(min=1, max=255, message="От 1 до 255 символов."),
        ],
    )
    description = TextAreaField(
        "Описание",
        validators=[
            Optional(),
            Length(max=5000, message="Не более 5000 символов."),
        ],
    )
    quantity = IntegerField(
        "Количество",
        validators=[
            DataRequired(message="Укажите количество."),
            NumberRange(min=1, max=99999, message="От 1 до 99999."),
        ],
        default=1,
    )

    category_id = SelectField(
        "Категория",
        coerce=int,
        validators=[DataRequired(message="Выберите категорию.")],
        choices=[],
    )
    condition_id = SelectField(
        "Состояние",
        coerce=int,
        validators=[DataRequired(message="Выберите состояние.")],
        choices=[],
    )
    location_id = SelectField(
        "Место хранения",
        coerce=int,
        validators=[DataRequired(message="Выберите место хранения.")],
        choices=[],
    )
    box_id = SelectField(
        "Бокс",
        coerce=int,
        validators=[Optional()],
        choices=[],  # добавим "— не указан —" в роуте
    )
    packaging_id = SelectField(
        "Упаковка",
        coerce=int,
        validators=[Optional()],
        choices=[],
    )

    photo = FileField(
        "Фотография",
        validators=[
            Optional(),
            FileAllowed(
                ["jpg", "jpeg", "png", "webp", "heic"],
                message="Только изображения: JPG, PNG, WEBP, HEIC.",
            ),
        ],
    )

    submit = SubmitField("Сохранить")


# ============================================================
# Форма загрузки фото для анализа
# ============================================================


class ItemPhotoAnalyzeForm(FlaskForm):
    """
    Форма для шага «Загрузить фото → получить автозаполнение».

    Отдельная от ItemForm, чтобы не валидировать остальные поля
    до того, как пользователь их увидит.
    """

    photo = FileField(
        "Фотография",
        validators=[
            FileRequired(message="Выберите файл."),
            FileAllowed(
                ["jpg", "jpeg", "png", "webp", "heic"],
                message="Только изображения: JPG, PNG, WEBP, HEIC.",
            ),
        ],
    )
    submit = SubmitField("Распознать")


# ============================================================
# Расширенный поиск (используем на Этапе 5)
# ============================================================


class AdvancedSearchForm(FlaskForm):
    """
    Форма расширенного поиска.

    Все поля опциональны — пустая форма возвращает все предметы.
    Фильтр по упаковке убран (используется редко), вместо него — бокс.
    """

    class Meta:
        # Отключаем CSRF для GET-форм (поиск)
        csrf = False

    q = StringField(
        "Поиск по названию/описанию",
        validators=[Optional(), Length(max=255)],
    )

    date_from = DateTimeLocalField(
        "Дата с (включительно)",
        format="%Y-%m-%dT%H:%M",
        validators=[Optional()],
    )
    date_to = DateTimeLocalField(
        "Дата по (включительно)",
        format="%Y-%m-%dT%H:%M",
        validators=[Optional()],
    )

    category_id = SelectField("Категория", coerce=int, validators=[Optional()], choices=[])
    condition_id = SelectField("Состояние", coerce=int, validators=[Optional()], choices=[])
    location_id = SelectField("Место", coerce=int, validators=[Optional()], choices=[])
    box_id = SelectField("Бокс", coerce=int, validators=[Optional()], choices=[])

    has_photo = BooleanField("Только с фото", default=False)
    case_sensitive = BooleanField("Учитывать регистр", default=False)

    per_page = SelectField(
        "Записей на странице",
        coerce=int,
        choices=[(20, "20"), (50, "50"), (100, "100")],
        default=20,
        validators=[Optional()],
    )

    submit = SubmitField("Найти")
    reset = SubmitField("Сбросить")

class BulkActionForm(FlaskForm):
    """
    Форма массовых операций над предметами.

    Используется в расширенном поиске: пользователь отмечает предметы
    чекбоксами, выбирает действие (перенести/удалить) и цель, нажимает
    «Применить». Форма отправляется на /items/bulk/preview.

    ID предметов передаются НЕ через эту форму, а как набор
    чекбоксов с именем item_ids. Flask читает их через
    request.form.getlist("item_ids") — это работает без JS.
    """

    action = SelectField(
        "Действие",
        choices=[
            ("move", "Перенести"),
            ("delete", "Удалить"),
        ],
        validators=[DataRequired(message="Выберите действие.")],
        default="move",
    )

    target_location_id = SelectField(
        "Новая локация",
        coerce=int,
        validators=[Optional()],
        choices=[],
    )

    target_box_id = SelectField(
        "Новый бокс (опционально)",
        coerce=int,
        validators=[Optional()],
        choices=[],
    )

    submit = SubmitField("Применить")