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

PROMPT = """
This is a multiple-choice Kahoot question.
The image may be helpful or may be decorative.
Only use the image if it is clearly relevant.
Choose the best answer.
Reply ONLY with A, B, C, or D.
""".strip()

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

    best = None
    best_area = 0

    for img in imgs:
        try:
            src = img.get_attribute("src")
            size = img.size
            area = size["width"] * size["height"]
            if src and area > best_area:
                best = src
                best_area = area
        except:
            pass

    if not best:
        return None

    log("Found HTML image, downloading it")
    r = requests.get(best, timeout=10)
    with open("q_raw.png", "wb") as f:
        f.write(r.content)

    resize_to_512("q_raw.png", "q.png")
    return "q.png"


def screenshot_fallback(driver):
    log("No suitable HTML image found, taking screenshot")
    driver.save_screenshot("q_raw.png")
    resize_to_512("q_raw.png", "q.png")
    return "q.png"


# ---------- OLLAMA ----------

def ask_llava(prompt, image_path, max_tokens=80):
    log("Sending prompt + image to LLaVA")

    with open(image_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode()

    payload = {
        "model": OLLAMA_MODEL,
        "messages": [{
            "role": "user",
            "content": prompt,
            "images": [img_b64]
        }],
        "options": {
            "temperature": 0.4,
            "num_predict": max_tokens
        },
        "stream": True
    }

    text = ""
    with requests.post(OLLAMA_URL, json=payload, stream=True, timeout=60) as r:
        for line in r.iter_lines():
            if not line:
                continue
            data = json.loads(line)
            if "message" in data and "content" in data["message"]:
                text += data["message"]["content"]

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
            t = b.text.strip()
            if t:
                answer_buttons.append(b)
        except:
            pass

    return answer_buttons


def click_answer(driver, letter):
    idx = {"A": 0, "B": 1, "C": 2, "D": 3}[letter]
    buttons = get_answer_buttons(driver)

    log("Detected answer buttons:")
    for i, b in enumerate(buttons):
        log(f"  {i}: {b.text!r}")

    if idx >= len(buttons):
        raise RuntimeError("Not enough answer buttons detected")

    log(f"Clicking answer {letter}")
    buttons[idx].click()


def click_confidence(driver):
    time.sleep(0.2)
    try:
        btn = driver.find_element(
            By.CSS_SELECTOR,
            '[data-functional-selector="confidence-strength-level-1"]'
        )
        btn.click()
        log("Clicked confidence (extra points)")
    except:
        log("Confidence screen not found, skipping")


# ---------- MAIN LOOP ----------

def main():
    driver = webdriver.Chrome()
    driver.get("https://kahoot.it")

    log("Waiting for Kahoot questions...")
    last_question = ""

    while True:
        try:
            q_el = driver.find_element(
                By.CSS_SELECTOR,
                '[data-functional-selector="block-title"]'
            )
            question = q_el.text.strip()

            if not question or question == last_question:
                time.sleep(0.2)
                continue

            last_question = question
            log(f"New question detected: {question!r}")

            # --- Image ---
            img = extract_question_image(driver)
            if not img:
                img = screenshot_fallback(driver)

            # --- AI ---
            ai_text = ask_llava(PROMPT, img)
            answer = parse_answer(ai_text)

            if not answer:
                log("AI did not return a valid answer, skipping")
                time.sleep(1)
                continue

            log(f"Got response to answer: {answer}")

            # --- Click ---
            click_answer(driver, answer)
            click_confidence(driver)

            log("Answer submitted, waiting for next question\n")
            time.sleep(2)

        except KeyboardInterrupt:
            log("Stopped by user")
            break
        except Exception as e:
            log(f"Error: {e}")
            time.sleep(1)

    driver.quit()


if __name__ == "__main__":
    main()
