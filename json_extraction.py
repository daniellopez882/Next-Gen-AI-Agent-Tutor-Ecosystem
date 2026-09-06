"""
Pull a JSON object out of a model reply.

Six call sites did the same thing:

    clean = raw.replace('```json', '').replace('```', '').strip()
    json.loads(clean)

That parses a reply that is *only* JSON, optionally fenced. It fails on the
common case of a sentence before or after the JSON ("Sure! Here is the quiz:
{...}"), and on a fence that says ```JSON or carries a language tag. This
scans for a balanced brace region, tries the fenced blocks and the whole
string too, and never raises.
"""

from __future__ import annotations

import json
import re
from typing import Any

FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


def _balanced_spans(text: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    depth = 0
    start = -1
    in_string = False
    escaped = False
    for index, char in enumerate(text):
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            if depth == 0:
                start = index
            depth += 1
        elif char == "}" and depth > 0:
            depth -= 1
            if depth == 0 and start >= 0:
                spans.append((start, index + 1))
    return spans


def extract_json(text: str, *, default: dict | None = None) -> dict[str, Any]:
    """The first parseable JSON object in ``text``. Never raises."""
    if not isinstance(text, str) or not text.strip():
        return (
            default
            if default is not None
            else {"error": "empty model response", "raw_output": text}
        )

    candidates: list[str] = [text.strip()]
    candidates.extend(block.strip() for block in FENCE.findall(text))
    candidates.extend(text[a:b] for a, b in _balanced_spans(text))

    for candidate in candidates:
        if not candidate:
            continue
        try:
            parsed = json.loads(candidate)
        except (json.JSONDecodeError, ValueError, TypeError):
            continue
        if isinstance(parsed, dict):
            return parsed

    if default is not None:
        return default
    return {
        "error": "could not parse JSON from the model response",
        "raw_output": text[:2000],
    }
