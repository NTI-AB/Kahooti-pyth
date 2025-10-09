import json, time, hashlib, keyboard, cv2, numpy as np
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

# -------------------------------------------------
# --- Configuration ---
SCAN_INTERVAL = 0.25      # seconds between scans
SCAN_DURATION = 2.0       # total time to scan after answering
# -------------------------------------------------

CACHE_FILE = "kahoot_cache.json"

def load_cache():
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_cache(cache):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)

def make_key(question, answers):
    key_text = question.strip().lower() + "|" + "|".join(sorted(a.strip().lower() for a in answers))
    return hashlib.sha1(key_text.encode()).hexdigest()

# -------------------------------------------------
def count_green_checks(driver):
    """Screenshot bottom-right corner and count green check icons."""
    driver.save_screenshot("frame.png")
    img = cv2.imread("frame.png")
    if img is None:
        return 0

    h, w, _ = img.shape
    crop = img[int(h * 0.6):h, int(w * 0.6):w]
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)

    lower = np.array([45, 80, 80])
    upper = np.array([90, 255, 255])
    mask = cv2.inRange(hsv, lower, upper)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    valid = [c for c in contours if 200 < cv2.contourArea(c) < 5000]
    return len(valid)
# -------------------------------------------------

def main():
    opts = Options()
    opts.add_argument("--start-maximized")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)
    driver.get("https://kahoot.it")

    print("🟣 Join Kahoot manually.")
    input("Press Enter when a question is visible...")

    cache = load_cache()
    print(f"Loaded {len(cache)} cached questions.\n")

    last_q = ""

    while True:
        try:
            q_el = driver.find_element(By.CSS_SELECTOR, '[data-functional-selector="block-title"]')
            question = q_el.text.strip()
            if not question or question == last_q:
                time.sleep(0.2)
                continue

            ans_els = driver.find_elements(By.CSS_SELECTOR, '[data-functional-selector^="question-choice-text-"]')
            answers = [a.text.strip() for a in ans_els if a.text.strip()]
            if not answers:
                time.sleep(0.2)
                continue

            print("\n============================")
            print(f"QUESTION: {question}")
            for i, a in enumerate(answers, 1):
                print(f"{i}. {a}")
            print("============================")

            q_key = make_key(question, answers)

            # --- cached question ---
            if q_key in cache:
                corr = cache[q_key]["correct"]
                print(f"⚡ Cached answer found: {corr}")
                for b in driver.find_elements(By.CSS_SELECTOR, "button.choice__Choice-sc-ym3b8f-4"):
                    if corr.lower() in b.text.lower():
                        b.click()
                        print("✅ Clicked cached correct answer.")
                        break
                last_q = question
                continue

            # --- manual selection ---
            print("Press 1–4 to answer, or F3 to skip.")
            idx = None
            while idx is None:
                # Ignore normal 1–4 inputs while Shift is held (for manual correction)
                if keyboard.is_pressed("shift"):
                    time.sleep(0.05)
                    continue

                if keyboard.is_pressed("1"): idx = 0
                elif keyboard.is_pressed("2"): idx = 1
                elif keyboard.is_pressed("3"): idx = 2
                elif keyboard.is_pressed("4"): idx = 3
                elif keyboard.is_pressed("f3"):
                    print("⏭️  Skipping question.")
                    idx = -1
                time.sleep(0.05)

            if idx == -1:
                last_q = question
                continue

            buttons = driver.find_elements(By.CSS_SELECTOR, "button.choice__Choice-sc-ym3b8f-4")
            if 0 <= idx < len(buttons):
                before = count_green_checks(driver)
                buttons[idx].click()
                print(f"🖱️ Clicked: {answers[idx]}")

                # --- scan loop for checkmark detection ---
                correct = None
                before = count_green_checks(driver)
                for _ in range(int(SCAN_DURATION / SCAN_INTERVAL)):
                    time.sleep(SCAN_INTERVAL)
                    after = count_green_checks(driver)
                    if after > before:
                        correct = answers[idx]
                        print("✅ Correct answer detected (checkmark counter):", correct)
                        cache[q_key] = {"question": question, "answers": answers, "correct": correct}
                        save_cache(cache)
                        print("💾 Saved to cache.")
                        break

                # --- manual correction if wrong ---
                if not correct:
                    print("❌ No checkmark detected — if you know the correct answer, press Shift+1–4 now.")
                    correction = None
                    wait_start = time.time()
                    while time.time() - wait_start < 3:  # 3s to give correction
                        if keyboard.is_pressed("shift+1"): correction = 0
                        elif keyboard.is_pressed("shift+2"): correction = 1
                        elif keyboard.is_pressed("shift+3"): correction = 2
                        elif keyboard.is_pressed("shift+4"): correction = 3
                        if correction is not None:
                            break
                        time.sleep(0.05)

                    if correction is not None and 0 <= correction < len(answers):
                        correct = answers[correction]
                        print(f"✅ Manual correction received: {correct}")
                        cache[q_key] = {"question": question, "answers": answers, "correct": correct}
                        save_cache(cache)
                        print("💾 Saved to cache.")
                    else:
                        print("ℹ️ No correction provided. Moving on without saving.")

            # --- wait for next question ---
            last_q = question
            print("Waiting for next question...")
            while True:
                try:
                    newq = driver.find_element(By.CSS_SELECTOR, '[data-functional-selector="block-title"]').text.strip()
                    if newq and newq != last_q:
                        print("--- Next question detected ---")
                        break
                except Exception:
                    pass
                time.sleep(0.2)

        except KeyboardInterrupt:
            break
        except Exception as e:
            print("Error:", e)
            time.sleep(0.2)

    driver.quit()
    save_cache(cache)
    print("✅ Session ended, cache saved.")

# -------------------------------------------------
if __name__ == "__main__":
    main()
