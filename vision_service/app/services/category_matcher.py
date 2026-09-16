"""
Постобработка ответов Moondream.

Функции:
- clean_title: обрезка названия до первого предложения + 60 символов
- clean_description: обрезка описания до 2000 символов
- match_condition: сопоставление состояния (eng→rus) + fuzzy
- parse_quantity: извлечение числа из ответа

Категории НЕ матчим — модель их путает, пользователь выбирает сам.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher


# Справочник состояний (совпадает с app/seed_data.py на нетбуке)
CONDITIONS: list[str] = [
    "новый",
    "б/у",
    "сломанный",
]


# ============================================================
# Title / Description
# ============================================================


def clean_title(raw: str | None, max_chars: int = 60) -> str | None:
    """
    Чистит название предмета.

    Moondream может ответить:
    - «hammer»                    → «hammer»
    - «A hammer.»                 → «hammer»
    - «The main object is a book» → «book» (обрезка префикса)
    - «A hammer with a wooden...» → «A hammer with a wooden...» (обрезка до 60 символов)

    Не обрезаем по словам — лучше короткая незаконченная фраза,
    чем потеря смысла. Обрезаем только по:
    - первому предложению (точка, !, ?)
    - длине 60 символов (по границе слова)
    """
    if not raw:
        return None

    text = raw.strip()

    # Убираем частые префиксы-обёртки
    prefixes = [
        r"^(this is|it is|there is|i see|the main object is|the object is|the photo shows|the image shows)\s+(a|an|the)?\s*",
        r"^(this appears to be|it appears to be)\s+(a|an|the)?\s*",
    ]
    for pattern in prefixes:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)

    # Берём первое предложение
    first_sentence = re.split(r"[.!?]\s", text, maxsplit=1)[0]
    text = first_sentence.strip().rstrip(".!?,;:")

    # Обрезаем по 60 символов, если нужно
    if len(text) > max_chars:
        truncated = text[:max_chars]
        # Откатываемся до последнего пробела
        if " " in truncated:
            truncated = truncated.rsplit(" ", 1)[0]
        text = truncated

    text = text.strip()
    return text or None


def clean_description(raw: str | None, max_chars: int = 2000) -> str | None:
    """Чистит описание: strip + обрезка длины."""
    if not raw:
        return None
    text = raw.strip()
    if len(text) > max_chars:
        text = text[:max_chars].rsplit(" ", 1)[0] + "…"
    return text or None


# ============================================================
# Состояние
# ============================================================


def match_condition(raw: str | None, threshold: float = 0.6) -> str | None:
    """
    Сопоставляет состояние с CONDITIONS.

    Сначала пробует англо-русские алиасы (Moondream отвечает
    по-английски), потом fuzzy-матчинг по русским названиям.
    """
    if not raw:
        return None

    raw_norm = _normalize(raw)

    aliases = {
        "new": "новый",
        "brand new": "новый",
        "unused": "новый",
        "sealed": "новый",
        "used": "б/у",
        "second hand": "б/у",
        "secondhand": "б/у",
        "worn": "б/у",
        "old": "б/у",
        "broken": "сломанный",
        "damaged": "сломанный",
        "faulty": "сломанный",
        "defective": "сломанный",
    }

    for eng, rus in aliases.items():
        if eng in raw_norm:
            return rus

    return _best_match(raw, CONDITIONS, threshold)


# ============================================================
# Количество
# ============================================================


def parse_quantity(raw: str | None, default: int = 1) -> int:
    """
    Извлекает число из ответа модели.

    Примеры:
        "3"              → 3
        "3 items"        → 3
        "I see 5 items"  → 5
        "one"            → 1
        "abc"            → default
    """
    if not raw:
        return default

    match = re.search(r"\d+", raw)
    if match:
        try:
            n = int(match.group())
            return n if n >= 1 else default
        except ValueError:
            pass

    # Английские числительные (1-10)
    word_to_num = {
        "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
        "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
        # Русские — на случай, если модель ответит по-русски
        "один": 1, "одна": 1, "одно": 1, "два": 2, "две": 2,
        "три": 3, "четыре": 4, "пять": 5, "шесть": 6,
        "семь": 7, "восемь": 8, "девять": 9, "десять": 10,
    }
    raw_lower = raw.lower()
    for word, num in word_to_num.items():
        if re.search(rf"\b{word}\b", raw_lower):
            return num

    return default


# ============================================================
# Приватные функции
# ============================================================


def _normalize(text: str) -> str:
    """Нормализация: lower, ё→е, убрать пунктуацию, схлопнуть пробелы."""
    text = text.lower()
    text = text.replace("ё", "е")
    text = re.sub(r"[^\w\s/]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _best_match(
    raw: str | None,
    candidates: list[str],
    threshold: float,
) -> str | None:
    """Fuzzy-матчинг по списку кандидатов."""
    if not raw:
        return None

    raw_norm = _normalize(raw)
    if not raw_norm:
        return None

    best: str | None = None
    best_score = 0.0

    for candidate in candidates:
        cand_norm = _normalize(candidate)

        if cand_norm and cand_norm in raw_norm:
            score = 1.0
        else:
            score = SequenceMatcher(None, raw_norm, cand_norm).ratio()

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