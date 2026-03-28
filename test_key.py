import os
import requests
import json
from pathlib import Path
from dotenv import load_dotenv

# ─── Load env ───────────────────────────────────────────────────────────────
load_dotenv(Path(__file__).parent / ".env", override=True)

key = os.getenv("OPENROUTER_API_KEY", "").strip()
print(f"Key loaded: {len(key)} chars. Starts with: {key[:5]}")

url = "https://openrouter.ai/api/v1/chat/completions"
headers = {
    "Authorization": f"Bearer {key}",
    "Content-Type": "application/json",
    "HTTP-Referer": "http://localhost:8000",
    "X-Title": "Diagnostic"
}

payload = {
    "model": "google/gemini-2.0-flash-lite-preview-02-05:free",
    "messages": [{"role": "user", "content": "Hi"}]
}

try:
    resp = requests.post(url, headers=headers, json=payload, timeout=10)
    print(f"Status: {resp.status_code}")
    if resp.status_code != 200:
        print(f"Error Body: {resp.text}")
    else:
        print("Success! Connection established.")
except Exception as e:
    print(f"Error: {e}")
