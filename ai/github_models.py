from __future__ import annotations

import httpx
from tenacity import (
    RetryError,
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)


# ------------------------------------------------------------------ #
# Custom exceptions
# ------------------------------------------------------------------ #


class LLMUnavailableError(Exception):
    """Raised when the LLM endpoint fails in a non-retryable way."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


# ------------------------------------------------------------------ #
# Internal sentinel + retry predicate
# ------------------------------------------------------------------ #

_ENDPOINT = "https://models.inference.ai.azure.com/chat/completions"
_MODEL = "gpt-4o-mini"
_TIMEOUT = 25.0


class _RetryableHTTPError(Exception):
    """Internal sentinel raised when we receive HTTP 429."""


def _should_retry(exc: BaseException) -> bool:
    """Retry on timeouts and HTTP 429; everything else propagates immediately."""
    if isinstance(exc, httpx.TimeoutException):
        return True
    if isinstance(exc, _RetryableHTTPError):
        return True
    return False


# ------------------------------------------------------------------ #
# Core LLM call (with tenacity retry)
# ------------------------------------------------------------------ #


@retry(
    retry=retry_if_exception(_should_retry),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=8),
    reraise=True,   # re-raise the last retryable exception when attempts are exhausted
)
async def _call_with_retry(prompt: str, token: str) -> str:
    """Internal helper wrapped with tenacity retry logic."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": _MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 1000,
        "temperature": 0.3,
    }

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        try:
            response = await client.post(_ENDPOINT, headers=headers, json=payload)
        except httpx.TimeoutException:
            raise  # tenacity will catch and retry

        if response.status_code == 429:
            raise _RetryableHTTPError("Rate limited (429)")

        if response.status_code != 200:
            # Non-retryable — raise LLMUnavailableError directly; tenacity won't retry it
            raise LLMUnavailableError(
                f"LLM returned HTTP {response.status_code}: {response.text[:200]}",
                status_code=response.status_code,
            )

        data = response.json()
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as exc:
            raise LLMUnavailableError(
                f"Unexpected response shape: {str(data)[:200]}"
            ) from exc


async def call_llm(prompt: str, token: str) -> str:
    """
    Send *prompt* to the GitHub Models inference endpoint and return the
    assistant's reply as a plain string.

    Retries up to 3 times on timeouts and HTTP 429 with exponential back-off
    (2 s → 4 s → 8 s).  Any other failure raises :class:`LLMUnavailableError`.

    Args:
        prompt: The user message to send.
        token:  GitHub Models PAT (``GITHUB_MODELS_TOKEN``).

    Returns:
        The model's text reply.

    Raises:
        LLMUnavailableError: On non-retryable HTTP errors, malformed responses,
                             or when all retry attempts are exhausted.
    """
    try:
        return await _call_with_retry(prompt, token)
    except LLMUnavailableError:
        raise
    except _RetryableHTTPError as exc:
        # All 3 attempts were rate-limited
        raise LLMUnavailableError(str(exc), status_code=429) from exc
    except httpx.TimeoutException as exc:
        # All 3 attempts timed out
        raise LLMUnavailableError(
            f"LLM timed out after {_TIMEOUT}s (3 attempts exhausted)"
        ) from exc
    except Exception as exc:
        raise LLMUnavailableError(f"Unexpected LLM error: {exc}") from exc