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

# ============================================================
# Категории — маппинг title → категория
# ============================================================


# Словарь: английское название предмета → русская категория.
# Ключи — в нижнем регистре. Матчинг по вхождению ключа в title.
# Категории должны совпадать с app/seed_data.py на нетбуке.
TITLE_TO_CATEGORY: dict[str, str] = {
    # --- Инструменты ---
    "hammer": "Инструменты",
    "screwdriver": "Инструменты",
    "wrench": "Инструменты",
    "pliers": "Инструменты",
    "saw": "Инструменты",
    "chisel": "Инструменты",
    "file": "Инструменты",
    "knife": "Инструменты",
    "clamp": "Инструменты",
    "vice": "Инструменты",
    "tape measure": "Инструменты",
    "ruler": "Инструменты",
    "level": "Инструменты",
    "caliper": "Инструменты",
    "multimeter": "Инструменты",
    "tool": "Инструменты",
    "toolbox": "Инструменты",

    # --- Строительные инструменты ---
    "drill": "Строительные инструменты",
    "jigsaw": "Строительные инструменты",
    "sander": "Строительные инструменты",
    "grinder": "Строительные инструменты",
    "welder": "Строительные инструменты",
    "nail gun": "Строительные инструменты",
    "jackhammer": "Строительные инструменты",
    "circular saw": "Строительные инструменты",

    # --- Строительные материалы ---
    "screw": "Строительные материалы",
    "nail": "Строительные материалы",
    "dowel": "Строительные материалы",
    "bolt": "Строительные материалы",
    "nut": "Строительные материалы",
    "washer": "Строительные материалы",
    "anchor": "Строительные материалы",
    "cement": "Строительные материалы",
    "glue": "Строительные материалы",
    "sealant": "Строительные материалы",
    "silicone": "Строительные материалы",
    "foam": "Строительные материалы",
    "insulation": "Строительные материалы",
    "sandpaper": "Строительные материалы",
    "duct tape": "Строительные материалы",

    # --- Схемотехника / электроника ---
    "battery": "Схемотехника",
    "batteries": "Схемотехника",
    "accumulator": "Схемотехника",
    "resistor": "Схемотехника",
    "capacitor": "Схемотехника",
    "transistor": "Схемотехника",
    "diode": "Схемотехника",
    "microchip": "Схемотехника",
    "arduino": "Схемотехника",
    "raspberry": "Схемотехника",
    "usb cable": "Схемотехника",
    "hdmi cable": "Схемотехника",
    "charger": "Схемотехника",
    "power supply": "Схемотехника",
    "adapter": "Схемотехника",
    "wire": "Схемотехника",
    "cable": "Схемотехника",
    "connector": "Схемотехника",
    "circuit board": "Схемотехника",
    "pcb": "Схемотехника",
    "led": "Схемотехника",

    # --- Электроника / бытовое ---
    "computer mouse": "Схемотехника",
    "mouse": "Схемотехника",
    "keyboard": "Схемотехника",
    "monitor": "Схемотехника",
    "laptop": "Схемотехника",
    "computer": "Схемотехника",
    "router": "Схемотехника",
    "modem": "Схемотехника",
    "hard drive": "Схемотехника",
    "ssd": "Схемотехника",
    "flash drive": "Схемотехника",
    "usb drive": "Схемотехника",
    "phone": "Схемотехника",
    "smartphone": "Схемотехника",
    "tablet": "Схемотехника",
    "headphones": "Схемотехника",
    "earbuds": "Схемотехника",
    "speaker": "Схемотехника",
    "microphone": "Схемотехника",
    "webcam": "Схемотехника",
    "printer": "Схемотехника",
    "scanner": "Схемотехника",

    # --- Одежда ---
    "shirt": "Одежда",
    "t-shirt": "Одежда",
    "tshirt": "Одежда",
    "sweater": "Одежда",
    "hoodie": "Одежда",
    "jacket": "Одежда",
    "coat": "Одежда",
    "pants": "Одежда",
    "jeans": "Одежда",
    "shorts": "Одежда",
    "skirt": "Одежда",
    "dress": "Одежда",
    "suit": "Одежда",
    "sock": "Одежда",
    "socks": "Одежда",
    "gloves": "Одежда",
    "hat": "Одежда",
    "cap": "Одежда",
    "scarf": "Одежда",
    "tie": "Одежда",
    "belt": "Одежда",

    # --- Обувь ---
    "shoe": "Обувь",
    "shoes": "Обувь",
    "boot": "Обувь",
    "boots": "Обувь",
    "sneaker": "Обувь",
    "sneakers": "Обувь",
    "sandal": "Обувь",
    "slipper": "Обувь",
    "slippers": "Обувь",

    # --- Канцелярия ---
    "pen": "Канцелярия",
    "pencil": "Канцелярия",
    "marker": "Канцелярия",
    "notebook": "Канцелярия",
    "notepad": "Канцелярия",
    "book": "Канцелярия",
    "folder": "Канцелярия",
    "stapler": "Канцелярия",
    "scissors": "Канцелярия",
    "eraser": "Канцелярия",
    "sharpener": "Канцелярия",
    "ruler": "Канцелярия",
    "paper clip": "Канцелярия",
    "envelope": "Канцелярия",
    "sticker": "Канцелярия",

    # --- Документы ---
    "document": "Документы",
    "passport": "Документы",
    "certificate": "Документы",
    "diploma": "Документы",
    "contract": "Документы",
    "receipt": "Документы",
    "warranty": "Документы",
    "insurance": "Документы",
    "card": "Документы",

    # --- Медицинское ---
    "medicine": "Медицинское",
    "pill": "Медицинское",
    "pills": "Медицинское",
    "tablet": "Медицинское",
    "syringe": "Медицинское",
    "bandage": "Медицинское",
    "plaster": "Медицинское",
    "thermometer": "Медицинское",
    "tonometer": "Медицинское",
    "vitamin": "Медицинское",

    # --- Аптечка ---
    "first aid kit": "Аптечка/Медицина",
    "iodine": "Аптечка/Медицина",
    "antiseptic": "Аптечка/Медицина",
    "peroxide": "Аптечка/Медицина",

    # --- Химия ---
    "paint": "Химия",
    "varnish": "Химия",
    "solvent": "Химия",
    "thinner": "Химия",
    "acetone": "Химия",
    "bleach": "Химия",
    "detergent": "Химия",
    "cleaner": "Химия",
    "acid": "Химия",
    "alkali": "Химия",
    "shampoo": "Химия",
    "soap": "Химия",
    "perfume": "Химия",
    "deo": "Химия",

    # --- Растения/Животные ---
    "plant": "Растения/Животные",
    "flower": "Растения/Животные",
    "seed": "Растения/Животные",
    "fertilizer": "Растения/Животные",
    "soil": "Растения/Животные",
    "pot": "Растения/Животные",
    "pet": "Растения/Животные",
    "dog": "Растения/Животные",
    "cat": "Растения/Животные",
    "leash": "Растения/Животные",
    "collar": "Растения/Животные",

    # --- Развлечения ---
    "game": "Развлечения",
    "toy": "Развлечения",
    "puzzle": "Развлечения",
    "cards": "Развлечения",
    "chess": "Развлечения",
    "dice": "Развлечения",
    "ball": "Развлечения",
    "fishing": "Развлечения",

    # --- Музыкальные ---
    "guitar": "Музыкальные",
    "piano": "Музыкальные",
    "violin": "Музыкальные",
    "drum": "Музыкальные",
    "flute": "Музыкальные",
    "synthesizer": "Музыкальные",
    "ukulele": "Музыкальные",

    # --- Музыка ---
    "cd": "Музыка",
    "vinyl": "Музыка",
    "cassette": "Музыка",
    "record": "Музыка",

    # --- Для изделий из кожи ---
    "shoe polish": "Для изделий из кожи",
    "leather cream": "Для изделий из кожи",
    "leather brush": "Для изделий из кожи",

    # --- Праздничный ---
    "christmas": "Праздничный",
    "new year": "Праздничный",
    "garland": "Праздничный",
    "tinsel": "Праздничный",
    "ornament": "Праздничный",
    "candle": "Праздничный",
    "balloon": "Праздничный",
    "party": "Праздничный",

    # --- Интерьерные ---
    "picture": "Интерьерные",
    "painting": "Интерьерные",
    "frame": "Интерьерные",
    "vase": "Интерьерные",
    "statue": "Интерьерные",
    "figurine": "Интерьерные",
    "mirror": "Интерьерные",
    "clock": "Интерьерные",
    "rug": "Интерьерные",
    "carpet": "Интерьерные",
    "curtain": "Интерьерные",
    "lamp": "Интерьерные",

    # --- Бытовые ---
    "plate": "Бытовые",
    "cup": "Бытовые",
    "mug": "Бытовые",
    "glass": "Бытовые",
    "fork": "Бытовые",
    "spoon": "Бытовые",
    "knife": "Бытовые",
    "pot": "Бытовые",
    "pan": "Бытовые",
    "kettle": "Бытовые",
    "teapot": "Бытовые",
    "bowl": "Бытовые",
    "towel": "Бытовые",
    "napkin": "Бытовые",
    "bag": "Бытовые",
    "box": "Бытовые",
    "basket": "Бытовые",
    "broom": "Бытовые",
    "mop": "Бытовые",
    "vacuum": "Бытовые",
    "iron": "Бытовые",
    "fan": "Бытовые",
    "heater": "Бытовые",
    "clock": "Бытовые",
    "umbrella": "Бытовые",
    "cigarette": "Бытовые",
    "cigarettes": "Бытовые",
    "lighter": "Бытовые",
    "ashtray": "Бытовые",
    "matches": "Бытовые",
    "flask": "Бытовые",
    "thermos": "Бытовые",
    "bottle": "Бытовые",
    "jar": "Бытовые",
    "container": "Бытовые",
}


def match_category_by_title(
    title: str | None,
    description: str | None = None,
    threshold: float = 0.75,
) -> str | None:
    """
    Определяет категорию по title и (опционально) description.

    Алгоритм:
    1. Нормализуем title.
    2. Ищем точное вхождение ключа словаря в title (сначала длинные ключи).
    3. Если не нашли — fuzzy-матчинг по ключам.
    4. Если всё ещё не нашли — пробуем те же операции на description.
    5. Если не нашли — None (пользователь выберет вручную).

    :param title: короткое название предмета от Moondream
    :param description: описание (опционально, для fallback)
    :param threshold: порог fuzzy-схожести (0..1)
    :return: имя категории или None
    """
    if not title and not description:
        return None

    # 1. Сначала пробуем title
    result = _match_category_in_text(title, threshold)
    if result:
        return result

    # 2. Потом description (только начало — первые 200 символов)
    if description:
        result = _match_category_in_text(description[:200], threshold)
        if result:
            return result

    return None


def _match_category_in_text(
    text: str | None,
    threshold: float,
) -> str | None:
    """
    Ищет категорию в тексте.

    Шаг 1: точное совпадение по СЛОВАМ (не подстроке!),
           чтобы 'cat' не находился в 'medication'.
    Шаг 2: fuzzy-матчинг по ключам.

    Ключи сортируются по длине — длинные фразы приоритетнее
    (например, 'computer mouse' важнее 'mouse').
    """
    if not text:
        return None

    text_norm = _normalize(text)
    if not text_norm:
        return None

    text_words = set(text_norm.split())

    # --- 1. Точное совпадение по словам ---
    # Сортируем ключи по длине (длинные приоритетнее).
    # Для каждого ключа проверяем:
    #   - односложный ключ: должен быть отдельным словом в тексте
    #   - многословный ключ: все его слова должны быть в тексте
    for key in sorted(TITLE_TO_CATEGORY.keys(), key=len, reverse=True):
        key_norm = _normalize(key)
        if not key_norm:
            continue

        key_words = set(key_norm.split())

        # Все слова ключа присутствуют в тексте?
        if key_words and key_words <= text_words:
            return TITLE_TO_CATEGORY[key]

    # --- 2. Fuzzy-матчинг ---
    best_category: str | None = None
    best_score = 0.0

    for key, category in TITLE_TO_CATEGORY.items():
        key_norm = _normalize(key)
        if not key_norm:
            continue

        key_words = set(key_norm.split())
        if key_words and text_words:
            overlap = len(text_words & key_words) / len(key_words)
            score = overlap * 0.9
        else:
            score = SequenceMatcher(None, text_norm, key_norm).ratio()

        if score > best_score:
            best_score = score
            best_category = category

    if best_score >= threshold:
        return best_category

    return None