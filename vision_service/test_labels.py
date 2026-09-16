"""Проверка extract_labels и build_short_description."""

from app.services import category_matcher as cm

# Тест extract_labels
text = 'HIGH VOLTAGE 12V "ALKALINE" and L1028, MS21/MN21'
labels = cm.extract_labels(text)
print("extract_labels:", labels)
print()

# Тест build_short_description
desc = cm.build_short_description(
    quantity=3,
    title="pack of batteries",
    labels=["HIGH VOLTAGE", "ALKALINE", "23A", "12V"],
    full_caption="three Alkaline batteries neatly arranged in a row on a gray countertop.",
)
print("build_short_description:")
print(repr(desc))
print()
print("Rendered:")
print(desc)