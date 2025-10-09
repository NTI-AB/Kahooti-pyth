import time, os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

# -------------------------------------------------
CHATGPT_URL = "https://chat.openai.com/"
HTML_SAVE = "chatgpt_page.html"
WAIT_TIME = 10  # seconds to let the page fully load
# -------------------------------------------------

def main():
    # --- Launch Chrome ---
    opts = Options()
    opts.add_argument("--start-maximized")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)

    # --- Open ChatGPT page ---
    print(f"Opening {CHATGPT_URL} ...")
    driver.get(CHATGPT_URL)
    print(f"Waiting {WAIT_TIME}s for page to load (or for you to dismiss any prompts)...")
    time.sleep(WAIT_TIME)

    # --- Premade question ---
    question = "Solve the quadratic equation 3x^2 - 6x + 12 = 0"
    answers = ["x = 2 ± 3i", "x = 1 ± 2i", "x = 2", "x = 0"]

    print("\nPremade question:")
    print(question)
    for i, a in enumerate(answers, 1):
        print(f"{i}. {a}")

    # --- Save full HTML for inspection ---
    html = driver.page_source
    with open(HTML_SAVE, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\n✅ Saved full page HTML as '{HTML_SAVE}'.")
    print("Please send that file so I can analyze where the message box lives.")

    input("\nPress Enter to close the browser once it’s done rendering...")
    driver.quit()

# -------------------------------------------------
if __name__ == "__main__":
    main()
