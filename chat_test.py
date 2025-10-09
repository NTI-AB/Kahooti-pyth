import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# === Config ===
CHAT_URL = "https://chat.openai.com/"

# Premade question for now
question = "3x² - 6x + 12 = 0"
options = [
    "x = 1 + i√3",
    "x = -1 + i√3",
    "x = 1 - i√3",
    "x = -1 - i√3"
]

# Formatted prompt
QUESTION_MESSAGE = (
    "Answer the following question. Reply only with 1–4 for the correct answer."
)

# === Setup Chrome ===
chrome_options = Options()
chrome_options.add_argument("--start-maximized")
chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
chrome_options.add_experimental_option("useAutomationExtension", False)

service = Service()  # Uses chromedriver from PATH
driver = webdriver.Chrome(service=service, options=chrome_options)
wait = WebDriverWait(driver, 30)

# === Open ChatGPT ===
driver.get(CHAT_URL)

# === Optional: open new chat ===
try:
    new_chat_btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, 'a[href="/"]')))
    new_chat_btn.click()
    print("🆕 New chat opened")
    time.sleep(2)
except Exception:
    pass

# === Wait for message box ===
message_box = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#prompt-textarea")))
message_box.click()
time.sleep(0.5)

# === Type the entire message with Shift+Enter between lines ===
def type_line(line: str):
    message_box.send_keys(line)
    message_box.send_keys(Keys.SHIFT, Keys.ENTER)

# Build message dynamically
type_line(QUESTION_MESSAGE)
type_line("")  # blank line
type_line(f"Question: {question}")
type_line("Options:")
for i, opt in enumerate(options, start=1):
    type_line(f"{i}) {opt}")

# final newline not necessary, but safe
time.sleep(0.5)

# === Click send ===
send_button = wait.until(
    EC.element_to_be_clickable((By.CSS_SELECTOR, "button[data-testid='send-button']"))
)
send_button.click()
print("✅ Question sent successfully!")

time.sleep(120)
# driver.quit()
