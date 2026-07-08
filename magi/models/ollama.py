"""Ollama backend utilities for MAGI."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass


OLLAMA_BASE_URL = os.environ.get("MAGI_OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_CHAT_URL = f"{OLLAMA_BASE_URL}/api/chat"
OLLAMA_TAGS_URL = f"{OLLAMA_BASE_URL}/api/tags"
REQUEST_TIMEOUT = 120


class OllamaError(RuntimeError):
    """Base class for Ollama-related errors."""


class OllamaConnectionError(OllamaError):
    """Raised when MAGI cannot connect to Ollama."""


class OllamaModelNotFoundError(OllamaError):
    """Raised when a requested model is not installed locally."""

    def __init__(self, requested: str, available: list[str]) -> None:
        self.requested = requested
        self.available = available

        available_text = "\n".join(f"  - {name}" for name in available) or "  - none"

        super().__init__(
            f"Ollama model not found: {requested}\n\n"
            f"Installed models:\n{available_text}\n\n"
            f"Install it with:\n"
            f"  ollama pull {requested}\n"
        )


@dataclass(frozen=True)
class OllamaStatus:
    """Human-readable Ollama readiness status."""

    running: bool
    models: list[str]
    message: str


def _request_json(url: str, payload: dict | None = None, timeout: int = REQUEST_TIMEOUT) -> dict:
    data = None
    headers = {}

    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(url, data=data, headers=headers)

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise OllamaConnectionError(
            "Could not connect to Ollama.\n\n"
            "Make sure Ollama is installed and running:\n"
            "  ollama serve\n\n"
            "Then check installed models:\n"
            "  ollama list\n\n"
            f"MAGI tried to reach:\n"
            f"  {OLLAMA_BASE_URL}\n"
        ) from exc
    except json.JSONDecodeError as exc:
        raise OllamaError("Ollama returned invalid JSON.") from exc


def installed_models() -> list[str]:
    """Return installed Ollama model names."""
    data = _request_json(OLLAMA_TAGS_URL, timeout=10)
    models = data.get("models", [])

    names = []
    for model in models:
        name = model.get("name")
        if name:
            names.append(name)

    return sorted(names)


def normalize_model_name(name: str) -> str:
    """Normalize a model name for comparison."""
    return name.strip().lower()


def resolve_model_name(requested: str, available: list[str]) -> str | None:
    """Resolve a requested model against installed Ollama models.

    Supports:
    - exact match: llama3.2:latest
    - short match: llama3.2 -> llama3.2:latest
    - prefix match: qwen2.5 -> qwen2.5:7b
    """
    requested_clean = requested.strip()
    requested_norm = normalize_model_name(requested_clean)

    exact = {
        normalize_model_name(model): model
        for model in available
    }

    if requested_norm in exact:
        return exact[requested_norm]

    latest_name = f"{requested_norm}:latest"
    if latest_name in exact:
        return exact[latest_name]

    prefix_matches = [
        model
        for model in available
        if normalize_model_name(model).startswith(f"{requested_norm}:")
    ]

    if prefix_matches:
        return sorted(prefix_matches)[0]

    return None


def model_is_available(requested: str, available: list[str] | None = None) -> bool:
    """Return whether a model is available locally."""
    if available is None:
        available = installed_models()

    return resolve_model_name(requested, available) is not None


def ollama_status() -> OllamaStatus:
    """Return a readiness status for Ollama."""
    try:
        models = installed_models()
    except OllamaConnectionError as exc:
        return OllamaStatus(
            running=False,
            models=[],
            message=str(exc),
        )

    if not models:
        return OllamaStatus(
            running=True,
            models=[],
            message=(
                "Ollama is running, but no models are installed.\n\n"
                "Install one model first, for example:\n"
                "  ollama pull llama3.2\n"
            ),
        )

    return OllamaStatus(
        running=True,
        models=models,
        message="Ollama is running and local models are available.",
    )


def format_model_list(models: list[str]) -> str:
    """Format installed models for terminal display."""
    if not models:
        return "No local Ollama models found."

    return "\n".join(f"  - {model}" for model in models)


def chat(model: str, system: str, user: str, temperature: float = 0.7) -> str:
    """Call Ollama chat API."""
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": system,
            },
            {
                "role": "user",
                "content": user,
            },
        ],
        "stream": False,
        "options": {
            "temperature": temperature,
        },
    }

    data = _request_json(OLLAMA_CHAT_URL, payload=payload)

    try:
        return data["message"]["content"]
    except KeyError as exc:
        raise OllamaError(f"Unexpected Ollama response: {data}") from exc
