import time
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from PIL import Image, UnidentifiedImageError
import requests

from gemini_client import ask_gemini
from gemini_client import ask_gemini_needs_image

# =========================================================

def log(msg):
    print(f"[BOT] {msg}", flush=True)

# =========================================================
# IMAGE HANDLING
# =========================================================

def resize_to_512(src, dst):
    try:
        img = Image.open(src)
        img.verify()          # validate file
        img = Image.open(src).convert("RGB")
    except UnidentifiedImageError:
        raise RuntimeError("Downloaded file is not a valid image")

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

# =========================================================
# SELENIUM ACTIONS
# =========================================================

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
        '[data-functional-selector^="confidence-strength-level-"]'
    )
    if btns:
        def level(btn):
            sel = btn.get_attribute("data-functional-selector") or ""
            match = re.search(r"(\d+)$", sel)
            return int(match.group(1)) if match else 0

        btn = max(btns, key=level)
        sel = btn.get_attribute("data-functional-selector") or "confidence-strength"
        btn.click()
        log(f"Clicked confidence ({sel})")
        return

    for b in driver.find_elements(By.TAG_NAME, "button"):
        try:
            text = b.text.strip()
            if re.search(r"\b(50|75|100)\b", text):
                b.click()
                log(f"Clicked confidence (text {text!r})")
                return
        except Exception:
            pass

# =========================================================
# MAIN LOOP
# =========================================================

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

            # ---- collect answers ----
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

            # ---- ask Gemini (TEXT vs IMAGE decision) ----
            needs_img = False
            try:
                needs_img = ask_gemini_needs_image(question, answers)
            except Exception as e:
                log(f"Image decision failed, defaulting to TEXT: {e}")

            img = None

            if needs_img:
                log("Gemini requested image")
                try:
                    img = extract_question_image(driver)
                    if not img:
                        img = screenshot_fallback(driver)
                except Exception as e:
                    log(f"Image extraction failed, continuing without image: {e}")
                    img = None

            # ---- answer ----
            ai_text = ask_gemini(question, answers, img) or ""
            ai_text = ai_text.strip().upper()

            match = re.search(r"\b([ABCD])\b", ai_text)
            answer = match.group(1) if match else None

            if not answer:
                log(f"Invalid AI response: {ai_text!r}")
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
