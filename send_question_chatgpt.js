// Open using Node + Puppeteer
// npm install puppeteer
import puppeteer from "puppeteer";
import path from "path";
import { fileURLToPath } from "url";
import fs from "fs";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const CHAT_URL = "https://chat.openai.com/";
const IMAGE_FILE = path.join(__dirname, "image.png");

// Premade question (can later replace dynamically)
const QUESTION_MESSAGE = `
Answer the following question.
Question: 3x² - 6x + 12 = 0
Options:
1) x = 1 + i√3
2) x = -1 + i√3
3) x = 1 - i√3
4) x = -1 - i√3
Reply only with 1–4 for the correct answer.
`;

(async () => {
  const browser = await puppeteer.launch({
    headless: false, // keep visible so you can see it happen
    defaultViewport: null,
  });

  const page = await browser.newPage();
  await page.goto(CHAT_URL, { waitUntil: "domcontentloaded" });

  // Wait for message box to exist
  await page.waitForSelector("#prompt-textarea", { visible: true });
  const box = await page.$("#prompt-textarea");

  // Type the question
  await box.focus();
  await page.keyboard.type(QUESTION_MESSAGE, { delay: 10 });

  // Upload image.png if present
  if (fs.existsSync(IMAGE_FILE)) {
    const uploadInput = await page.$("#upload-photos");
    if (uploadInput) {
      await uploadInput.uploadFile(IMAGE_FILE);
      console.log("✅ Uploaded image:", IMAGE_FILE);
    } else {
      console.warn("⚠️ Could not find #upload-photos element.");
    }
  }

  // Click send button (uses the last visible "Send" button)
  await page.waitForSelector('button[data-testid="send-button"]', { visible: true });
  await page.click('button[data-testid="send-button"]');

  console.log("✅ Question sent!");
})();
