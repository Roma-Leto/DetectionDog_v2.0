"""
Формы аутентификации и управления пользователями.

WTForms + Flask-WTF: валидация полей, CSRF-защита, рендеринг
через Jinja2-макросы.
"""

from __future__ import annotations

from wtforms import BooleanField, PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired, EqualTo, Length, Regexp

from flask_wtf import FlaskForm


class LoginForm(FlaskForm):
    """Форма входа в систему."""

    username = StringField(
        "Имя пользователя",
        validators=[
            DataRequired(message="Введите имя пользователя."),
            Length(min=3, max=64, message="От 3 до 64 символов."),
        ],
    )
    password = PasswordField(
        "Пароль",
        validators=[
            DataRequired(message="Введите пароль."),
        ],
    )
    remember_me = BooleanField("Запомнить меня", default=True)
    submit = SubmitField("Войти")


class RegisterForm(FlaskForm):
    """
    Форма регистрации.

    По умолчанию регистрация закрыта — только админ создаёт
    пользователей через UserCreateForm. Эта форма оставлена
    на случай, если позже решите открыть регистрацию.
    """

    username = StringField(
        "Имя пользователя",
        validators=[
            DataRequired(message="Введите имя пользователя."),
            Length(min=3, max=64),
            Regexp(
                r"^[a-zA-Z0-9_.-]+$",
                message="Только латиница, цифры, _, ., -",
            ),
        ],
    )
    password = PasswordField(
        "Пароль",
        validators=[
            DataRequired(message="Введите пароль."),
            Length(min=8, message="Минимум 8 символов."),
        ],
    )
    password_confirm = PasswordField(
        "Повторите пароль",
        validators=[
            DataRequired(message="Повторите пароль."),
            EqualTo("password", message="Пароли не совпадают."),
        ],
    )
    submit = SubmitField("Зарегистрироваться")


class UserCreateForm(FlaskForm):
    """
    Форма создания пользователя администратором.

    Отличается от RegisterForm отсутствием подтверждения пароля
    (админ вводит пароль один раз и сообщает пользователю).
    """

    username = StringField(
        "Имя пользователя",
        validators=[
            DataRequired(message="Введите имя пользователя."),
            Length(min=3, max=64),
            Regexp(
                r"^[a-zA-Z0-9_.-]+$",
                message="Только латиница, цифры, _, ., -",
            ),
        ],
    )
    password = PasswordField(
        "Пароль",
        validators=[
            DataRequired(message="Введите пароль."),
            Length(min=8, message="Минимум 8 символов."),
        ],
    )
    is_admin = BooleanField("Администратор", default=False)
    submit = SubmitField("Создать")