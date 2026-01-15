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

# ==========================================


def resize_to_512(src, dst):
    img = Image.open(src).convert("RGB")
    w, h = img.size
    scale = 512 / min(w, h)
    img = img.resize((int(w * scale), int(h * scale)), Image.BICUBIC)
    img.save(dst, format="PNG")


def ask_llava(prompt, image_path, max_tokens=60):
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
    with requests.post(OLLAMA_URL, json=payload, stream=True) as r:
        for line in r.iter_lines():
            if not line:
                continue
            data = json.loads(line)
            if "message" in data:
                text += data["message"]["content"]

    return text.strip()


def extract_question_image(driver):
    imgs = driver.find_elements(By.CSS_SELECTOR, '[data-functional-selector="media-container__media-image"]')
    if not imgs:
        return None

    src = imgs[0].get_attribute("src")
    if not src:
        return None

    r = requests.get(src, timeout=10)
    with open("q_raw.png", "wb") as f:
        f.write(r.content)

    resize_to_512("q_raw.png", "q.png")
    return "q.png"


def screenshot_fallback(driver):
    driver.save_screenshot("q_raw.png")
    resize_to_512("q_raw.png", "q.png")
    return "q.png"


def parse_answer(text):
    text = text.upper()
    for c in ["A", "B", "C", "D"]:
        if c in text:
            return c
    return None


def click_answer(driver, letter):
    idx = {"A": 0, "B": 1, "C": 2, "D": 3}[letter]
    btn = driver.find_element(By.CSS_SELECTOR, f'[data-functional-selector="answer-{idx}"]')
    btn.click()


def click_confidence(driver):
    time.sleep(0.2)
    btn = driver.find_element(By.CSS_SELECTOR, '[data-functional-selector="confidence-strength-level-1"]')
    btn.click()


def wait_for_question(driver):
    while True:
        try:
            driver.find_element(By.CSS_SELECTOR, '[data-functional-selector="block-title"]')
            return
        except:
            time.sleep(0.1)


def main():
    driver = webdriver.Chrome()
    driver.get("https://kahoot.it")

    print("Waiting for questions...")

    while True:
        wait_for_question(driver)

        img = extract_question_image(driver)
        if not img:
            img = screenshot_fallback(driver)

        answer_text = ask_llava(PROMPT, img)
        answer = parse_answer(answer_text)

        if answer:
            click_answer(driver, answer)
            click_confidence(driver)

        time.sleep(2)  # wait for next question


if __name__ == "__main__":
    main()
