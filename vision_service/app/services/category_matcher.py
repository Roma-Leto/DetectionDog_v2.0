"""
Постобработка ответов Moondream.

Функции:
- clean_title: чистит название предмета
- clean_description: чистит описание (убирает преамбулы, фон, зацикливания, кириллицу)
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
# Title
# ============================================================


def clean_title(raw: str | None, max_chars: int = 60) -> str | None:
    """
    Чистит title:
    - убирает типичные преамбулы Moondream
    - отбрасывает бренды (одно слово заглавными буквами)
    - убирает кириллицу (модель на ней галлюцинирует)
    - обрезает до max_chars по границе слова
    """
    if not raw:
        return None

    text = raw.strip()

    # Отбрасываем бренд-only: одно слово, все буквы заглавные, 3-15 символов
    if text.isupper() and 3 <= len(text) <= 15 and text.isalpha():
        return None

    # Убираем типичные преамбулы
    prefixes = [
        r"^the (main\s+)?object (in the center of (this|the) photo\s+)?is\s+(a|an|the)?\s*",
        r"^the image (shows|contains|depicts)\s+(a|an|the)?\s*",
        r"^i see\s+(a|an|the)?\s*",
        r"^this is\s+(a|an|the)?\s*",
        r"^it is\s+(a|an|the)?\s*",
        r"^there is\s+(a|an|the)?\s*",
        r"^a photo of\s+(a|an|the)?\s*",
        r"^an? image of\s+(a|an|the)?\s*",
    ]
    for pattern in prefixes:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)

    # Убираем артикли в начале
    text = re.sub(r"^(a|an|the)\s+", "", text, flags=re.IGNORECASE)

    # Убираем кириллицу (Moondream на ней зацикливается и галлюцинирует)
    text = re.sub(r"[\u0400-\u04FF]+", "", text)

    # Схлопываем пробелы и убираем висящую пунктуацию
    text = re.sub(r"\s+", " ", text).strip()
    text = text.strip(".!?,;:")

    # Обрезаем по границе слова
    if len(text) > max_chars:
        truncated = text[:max_chars]
        if " " in truncated:
            truncated = truncated.rsplit(" ", 1)[0]
        text = truncated

    text = text.strip()
    return text or None


# ============================================================
# Description
# ============================================================


def clean_description(raw: str | None, max_chars: int = 2000) -> str | None:
    """
    Чистит description:

    1. Обрезает зацикливания Moondream (периодические повторы).
    2. Убирает типичные преамбулы.
    3. Убирает фразы про фон и поверхности.
    4. Полностью удаляет кириллицу (модель на ней галлюцинирует).
    5. Чистит артефакты после удаления (двойные кавычки, запятые, пробелы).
    6. Обрезает по границе предложения или слова.
    """
    if not raw:
        return None

    text = raw.strip()

    # --- 1. Обрезаем зацикливания ---
    # Один символ 8+ раз подряд
    text = re.sub(r"(.)\1{7,}.*$", "", text, flags=re.DOTALL)
    # Периодический паттерн 2-3 символа, повторённый 5+ раз
    text = re.sub(r"(.{2,3})\1{4,}.*$", "", text, flags=re.DOTALL)
    text = text.strip()

    # --- 2. Убираем преамбулы ---
    prefixes = [
        r"^the (main\s+)?object (in the center of (this|the) photo\s+)?is\s+(a|an|the)?\s*",
        r"^the image (shows|contains|depicts)\s+(a|an|the)?\s*",
        r"^i see\s+(a|an|the)?\s*",
        r"^a\s+\w+\s+(desk|table|floor|surface|background|shelf|ground)\s+(holds|has|contains|shows)\s+(a|an|the)?\s*",
    ]
    for pattern in prefixes:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)

    # --- 3. Убираем фразы про фон ---
    background_patterns = [
        r",?\s*are arranged (in a grid )?on (a|an|the)?\s*[a-z]+\s+background\.?",
        r",?\s*(arranged|placed|set|lying|sitting) on (a|an|the)?\s*[a-z]+\s+(desk|table|floor|surface|background)\.?",
        r",?\s*on (a|an|the)?\s+[a-z]+\s+(desk|table|floor|surface|background)\.?",
    ]
    for pattern in background_patterns:
        text = re.sub(pattern, ".", text, flags=re.IGNORECASE)

    # --- 4. Удаляем кириллицу полностью ---
    # Диапазон Unicode 0400-04FF — кириллица. Удаляем все вхождения.
    text = re.sub(r"[\u0400-\u04FF]+", "", text)

    # --- 5. Чистим артефакты после удаления ---
    # Пустые кавычки: "" или '' или " "
    text = re.sub(r'["\'«»]\s*["\'«»]', "", text)
    # Висящие открытые кавычки: "text (без закрывающей)
    text = re.sub(r'["\'«»](\s*[.,;:])', r"\1", text)
    # Двойные запятые
    text = re.sub(r",\s*,", ",", text)
    # Запятая перед точкой
    text = re.sub(r",\s*\.", ".", text)
    # Двойные точки
    text = re.sub(r"\.{2,}", ".", text)
    # Пробел перед пунктуацией
    text = re.sub(r"\s+([.,;:!?])", r"\1", text)
    # Множественные пробелы
    text = re.sub(r"\s+", " ", text)
    # Обрезаем висящую пунктуацию в конце
    text = text.strip().rstrip(",;: ")

    # --- 6. Финальная обрезка ---
    # Если осталось больше 500 символов — обрезаем по последней точке
    if len(text) > 500:
        cut = text[:500].rfind(".")
        if cut > 100:
            text = text[:cut + 1]
        else:
            text = text[:500].rsplit(" ", 1)[0] + "…"

    if len(text) > max_chars:
        text = text[:max_chars].rsplit(" ", 1)[0] + "…"

    return text or None


# ============================================================
# Состояние
# ============================================================


def match_condition(raw: str | None, threshold: float = 0.6) -> str | None:
    """
    Сопоставляет состояние с CONDITIONS.

    Сначала пробует англо-русские алиасы, потом fuzzy-матчинг.
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

    word_to_num = {
        "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
        "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
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