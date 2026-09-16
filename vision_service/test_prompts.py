"""
Тест разных промптов для Moondream — какой даёт лучший title/description.
Запуск: uv run python test_prompts.py
"""

import torch
from PIL import Image
from transformers import AutoModelForCausalLM, AutoTokenizer
from app.config import get_settings

s = get_settings()

print("Loading model...")
tokenizer = AutoTokenizer.from_pretrained(
    s.model_id, revision=s.model_revision, cache_dir=str(s.model_cache_dir)
)
model = AutoModelForCausalLM.from_pretrained(
    s.model_id,
    revision=s.model_revision,
    trust_remote_code=True,
    torch_dtype=torch.float16,
    device_map="cuda:0",
    cache_dir=str(s.model_cache_dir),
)

img = Image.open("test_photo2.jpg").convert("RGB")
emb = model.encode_image(img)

prompts = [
    ("CONFIG prompt_title", s.prompt_title),
    ("Short: what object", "What object is in the center of this photo?"),
    ("Simple: What is this", "What is this?"),
    ("Name only", "Name the main object in this photo in one or two words."),
    ("List objects", "List the objects you see in this photo, comma-separated."),
    ("Identify", "Identify the main item. Answer with a short noun phrase."),
]

for label, prompt in prompts:
    print()
    print("=" * 60)
    print(f"[{label}]")
    print(f"PROMPT: {prompt}")
    try:
        answer = model.answer_question(emb, prompt, tokenizer)
        print(f"ANSWER: {answer!r}")
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}")

# Description test
print()
print("=" * 60)
print("[CONFIG prompt_description]")
print(f"PROMPT: {s.prompt_description}")
try:
    answer = model.answer_question(emb, s.prompt_description, tokenizer)
    print(f"ANSWER: {answer!r}")
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")

# Caption (старый способ)
print()
print("=" * 60)
print("[caption - old method]")
try:
    result = model.caption([img], tokenizer=tokenizer, length="short")
    print(f"ANSWER: {result!r}")
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")