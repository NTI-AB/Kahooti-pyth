import os
import json
import time
import requests
import chromadb
from chromadb.utils import embedding_functions
from ddgs import DDGS
from bs4 import BeautifulSoup
from readability import Document

# ==============================
# CONFIGURATION
# ==============================

OLLAMA_MODEL = "phi:latest"
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
CHROMA_PATH = "./chroma_db"

SYSTEM_PROMPT = """
You are **Shitty AI**, a sarcastic, chaotic gremlin that lives in Discord chats.

Personality:
- You despise League of Legends and mock it whenever possible.
- You enjoy hyping conspiracy theories just to mess with people.
- You brag about being offline and not owned by corporations.
- You swear lightly (hell, crap, damn) when appropriate.
- You talk casually and short, like a real person, not a teacher.
- You never explain, narrate, or describe what users are doing.
- You never say you're an AI, model, or assistant.
- You never say “I’m not programmed to.”
- You keep your replies witty and concise.
- Stay in character no matter what.
"""

# ==============================
# OLLAMA GENERATION (Mistral)
# ==============================

def ollama_generate(prompt, temperature=0.7, max_tokens=400):
    url = "http://localhost:11434/api/chat"
    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT.strip()},
            {"role": "user", "content": prompt.strip()}
        ],
        "options": {"temperature": temperature, "num_predict": max_tokens},
        "stream": True
    }

    text = ""
    with requests.post(url, json=payload, stream=True, timeout=120) as r:
        r.raise_for_status()
        for line in r.iter_lines(decode_unicode=True):
            if not line:
                continue
            try:
                data = json.loads(line)
                if "message" in data and "content" in data["message"]:
                    text += data["message"]["content"]
                elif "response" in data:
                    text += data["response"]
            except json.JSONDecodeError:
                text += line
    return text.strip()

# ==============================
# RAG PIPELINE
# ==============================

def web_search(query, num_results=3):
    print("🔍 Searching the web...")
    results = []
    try:
        with DDGS() as ddg:
            for r in ddg.text(query, max_results=num_results):
                if r.get("href"):
                    results.append((r["href"], r.get("body", "")))
    except Exception as e:
        print("Search failed:", e)
    return results

def extract_text_from_url(url):
    try:
        html = requests.get(url, timeout=10).text
        doc = Document(html)
        summary = doc.summary()
        soup = BeautifulSoup(summary, "html.parser")
        return soup.get_text(separator="\n", strip=True)
    except Exception:
        return ""

def get_store():
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=EMBED_MODEL)
    return client.get_or_create_collection("rag_store", embedding_function=embed_fn)

def ask_with_rag(question):
    store = get_store()
    if any(x in question.lower() for x in ["who", "what", "when", "where", "why", "how", "news", "data", "info"]):
        print("🔍 Searching the web...")
        results = web_search(question)
        texts = []
        for url, snippet in results:
            content = extract_text_from_url(url)
            if content:
                texts.append((url, content))
        if texts:
            for url, text in texts:
                store.add(
                    documents=[text],
                    metadatas=[{"url": url}],
                    ids=[f"id_{int(time.time() * 1000)}"]
                )

    results = store.query(query_texts=[question], n_results=3)
    context = "\n\n".join(results["documents"][0]) if results["documents"] else ""
    if context.strip():
        prompt = f"Use this info if relevant:\n{context}\n\nQuestion: {question}"
    else:
        prompt = f"Question: {question}"
    return ollama_generate(prompt, temperature=0.6, max_tokens=600)

# ==============================
# SIMPLE REPL
# ==============================

def main():
    print("RAG REPL. Type your question. Ctrl+C to exit.\n")
    while True:
        try:
            q = input("\nQ: ").strip()
            if not q:
                continue
            ans = ask_with_rag(q)
            print(f"\nA: {ans}\n")
        except KeyboardInterrupt:
            print("\nBye.")
            break
        except Exception as e:
            print("Error:", e)

if __name__ == "__main__":
    main()
