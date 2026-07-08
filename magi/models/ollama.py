"""Minimal Ollama backend for MAGI."""

from __future__ import annotations

import json
import urllib.error
import urllib.request

OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_CHAT_URL = f"{OLLAMA_BASE_URL}/api/chat"
OLLAMA_TAGS_URL = f"{OLLAMA_BASE_URL}/api/tags"
REQUEST_TIMEOUT = 120


class OllamaConnectionError(RuntimeError):
    """Raised when Ollama cannot be reached."""


def installed_models() -> set[str]:
    """Return locally available Ollama model names."""
    try:
        with urllib.request.urlopen(OLLAMA_TAGS_URL, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, json.JSONDecodeError, OSError):
        return set()

    names: set[str] = set()
    for model in data.get("models", []):
        full_name = model.get("name", "")
        if full_name:
            names.add(full_name)
            names.add(full_name.split(":", 1)[0])
    return names


def chat(model: str, system: str, user: str, temperature: float = 0.7) -> str:
    """Send a chat request to Ollama."""
    payload = {
        "model": model,
        "stream": False,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "options": {
            "temperature": temperature,
        },
    }

    request = urllib.request.Request(
        OLLAMA_CHAT_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise OllamaConnectionError(
            f"Could not reach Ollama at {OLLAMA_CHAT_URL}. "
            "Start Ollama or run MAGI with --mock."
        ) from exc

    return data["message"]["content"]
