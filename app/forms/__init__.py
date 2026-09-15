"""
Пакет WTForms. Импортирует все формы для удобства:

    from app.forms import LoginForm, CategoryForm
"""

from app.forms.auth_forms import LoginForm, RegisterForm, UserCreateForm
from app.forms.category_form import CategoryForm, ConditionForm
from app.forms.location_form import BoxForm, LocationForm, PackagingForm

__all__ = [
    # auth
    "LoginForm",
    "RegisterForm",
    "UserCreateForm",
    # categories
    "CategoryForm",
    "ConditionForm",
    # locations
    "LocationForm",
    "BoxForm",
    "PackagingForm",
]