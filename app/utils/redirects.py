"""
Утилиты для безопасных редиректов.

Используется при сценариях «пользователь ушёл создать справочник
и должен вернуться обратно в форму». Мы не принимаем произвольный URL
из query-параметра (open redirect — уязвимость), а разрешаем только
заранее известные endpoint'ы.
"""

from __future__ import annotations

from flask import redirect, request, url_for


# Разрешённые значения return_to → endpoint.
# Если пользователь передал return_to, которого нет в этом списке,
# используется fallback — безопасный редирект на список.
ALLOWED_RETURN_TO: dict[str, str] = {
    "items.create": "items.create",
    "items.list": "items.list_items",
}


def redirect_after_create(fallback_endpoint: str):
    """
    Возвращает redirect на endpoint из ?return_to=..., если он разрешён.

    Иначе — на fallback_endpoint.

    :param fallback_endpoint: имя endpoint'а для редиректа по умолчанию
                              (например, 'locations.list_packagings')
    :return: flask.Response (redirect)
    """
    return_to = request.args.get("return_to", "").strip()

    target = ALLOWED_RETURN_TO.get(return_to)
    if target:
        return redirect(url_for(target))

    return redirect(url_for(fallback_endpoint))