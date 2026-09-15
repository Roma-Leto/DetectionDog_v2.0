"""
Пакет WTForms. Импортирует все формы для удобства:

    from app.forms import LoginForm
"""

from app.forms.auth_forms import LoginForm, RegisterForm, UserCreateForm

__all__ = [
    "LoginForm",
    "RegisterForm",
    "UserCreateForm",
]