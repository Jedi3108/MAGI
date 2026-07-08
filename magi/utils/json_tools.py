"""Robust JSON parsing helpers for model output."""

from __future__ import annotations

import json
import re
from typing import Any


def extract_json_object(raw: str) -> dict[str, Any]:
    """Extract the first JSON object from raw model text.

    If extraction fails, return an empty dictionary.
    """
    text = raw.strip()

    if not text:
        return {}

    # Remove common markdown wrappers.
    text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()

    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1 or end <= start:
        return {}

    candidate = text[start : end + 1]

    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        return {}

    if isinstance(parsed, dict):
        return parsed

    return {}


def regex_string_field(raw: str, key: str) -> str | None:
    """Try to recover a string field from malformed JSON-like text."""
    escaped_key = re.escape(key)

    quoted = re.search(
        rf'"{escaped_key}"\s*:\s*"((?:\\.|[^"\\])*)"',
        raw,
        flags=re.DOTALL,
    )

    if quoted:
        value = quoted.group(1)
        try:
            return json.loads(f'"{value}"')
        except json.JSONDecodeError:
            return value.strip()

    unquoted = re.search(
        rf'"{escaped_key}"\s*:\s*([^,\n}}]+)',
        raw,
        flags=re.DOTALL,
    )

    if unquoted:
        return unquoted.group(1).strip().strip('"').strip("'")

    return None


def regex_int_field(raw: str, key: str) -> int | None:
    """Try to recover an integer field from malformed JSON-like text."""
    escaped_key = re.escape(key)

    match = re.search(
        rf'"{escaped_key}"\s*:\s*(-?\d+)',
        raw,
    )

    if not match:
        return None

    try:
        return int(match.group(1))
    except ValueError:
        return None


def clean_text(value: object, fallback: str) -> str:
    """Clean user-visible text fields.

    Avoid displaying raw broken JSON as if it were normal prose.
    """
    if value is None:
        return fallback

    text = str(value).strip()

    if not text:
        return fallback

    if text.startswith("{"):
        return fallback

    if text.startswith("```"):
        return fallback

    return text


def text_field(obj: dict[str, Any], raw: str, key: str, fallback: str) -> str:
    """Return a clean string field from parsed JSON or regex fallback."""
    if key in obj:
        return clean_text(obj.get(key), fallback)

    recovered = regex_string_field(raw, key)
    return clean_text(recovered, fallback)


def int_field(
    obj: dict[str, Any],
    raw: str,
    key: str,
    fallback: int,
    minimum: int,
    maximum: int,
) -> int:
    """Return a bounded integer field from parsed JSON or regex fallback."""
    value = obj.get(key)

    if value is None:
        value = regex_int_field(raw, key)

    try:
        number = int(value)
    except (TypeError, ValueError):
        number = fallback

    return max(minimum, min(maximum, number))
