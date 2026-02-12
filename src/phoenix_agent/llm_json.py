"""Robust JSON extraction from LLM output.

Local models (especially smaller ones like llama3.2) frequently produce
malformed JSON: trailing commas, single quotes, prose before/after the
JSON block, unescaped newlines inside strings, etc.

This module provides best-effort extraction and repair.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


def extract_json(text: str) -> dict[str, Any]:
    """Extract a JSON object from LLM text, with progressive fallbacks.

    1. Try to parse the raw text as JSON.
    2. Strip markdown code fences and retry.
    3. Find the outermost { ... } and parse that.
    4. Apply common repairs (trailing commas, single quotes) and retry.
    5. Raise ValueError if all attempts fail.
    """
    text = text.strip()

    # Attempt 1: raw parse
    result = _try_parse(text)
    if result is not None:
        return result

    # Attempt 2: strip markdown fences
    stripped = _strip_code_fences(text)
    if stripped != text:
        result = _try_parse(stripped)
        if result is not None:
            return result

    # Attempt 3: extract outermost braces
    braced = _extract_braces(stripped)
    if braced:
        result = _try_parse(braced)
        if result is not None:
            return result

        # Attempt 4: repair common issues
        repaired = _repair_json(braced)
        result = _try_parse(repaired)
        if result is not None:
            return result

    # Nothing worked
    preview = text[:200].replace("\n", "\\n")
    raise ValueError(f"Could not extract valid JSON from LLM output: {preview}...")


def _try_parse(text: str) -> dict[str, Any] | None:
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except (json.JSONDecodeError, ValueError):
        pass
    return None


def _strip_code_fences(text: str) -> str:
    """Remove ```json ... ``` or ``` ... ``` wrappers."""
    lines = text.splitlines()
    if lines and lines[0].strip().startswith("```"):
        end = len(lines) - 1
        while end > 0 and not lines[end].strip():
            end -= 1
        if lines[end].strip() == "```":
            return "\n".join(lines[1:end])
        else:
            return "\n".join(lines[1:])
    return text


def _extract_braces(text: str) -> str | None:
    """Find the outermost { ... } in the text using brace counting."""
    start = text.find("{")
    if start == -1:
        return None

    depth = 0
    in_string = False
    escape = False

    for i in range(start, len(text)):
        ch = text[i]
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"' and not escape:
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    # Unbalanced — return from start to end
    return text[start:]


def _repair_json(text: str) -> str:
    """Apply common fixes for malformed JSON from LLMs."""
    # Remove trailing commas before } or ]
    text = re.sub(r",\s*([}\]])", r"\1", text)

    # Replace single quotes with double quotes (but not inside strings)
    # This is a rough heuristic — only do it if there are no double-quoted strings
    if '"' not in text and "'" in text:
        text = text.replace("'", '"')

    # Fix unescaped newlines inside string values
    # Match strings and escape bare newlines within them
    def _escape_newlines_in_strings(m: re.Match) -> str:
        s = m.group(0)
        inner = s[1:-1]
        inner = inner.replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")
        return f'"{inner}"'

    text = re.sub(r'"(?:[^"\\]|\\.)*"', _escape_newlines_in_strings, text, flags=re.DOTALL)

    return text
