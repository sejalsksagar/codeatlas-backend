"""
Unit tests for ai/github_models.py
Run with:  pytest tests/test_github_models.py -v
"""
from __future__ import annotations

import json
import pytest
import httpx

# Make sure the project root is on sys.path when running from repo root.
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from unittest.mock import AsyncMock, MagicMock, patch
from ai.github_models import call_llm, LLMUnavailableError


# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #

def _mock_response(status_code: int, body: dict | str) -> MagicMock:
    """Build a mock httpx.Response."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    if isinstance(body, dict):
        resp.json.return_value = body
        resp.text = json.dumps(body)
    else:
        resp.json.side_effect = ValueError("not json")
        resp.text = body
    return resp


def _llm_ok_response(content: str) -> dict:
    return {
        "choices": [
            {"message": {"role": "assistant", "content": content}}
        ]
    }


# ------------------------------------------------------------------ #
# Happy-path
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_call_llm_success():
    """Returns the assistant message content on HTTP 200."""
    mock_resp = _mock_response(200, _llm_ok_response("Hello from LLM"))

    with patch("ai.github_models.httpx.AsyncClient") as MockClient:
        instance = MockClient.return_value.__aenter__.return_value
        instance.post = AsyncMock(return_value=mock_resp)

        result = await call_llm("Say hello", token="test-token")

    assert result == "Hello from LLM"


# ------------------------------------------------------------------ #
# HTTP error handling
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_call_llm_401_raises_llm_unavailable():
    """Non-retryable HTTP errors raise LLMUnavailableError immediately."""
    mock_resp = _mock_response(401, "Unauthorized")

    with patch("ai.github_models.httpx.AsyncClient") as MockClient:
        instance = MockClient.return_value.__aenter__.return_value
        instance.post = AsyncMock(return_value=mock_resp)

        with pytest.raises(LLMUnavailableError) as exc_info:
            await call_llm("test", token="bad-token")

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_call_llm_500_raises_llm_unavailable():
    mock_resp = _mock_response(500, "Internal Server Error")

    with patch("ai.github_models.httpx.AsyncClient") as MockClient:
        instance = MockClient.return_value.__aenter__.return_value
        instance.post = AsyncMock(return_value=mock_resp)

        with pytest.raises(LLMUnavailableError) as exc_info:
            await call_llm("test", token="tok")

    assert exc_info.value.status_code == 500


# ------------------------------------------------------------------ #
# Rate limiting (429) — retried then fails
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_call_llm_429_exhausts_retries():
    """After 3 × 429 responses the function raises LLMUnavailableError."""
    mock_resp = _mock_response(429, "Too Many Requests")

    with patch("ai.github_models.httpx.AsyncClient") as MockClient:
        instance = MockClient.return_value.__aenter__.return_value
        instance.post = AsyncMock(return_value=mock_resp)

        # Patch wait so the test doesn't actually sleep
        with patch("ai.github_models.wait_exponential", return_value=lambda *_: 0):
            with pytest.raises(LLMUnavailableError) as exc_info:
                await call_llm("test", token="tok")

    assert "429" in str(exc_info.value) or exc_info.value.status_code == 429


# ------------------------------------------------------------------ #
# Timeout — retried then fails
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_call_llm_timeout_raises_llm_unavailable():
    """TimeoutException after all retries raises LLMUnavailableError."""
    with patch("ai.github_models.httpx.AsyncClient") as MockClient:
        instance = MockClient.return_value.__aenter__.return_value
        instance.post = AsyncMock(side_effect=httpx.TimeoutException("timed out"))

        with patch("ai.github_models.wait_exponential", return_value=lambda *_: 0):
            with pytest.raises(LLMUnavailableError) as exc_info:
                await call_llm("test", token="tok")

    assert "timed out" in str(exc_info.value).lower() or "timeout" in str(exc_info.value).lower()


# ------------------------------------------------------------------ #
# Malformed response shape
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_call_llm_bad_shape_raises_llm_unavailable():
    """If choices array is missing, raises LLMUnavailableError."""
    mock_resp = _mock_response(200, {"unexpected": "shape"})

    with patch("ai.github_models.httpx.AsyncClient") as MockClient:
        instance = MockClient.return_value.__aenter__.return_value
        instance.post = AsyncMock(return_value=mock_resp)

        with pytest.raises(LLMUnavailableError):
            await call_llm("test", token="tok")


# ------------------------------------------------------------------ #
# Authorization header is sent correctly
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_call_llm_sends_correct_auth_header():
    """Verifies the Bearer token is forwarded in the Authorization header."""
    mock_resp = _mock_response(200, _llm_ok_response("ok"))
    captured_headers: dict = {}

    async def fake_post(url, *, headers, json, **kw):
        captured_headers.update(headers)
        return mock_resp

    with patch("ai.github_models.httpx.AsyncClient") as MockClient:
        instance = MockClient.return_value.__aenter__.return_value
        instance.post = fake_post

        await call_llm("hello", token="my-secret-token")

    assert captured_headers.get("Authorization") == "Bearer my-secret-token"