"""Проверка match_category_by_title."""

from app.services.category_matcher import match_category_by_title

tests = [
    ("pack of batteries", None),
    ("computer mouse", None),
    ("hammer", None),
    ("glass ashtray", None),
    ("box of medication", "medicine"),
    ("cigarette pack", None),
    ("guitar", None),
    ("box of pills", None),
    ("wooden table", None),
    ("unknown object xyz", None),
]

for title, desc in tests:
    result = match_category_by_title(title=title, description=desc)
    print(f"{title!r:35} -> {result!r}")