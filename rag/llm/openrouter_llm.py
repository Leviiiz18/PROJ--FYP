import os
import requests
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

def call_openrouter(prompt: str) -> str:
    api_key = os.getenv("OPENROUTER_API_KEY")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:8501",
        "X-Title": "RAG PDF Assistant",
    }

    payload = {
        "model": "x-ai/grok-4.1-fast",
        "messages": [
            {"role": "system", "content": "You are a document-grounded assistant."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0,
    }

    response = requests.post(OPENROUTER_URL, headers=headers, json=payload)

    if response.status_code == 401:
        raise Exception(
            "401 Unauthorized — Check OPENROUTER_API_KEY in .env and dashboard"
        )

    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]
