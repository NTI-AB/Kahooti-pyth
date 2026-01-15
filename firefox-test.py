import json, time, hashlib, keyboard, cv2, numpy as np, pyperclip, threading
import os, sys, configparser
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.firefox.options import Options
from webdriver_manager.firefox import GeckoDriverManager

# -------------------------------------------------
# --- Configuration ---
SCAN_INTERVAL = 0.25      # seconds between scans
SCAN_DURATION = 2.0       # total time to scan after answering
# Path to your Firefox profile for persistence
FIREFOX_PROFILE_PATH = r"C:\Users\axel.borjeson\AppData\Roaming\Mozilla\Firefox\Profiles"
# Optional: specify exact profile folder like "abcd1234.selenium"
# FIREFOX_PROFILE_PATH = r"C:\Users\axel.borjeson\AppData\Roaming\Mozilla\Firefox\Profiles\abcd1234.selenium"
# -------------------------------------------------

CACHE_FILE = "kahoot_cache.json"
clipboard_data = {"text": ""}

# -------------------------------------------------
# Clipboard hotkey thread
def clipboard_hotkey():
    while True:
        keyboard.wait("f2")
        if clipboard_data["text"]:
            pyperclip.copy(clipboard_data["text"])
            print("\n📋 Copied current Kahoot question + answers to clipboard!\n")
        else:
            print("\n⚠️ No question loaded yet.\n")

threading.Thread(target=clipboard_hotkey, daemon=True).start()
# -------------------------------------------------

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
def find_default_firefox_profile():
    """Attempt to locate the user's default Firefox profile directory.

    Priority:
    1) profiles.ini Default=1 entry
    2) A directory ending with .default-release
    3) A directory ending with .default
    Returns absolute path or None.
    """
    try:
        if os.name == "nt":
            base_dir = os.path.expandvars(r"%APPDATA%\Mozilla\Firefox")
        elif sys.platform == "darwin":
            base_dir = os.path.expanduser("~/Library/Application Support/Firefox")
        else:
            base_dir = os.path.expanduser("~/.mozilla/firefox")

        ini_path = os.path.join(base_dir, "profiles.ini")
        profiles_root = os.path.join(base_dir, "Profiles")

        # 1) Use profiles.ini if present
        if os.path.isfile(ini_path):
            cp = configparser.ConfigParser()
            cp.read(ini_path)
            for section in cp.sections():
                if section.lower().startswith("profile"):
                    is_default = cp.getboolean(section, "Default", fallback=False)
                    if is_default:
                        rel = cp.getboolean(section, "IsRelative", fallback=True)
                        path_value = cp.get(section, "Path", fallback="")
                        if not path_value:
                            continue
                        prof_path = os.path.join(base_dir, path_value) if rel else path_value
                        if os.path.isdir(prof_path) and os.path.isfile(os.path.join(prof_path, "prefs.js")):
                            return os.path.abspath(prof_path)

        # 2) Fallback: prefer *.default-release, then *.default
        if os.path.isdir(profiles_root):
            candidates = [
                d for d in (os.path.join(profiles_root, x) for x in os.listdir(profiles_root))
                if os.path.isdir(d)
            ]
            for d in candidates:
                if d.endswith(".default-release") and os.path.isfile(os.path.join(d, "prefs.js")):
                    return os.path.abspath(d)
            for d in candidates:
                if d.endswith(".default") and os.path.isfile(os.path.join(d, "prefs.js")):
                    return os.path.abspath(d)

        return None
    except Exception:
        return None

def resolve_profile_path(user_path):
    """Resolve a valid Firefox profile directory based on user_path or defaults.

    - If user_path points to a directory containing prefs.js, use it.
    - Otherwise try to auto-detect the default profile.
    """
    if user_path:
        expanded = os.path.expandvars(user_path)
        if os.path.isdir(expanded) and os.path.isfile(os.path.join(expanded, "prefs.js")):
            return os.path.abspath(expanded)
    return find_default_firefox_profile()

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
    # --- Firefox setup ---
    opts = Options()
    opts.set_preference("browser.startup.page", 1)
    opts.set_preference("browser.startup.homepage", "https://kahoot.it/")
    opts.set_preference("dom.webnotifications.enabled", False)

    # Use saved Firefox profile (auto-detect if not exact dir)
    profile_dir = resolve_profile_path(FIREFOX_PROFILE_PATH)
    if profile_dir:
        print(f"Using Firefox profile: {profile_dir}")
        opts.profile = profile_dir
    else:
        print("Warning: No Firefox profile found; using a temporary profile.")

    driver = webdriver.Firefox(service=Service(GeckoDriverManager().install()), options=opts)
    driver.maximize_window()
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

            # Update clipboard data for F2 copying
            clipboard_data["text"] = (
                f"Kahoot question:\n{question}\n"
                + "\n".join([f"{i+1}. {a}" for i, a in enumerate(answers)])
                + "\n\nReply ONLY with the correct number (1–4)."
            )

            print("\n============================")
            print(f"QUESTION: {question}")
            for i, a in enumerate(answers, 1):
                print(f"{i}. {a}")
            print("============================")
            print("(Press F2 anytime to copy this question + answers to clipboard)\n")

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
