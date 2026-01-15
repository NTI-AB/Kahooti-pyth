import os
from google import genai
from google.genai import types

# =========================================================
# CONFIG
# =========================================================

MODEL_TEXT = os.getenv("GEMINI_TEXT_MODEL", "models/gemini-2.5-flash")
MODEL_IMAGE = os.getenv("GEMINI_IMAGE_MODEL", MODEL_TEXT)
KEY_FILE = "gemini_key.txt"

# =========================================================
# CLIENT SETUP
# =========================================================

_client = None


def _load_key_file():
    try:
        with open(KEY_FILE, "r", encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        return ""


def _get_client():
    global _client
    if _client is not None:
        return _client

    env_key = os.getenv("GEMINI_API_KEY")
    if env_key:
        _client = genai.Client()
        return _client

    file_key = _load_key_file()
    if not file_key:
        raise RuntimeError("Missing GEMINI_API_KEY or gemini_key.txt")

    _client = genai.Client(api_key=file_key)
    return _client

# =========================================================
# RESPONSE HANDLING
# =========================================================


def _extract_text(response):
    text = getattr(response, "text", None)
    if text:
        return text

    candidates = getattr(response, "candidates", None) or []
    for cand in candidates:
        content = getattr(cand, "content", None)
        if not content:
            continue
        parts = getattr(content, "parts", None) or []
        for part in parts:
            if isinstance(part, str) and part.strip():
                return part
            part_text = getattr(part, "text", None)
            if part_text:
                return part_text
            if isinstance(part, dict):
                part_text = part.get("text")
                if part_text:
                    return part_text
        content_text = getattr(content, "text", None)
        if content_text:
            return content_text

    return ""


def _generate(model, contents, config):
    client = _get_client()
    return client.models.generate_content(
        model=model,
        contents=contents,
        config=config,
    )


def _config_for(temperature, max_output_tokens):
    return types.GenerateContentConfig(
        temperature=temperature,
        max_output_tokens=max_output_tokens,
        thinking_config=types.ThinkingConfig(thinking_budget=0),
    )

# =========================================================
# STAGE 1 — TEXT vs IMAGE CLASSIFIER
# =========================================================


def ask_gemini_needs_image(question, answers):
    labeled = [f"{chr(65+i)}) {a}" for i, a in enumerate(answers)]

    prompt = (
        "You will be given a multiple-choice question.\n"
        "Decide whether the question REQUIRES seeing an image to answer correctly.\n\n"
        "Reply IMAGE if the image is required.\n"
        "Reply TEXT if the image is NOT required.\n"
        "Reply with ONLY one word: IMAGE or TEXT.\n\n"
        f"Question:\n{question}\n\n"
        "Options:\n" + "\n".join(labeled)
    )

    response = _generate(
        MODEL_TEXT,
        prompt,
        _config_for(temperature=0.0, max_output_tokens=5),
    )

    return _extract_text(response).strip().upper() == "IMAGE"

# =========================================================
# STAGE 2 — ANSWER (TEXT ONLY)
# =========================================================


def answer_text_only(question, answers):
    labeled = [f"{chr(65+i)}) {a}" for i, a in enumerate(answers)]

    prompt = (
        "This is a multiple-choice question.\n"
        "Choose the correct answer.\n"
        "Reply ONLY with A, B, C, or D.\n\n"
        f"Question:\n{question}\n\n"
        "Options:\n" + "\n".join(labeled)
    )

    response = _generate(
        MODEL_TEXT,
        prompt,
        _config_for(temperature=0.2, max_output_tokens=10),
    )

    return _extract_text(response).strip()

# =========================================================
# STAGE 3 — ANSWER (WITH IMAGE)
# =========================================================


def answer_with_image(question, answers, image_path):
    labeled = [f"{chr(65+i)}) {a}" for i, a in enumerate(answers)]

    with open(image_path, "rb") as f:
        img_bytes = f.read()

    prompt = (
        "This is a multiple-choice question.\n"
        "The image may be helpful or decorative.\n"
        "Only use the image if it is relevant.\n"
        "Choose the correct answer.\n"
        "Reply ONLY with A, B, C, or D.\n\n"
        f"Question:\n{question}\n\n"
        "Options:\n" + "\n".join(labeled)
    )

    response = _generate(
        MODEL_IMAGE,
        [
            prompt,
            types.Part.from_bytes(data=img_bytes, mime_type="image/png"),
        ],
        _config_for(temperature=0.2, max_output_tokens=10),
    )

    return _extract_text(response).strip()

# =========================================================
# PUBLIC ENTRY POINT (USED BY main.py)
# =========================================================


def ask_gemini(question, answers, image_path=None):
    """
    Returns raw model text (expected: A / B / C / D)
    """

    if image_path is None:
        return answer_text_only(question, answers)
    return answer_with_image(question, answers, image_path)
