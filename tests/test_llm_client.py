# tests/test_llm_client.py
import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))
import llm_client
from llm_client import LLMError, complete


def _mock_response(text: str, status: int = 200):
    """Build a fake urllib response object."""
    body = json.dumps({
        "candidates": [{"content": {"parts": [{"text": text}]}}]
    }).encode()
    mock = MagicMock()
    mock.__enter__ = lambda s: s
    mock.__exit__ = MagicMock(return_value=False)
    mock.read.return_value = body
    mock.status = status
    return mock


def test_complete_returns_string(monkeypatch):
    payload = json.dumps({"result": "ok"})
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    with patch("urllib.request.urlopen", return_value=_mock_response(payload)):
        result = complete("test prompt")
    assert result == payload


def test_complete_strips_markdown_fences(monkeypatch):
    raw_json = '{"a": 1}'
    fenced = f"```json\n{raw_json}\n```"
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    with patch("urllib.request.urlopen", return_value=_mock_response(fenced)):
        result = complete("test prompt")
    assert result == raw_json
    json.loads(result)  # must be valid JSON


def test_complete_retries_on_bad_json_then_raises(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    call_count = {"n": 0}

    def fake_urlopen(req, timeout=None):
        call_count["n"] += 1
        return _mock_response("not valid json at all")

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        try:
            complete("test prompt")
            assert False, "should have raised"
        except LLMError:
            pass
    assert call_count["n"] == 2  # initial + 1 retry


def test_complete_succeeds_on_retry(monkeypatch):
    """First call returns bad JSON; second call (retry) returns valid JSON — must succeed."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    call_count = {"n": 0}
    valid = '{"ok": true}'

    def fake_urlopen(req, timeout=None):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return _mock_response("not json")
        return _mock_response(valid)

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        result = complete("test prompt")

    assert result == valid
    assert call_count["n"] == 2


def test_complete_raises_on_429(monkeypatch):
    import urllib.error
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    err = urllib.error.HTTPError(url="", code=429, msg="Too Many Requests", hdrs={}, fp=None)
    with patch("urllib.request.urlopen", side_effect=err):
        try:
            complete("test prompt")
            assert False, "should have raised"
        except LLMError as e:
            assert "429" in str(e)


def test_complete_raises_on_timeout(monkeypatch):
    import socket
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    with patch("urllib.request.urlopen", side_effect=TimeoutError("timed out")):
        try:
            complete("test prompt")
            assert False, "should have raised"
        except LLMError as e:
            assert "timed out" in str(e).lower()


def test_model_read_from_env(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "key")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-custom-model")
    captured_urls = []

    def fake_urlopen(req, timeout=None):
        captured_urls.append(req.full_url)
        return _mock_response('{"ok": true}')

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        complete("prompt")

    assert "gemini-custom-model" in captured_urls[0]
