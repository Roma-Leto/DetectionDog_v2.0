"""
Сопоставление «сырых» ответов Moondream с нашими справочниками.

Moondream не знает про наши категории и состояния. Он возвращает
свободный текст. Мы матчим его на список известных значений
через нормализацию + fuzzy matching.

Нормализация:
- приведение к нижнему регистру
- замена ё → е
- удаление пунктуации и лишних пробелов

Fuzzy matching через difflib.SequenceMatcher (без внешних зависимостей).
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher

# ============================================================
# Справочники (должны совпадать с app/seed_data.py на нетбуке)
# ============================================================

CATEGORIES: list[str] = [
    "Строительные инструменты",
    "Строительные материалы",
    "Праздничный",
    "Схемотехника",
    "Одежда",
    "Обувь",
    "Инструменты",
    "Документы",
    "Канцелярия",
    "Бытовые",
    "Интерьерные",
    "Растения/Животные",
    "Развлечения",
    "Разное",
    "Химия",
    "Медицинское",
    "Для изделий из кожи",
    "Музыкальные",
    "Музыка",
    "Аптечка/Медицина",
]

CONDITIONS: list[str] = [
    "новый",
    "б/у",
    "сломанный",
]


# ============================================================
# Публичные функции
# ============================================================


def match_category(raw: str | None, threshold: float = 0.55) -> str | None:
    """
    Ищет наиболее подходящую категорию из CATEGORIES.

    :param raw: сырой ответ модели (может содержать лишний текст)
    :param threshold: минимальный коэффициент схожести (0..1)
    :return: имя категории или None, если ничего похожего нет
    """
    return _best_match(raw, CATEGORIES, threshold)


def match_condition(raw: str | None, threshold: float = 0.6) -> str | None:
    """
    Ищет состояние из CONDITIONS.

    Дополнительно распознаёт английские варианты
    (new / used / broken), потому что Moondream может ответить
    по-английски, несмотря на русский промпт.
    """
    if not raw:
        return None

    # Англо-русский словарик
    raw_norm = _normalize(raw)
    aliases = {
        "new": "новый",
        "brand new": "новый",
        "unused": "новый",
        "used": "б/у",
        "second hand": "б/у",
        "secondhand": "б/у",
        "worn": "б/у",
        "broken": "сломанный",
        "damaged": "сломанный",
        "faulty": "сломанный",
    }

    # Точное совпадение по alias
    for eng, rus in aliases.items():
        if eng in raw_norm:
            return rus

    # Иначе — fuzzy по CONDITION
    return _best_match(raw, CONDITIONS, threshold)


def clean_title(raw: str | None, max_words: int = 5) -> str | None:
    """
    Чистит title: убирает служебные фразы, ограничивает длину.

    Moondream часто возвращает «This is a hammer» или
    «На фото изображён молоток». Мы убираем такие префиксы.
    """
    if not raw:
        return None

    text = raw.strip()

    # Убираем частые префиксы
    prefixes = [
        r"^(this is|it is|there is|i see|the photo shows|the image shows)\s+(a|an|the)?\s*",
        r"^(на фото|на изображении|на картинке)\s+(изображён|изображен|показан|виден|находится)?\s*",
        r"^(это|здесь)\s+",
    ]
    for pattern in prefixes:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)

    # Убираем финальную точку
    text = text.rstrip(".!?,;:")

    # Обрезаем по словам
    words = text.split()
    if len(words) > max_words:
        text = " ".join(words[:max_words])

    text = text.strip()
    return text or None


def clean_description(raw: str | None, max_chars: int = 2000) -> str | None:
    """Чистит описание: strip, обрезка длины."""
    if not raw:
        return None
    text = raw.strip()
    if len(text) > max_chars:
        text = text[:max_chars].rsplit(" ", 1)[0] + "…"
    return text or None


def parse_quantity(raw: str | None, default: int = 1) -> int:
    """
    Извлекает число из ответа модели.

    Примеры:
        "3"            → 3
        "3 шт."        → 3
        "I see 5 items" → 5
        "один"          → 1
        "abc"          → default
    """
    if not raw:
        return default

    # Ищем первую цифру или последовательность цифр
    match = re.search(r"\d+", raw)
    if match:
        try:
            n = int(match.group())
            return n if n >= 1 else default
        except ValueError:
            pass

    # Русские числительные (только до 10)
    word_to_num = {
        "один": 1, "одна": 1, "одно": 1,
        "два": 2, "две": 2,
        "три": 3, "четыре": 4, "пять": 5,
        "шесть": 6, "семь": 7, "восемь": 8,
        "девять": 9, "десять": 10,
    }
    raw_lower = raw.lower()
    for word, num in word_to_num.items():
        if word in raw_lower:
            return num

    return default


# ============================================================
# Приватные функции
# ============================================================


def _normalize(text: str) -> str:
    """
    Нормализует текст для сравнения:
    - нижний регистр
    - ё → е
    - удаление пунктуации
    - схлопывание пробелов
    """
    text = text.lower()
    text = text.replace("ё", "е")
    text = re.sub(r"[^\w\s/]", " ", text)  # сохраняем / для «Растения/Животные»
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _best_match(
    raw: str | None,
    candidates: list[str],
    threshold: float,
) -> str | None:
    """
    Ищет наиболее похожего кандидата.

    Алгоритм:
    1. Если raw пустой → None.
    2. Нормализуем raw и всех кандидатов.
    3. Для каждого кандидата считаем:
       a) Точное вхождение: если кандидат содержится в raw → 1.0
       b) SequenceMatcher.ratio() → 0..1
    4. Возвращаем лучшего, если его score >= threshold.
    """
    if not raw:
        return None

    raw_norm = _normalize(raw)
    if not raw_norm:
        return None

    best: str | None = None
    best_score = 0.0

    for candidate in candidates:
        cand_norm = _normalize(candidate)

        # 1. Точное вхождение
        if cand_norm and cand_norm in raw_norm:
            score = 1.0
        else:
            # 2. Fuzzy
            score = SequenceMatcher(None, raw_norm, cand_norm).ratio()

            # Дополнительно: проверяем совпадение слов
            raw_words = set(raw_norm.split())
            cand_words = set(cand_norm.split())
            if cand_words and raw_words:
                word_overlap = len(raw_words & cand_words) / len(cand_words)
                score = max(score, word_overlap * 0.9)

        if score > best_score:
            best_score = score
            best = candidate

    if best_score >= threshold:
        return best
    return None