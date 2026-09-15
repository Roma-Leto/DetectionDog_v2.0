"""
Утилита пагинации для SQLAlchemy-запросов.

Использует встроенную пагинацию Flask-SQLAlchemy (db.paginate),
но с нашими дефолтами: 20 элементов на страницу, параметры из
конфига, безопасное ограничение max_per_page.
"""

from __future__ import annotations

from typing import Any, TypeVar

from flask import current_app, request
from sqlalchemy import Select

from app.extensions import db

T = TypeVar("T")


def paginate(
    stmt: Select,
    *,
    page: int | None = None,
    per_page: int | None = None,
    max_per_page: int = 100,
    error_out: bool = False,
):
    """
    Пагинация SQLAlchemy-запроса.

    :param stmt: SQLAlchemy Select (db.select(...))
    :param page: номер страницы (по умолчанию — из ?page=N или 1)
    :param per_page: элементов на странице (по умолчанию — из конфига)
    :param max_per_page: ограничение сверху (защита от ?per_page=10000)
    :param error_out: если True — 404 при выходе за границы,
                      если False — возвращает пустую страницу
    :return: flask_sqlalchemy.pagination.Pagination
    """
    if page is None:
        page = request.args.get("page", 1, type=int)
    if per_page is None:
        per_page = current_app.config.get("ITEMS_PER_PAGE", 20)

    return db.paginate(
        stmt,
        page=page,
        per_page=per_page,
        max_per_page=max_per_page,
        error_out=error_out,
    )