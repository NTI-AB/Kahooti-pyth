import time
import json
import base64
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from PIL import Image

# ================= CONFIG =================

OLLAMA_URL = "http://localhost:11434/api/chat"
OLLAMA_MODEL = "llava:7b"

# =========================================


def log(msg):
    print(f"[BOT] {msg}", flush=True)


# ---------- IMAGE HELPERS ----------

def resize_to_512(src, dst):
    img = Image.open(src).convert("RGB")
    w, h = img.size
    scale = 512 / min(w, h)
    img = img.resize((int(w * scale), int(h * scale)), Image.BICUBIC)
    img.save(dst, format="PNG")


def extract_question_image(driver):
    imgs = driver.find_elements(By.TAG_NAME, "img")

    best_src = None
    best_area = 0

    for img in imgs:
        try:
            src = img.get_attribute("src")
            size = img.size
            area = size["width"] * size["height"]
            if src and area > best_area:
                best_src = src
                best_area = area
        except:
            pass

    if not best_src:
        return None

    log("Found HTML image, downloading it")
    r = requests.get(best_src, timeout=10)
    with open("q_raw.png", "wb") as f:
        f.write(r.content)

    resize_to_512("q_raw.png", "q.png")
    return "q.png"


def screenshot_fallback(driver):
    log("No suitable HTML image found, taking screenshot")
    driver.save_screenshot("q_raw.png")
    resize_to_512("q_raw.png", "q.png")
    return "q.png"


# ---------- OLLAMA (FIXED) ----------

def ask_llava(question, answers, image_path, max_tokens=80):
    log("Sending question + answers + image to LLaVA")

    labeled = [f"{chr(65+i)}) {a}" for i, a in enumerate(answers)]
    prompt = (
        "This is a multiple-choice Kahoot question.\n"
        "The image may be helpful or may be decorative.\n"
        "Only use the image if it is clearly relevant.\n\n"
        f"Question:\n{question}\n\n"
        "Options:\n" + "\n".join(labeled) + "\n\n"
        "Reply ONLY with A, B, C, or D."
    )

    with open(image_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode()

    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {
                "role": "user",
                "content": prompt,
                "images": [img_b64]
            }
        ],
        "options": {
            "temperature": 0.4,
            "num_predict": max_tokens
        },
        "stream": False   # IMPORTANT FOR IMAGES
    }

    r = requests.post(OLLAMA_URL, json=payload, timeout=60)
    r.raise_for_status()

    data = r.json()
    text = data["message"]["content"]

    log(f"Raw AI response: {text!r}")
    return text.strip()


def parse_answer(text):
    text = text.upper()
    for c in ["A", "B", "C", "D"]:
        if c in text:
            return c
    return None


# ---------- SELENIUM ACTIONS ----------

def get_answer_buttons(driver):
    buttons = driver.find_elements(By.TAG_NAME, "button")
    answer_buttons = []

    for b in buttons:
        try:
            if b.text.strip():
                answer_buttons.append(b)
        except:
            pass

    return answer_buttons


def click_answer(driver, letter):
    idx = {"A": 0, "B": 1, "C": 2, "D": 3}[letter]
    buttons = get_answer_buttons(driver)

    log("Detected answer options:")
    for i, b in enumerate(buttons):
        log(f"  {i}: {b.text!r}")

    if idx >= len(buttons):
        raise RuntimeError("Not enough answer buttons detected")

    log(f"Clicking answer {letter}")
    buttons[idx].click()


def click_confidence(driver):
    time.sleep(0.2)
    btns = driver.find_elements(
        By.CSS_SELECTOR,
        '[data-functional-selector="confidence-strength-level-1"]'
    )
    if btns:
        btns[0].click()
        log("Clicked confidence (extra points)")


# ---------- MAIN LOOP ----------

def main():
    driver = webdriver.Chrome()
    driver.get("https://kahoot.it")

    log("Bot started. Waiting for questions...")
    last_question = ""

    while True:
        try:
            q_els = driver.find_elements(
                By.CSS_SELECTOR,
                '[data-functional-selector="block-title"]'
            )

            if not q_els:
                time.sleep(0.2)
                continue

            question = q_els[0].text.strip()

            if not question or question == last_question:
                time.sleep(0.2)
                continue

            last_question = question
            log(f"New question detected: {question!r}")

            # Collect answers
            ans_els = driver.find_elements(
                By.CSS_SELECTOR,
                '[data-functional-selector^="question-choice-text-"]'
            )
            answers = [a.text.strip() for a in ans_els if a.text.strip()]

            log(f"Detected answers: {answers}")

            if len(answers) < 2:
                log("Not enough answers detected, skipping")
                time.sleep(1)
                continue

            # Image
            img = extract_question_image(driver)
            if not img:
                img = screenshot_fallback(driver)

            # AI
            ai_text = ask_llava(question, answers, img)
            answer = parse_answer(ai_text)

            if not answer:
                log("AI did not return a valid answer, skipping")
                time.sleep(1)
                continue

            log(f"Got response to answer {answer}")

            click_answer(driver, answer)
            click_confidence(driver)

            log("Answer submitted\n")
            time.sleep(1.5)

        except KeyboardInterrupt:
            log("Stopped by user")
            break
        except Exception as e:
            log(f"Unexpected error: {e}")
            time.sleep(1)

    driver.quit()


if __name__ == "__main__":
    main()
