from google import genai


KEY_FILE = "gemini_key.txt"


def load_api_key():
    with open(KEY_FILE, "r", encoding="utf-8") as f:
        return f.read().strip()


def main():
    client = genai.Client(api_key=load_api_key())
    models = list(client.models.list())
    for model in models:
        name = getattr(model, "name", "")
        print(name)


if __name__ == "__main__":
    main()
