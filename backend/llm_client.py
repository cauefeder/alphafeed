# backend/llm_client.py
"""
Thin LLM abstraction — wraps Gemini Flash (free tier) via stdlib urllib.
Swap model: set GEMINI_MODEL env var.
Swap provider: replace the _call() function body.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request


class LLMError(Exception):
    pass


def _strip_fences(text: str) -> str:
    """Remove ```json ... ``` or ``` ... ``` wrappers that Gemini often adds."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        # Drop first line (```json or ```) and last line (```)
        inner = lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
        text = "\n".join(inner).strip()
    return text


def _call(prompt: str) -> str:
    """Single HTTP call to Gemini. Returns raw text. Raises LLMError on HTTP/network failure."""
    api_key = os.environ.get("GEMINI_API_KEY", "")
    model = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent"
    )
    payload = json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode()
    req = urllib.request.Request(
        url, data=payload,
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = json.loads(resp.read())
            return body["candidates"][0]["content"]["parts"][0]["text"]
    except urllib.error.HTTPError as exc:
        raise LLMError(f"HTTP {exc.code}: {exc.reason}") from exc
    except (TimeoutError, OSError) as exc:
        raise LLMError(str(exc)) from exc


def complete(prompt: str) -> str:
    """
    Call the LLM, strip markdown fences, validate JSON.
    Retries once with an explicit 'Return only raw JSON' suffix on parse failure.
    Raises LLMError on two consecutive parse failures or on HTTP/network error.
    """
    raw = _call(prompt)
    text = _strip_fences(raw)
    try:
        json.loads(text)
        return text
    except json.JSONDecodeError:
        pass

    # Retry once with explicit JSON instruction
    raw2 = _call(prompt + "\n\nReturn only raw JSON, no markdown fences.")
    text2 = _strip_fences(raw2)
    try:
        json.loads(text2)
        return text2
    except json.JSONDecodeError as exc:
        raise LLMError(f"LLM returned invalid JSON after retry: {text2[:100]}") from exc
