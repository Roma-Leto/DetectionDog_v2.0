"""
Постобработка ответов Moondream.

Функции:
- clean_title: чистит название предмета
- clean_description: чистит описание (убирает преамбулы, фон, зацикливания, кириллицу)
- extract_labels: извлекает надписи (CAPS-слова, коды, текст в кавычках)
- build_short_description: собирает компактное описание из структурированных полей
- match_condition: сопоставление состояния (eng→rus) + fuzzy
- parse_quantity: извлечение числа из ответа

Категории НЕ матчим через модель — она путается.
Пользователь выбирает вручную (позже добавим словарь синонимов).
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
    - убирает кириллицу
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
    1. Обрезает зацикливания Moondream.
    2. Убирает типичные преамбулы.
    3. Убирает фразы про фон и поверхности.
    4. Полностью удаляет кириллицу.
    5. Чистит артефакты после удаления.
    6. Обрезает по границе предложения.
    """
    if not raw:
        return None

    text = raw.strip()

    # --- 1. Обрезаем зацикливания ---
    text = re.sub(r"(.)\1{7,}.*$", "", text, flags=re.DOTALL)
    text = re.sub(r"(.{2,3})\1{4,}.*$", "", text, flags=re.DOTALL)
    text = text.strip()

    # --- 2. Убираем преамбулы ---
    prefixes = [
        r"^the (main\s+)?object (in the center of (this|the) photo\s+)?is\s+(a|an|the)?\s*",
        r"^the image (shows|contains|depicts)\s+(a|an|the)?\s*",
        r"^i see\s+(a|an|the)?\s*",
        r"^a\s+\w+\s+(desk|table|floor|surface|background|shelf|ground)\s+(holds|has|contains|shows)\s+(a|an|the)?\s*",
        r",?\s*against\s+(a|an|the)?\s*[a-z]+\s+(background|wall)\.?",
        r",?\s*with\s+(a|an|the)?\s*blurred\s+[a-z]+\s+in\s+the\s+background\.?",
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

    # --- 4. Удаляем кириллицу ---
    text = re.sub(r"[\u0400-\u04FF]+", "", text)

    # --- 5. Чистим артефакты ---
    text = re.sub(r'["\'«»]\s*["\'«»]', "", text)
    text = re.sub(r'["\'«»](\s*[.,;:])', r"\1", text)
    text = re.sub(r",\s*,", ",", text)
    text = re.sub(r",\s*\.", ".", text)
    text = re.sub(r"\.{2,}", ".", text)
    text = re.sub(r"\s+([.,;:!?])", r"\1", text)
    text = re.sub(r"\s+", " ", text)
    text = text.strip().rstrip(",;: ")

    # --- 6. Обрезка ---
    if len(text) > 500:
        cut = text[:500].rfind(".")
        if cut > 100:
            text = text[:cut + 1]
        else:
            text = text[:500].rsplit(" ", 1)[0] + "…"

    if len(text) > max_chars:
        text = text[:max_chars].rsplit(" ", 1)[0] + "…"

    return text or None


def extract_labels(raw: str | None, max_labels: int = 8) -> list[str]:
    """
    Извлекает «надписи» из caption модели:
    - слова в кавычках: "HIGH VOLTAGE"
    - слова ЗАГЛАВНЫМИ буквами: ALKALINE, USB
    - короткие коды: 12V, 23A, L1028, MS21/MN21

    Дедупликация: если фраза «HIGH VOLTAGE» уже есть, отдельные
    слова «HIGH» и «VOLTAGE» не добавляем.
    """
    if not raw:
        return []

    labels: list[str] = []
    seen: set[str] = set()

    def _add(label: str) -> None:
        """Добавляет метку, если её ещё нет (по нормализованному виду)."""
        label = label.strip().strip("-/")
        if len(label) < 2:
            return
        # Только латиница, цифры, дефис, слэш
        if not re.match(r"^[A-Za-z0-9\-/ ]+$", label):
            return
        key = label.lower()
        if key in seen:
            return
        # Пропускаем метку, если она — часть уже добавленной фразы
        for existing in seen:
            if label.lower() in existing and label.lower() != existing:
                return
            if existing in label.lower() and existing != label.lower():
                # Новая метка длиннее существующей — заменяем
                labels[:] = [x for x in labels if x.lower() != existing]
                seen.discard(existing)
                break
        labels.append(label)
        seen.add(key)

    # 1. Текст в кавычках (приоритет — самые «полные» метки)
    for match in re.finditer(r'"([^"]{2,40})"', raw):
        _add(match.group(1))

    # 2. Слова ЗАГЛАВНЫМИ (2+ символа)
    for match in re.finditer(r"\b([A-Z][A-Z0-9\-/]{1,20})\b", raw):
        _add(match.group(1))

    # 3. Коды вида 12V, 23A, 220V, L1028
    for match in re.finditer(r"\b(\d+[A-Z]{1,4}|\d{3,}\w*)\b", raw):
        _add(match.group(1))

    return labels[:max_labels]


def build_short_description(
    quantity: int,
    title: str | None,
    labels: list[str] | None = None,
    full_caption: str | None = None,
) -> str | None:
    """
    Собирает описание из структурированных полей + полный caption модели.

    Формат:
        3 × pack of batteries. Надписи: HIGH VOLTAGE, ALKALINE, 23A, 12V.

        three Alkaline batteries neatly arranged in a row on a gray countertop...

    Первая строка — наша структура (английский title + CAPS-надписи).
    Вторая — полный текст от Moondream (для перевода в будущем).
    """
    if not title:
        return None

    if quantity and quantity > 1:
        header = f"{quantity} × {title}"
    else:
        header = title

    if labels:
        header += f". Надписи: {', '.join(labels)}."

    if full_caption:
        caption_clean = full_caption.strip()
        return f"{header}\n\n{caption_clean}"

    return header


# ============================================================
# Состояние
# ============================================================


def match_condition(raw: str | None, threshold: float = 0.6) -> str | None:
    """Сопоставляет состояние с CONDITIONS."""
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
    """Извлекает число из ответа модели."""
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