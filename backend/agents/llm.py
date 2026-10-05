"""Minimal OpenAI-compatible chat client (works with any provider exposing /chat/completions)."""

import json
import os
from urllib.request import Request, urlopen


def configured() -> bool:
    return bool(os.getenv("OPENAI_API_KEY"))


def chat(messages: list[dict], tools: list[dict], *, timeout: int = 30) -> dict:
    base = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    body = json.dumps({"model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"), "temperature": 0.2,
                       "messages": messages, "tools": tools, "tool_choice": "auto"}).encode()
    req = Request(f"{base}/chat/completions", data=body, method="POST",
                  headers={"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}", "Content-Type": "application/json"})
    with urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode())["choices"][0]["message"]
