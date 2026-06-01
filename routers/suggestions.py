"""
routers/suggestions.py
----------------------
POST /suggestions  — return architectural improvement suggestions for a repo.

Flow
~~~~
1. Validate the request body
2. Try the LLM with build_suggestions_prompt → parse JSON array
3. Fall back to fallback_suggestions on any failure
4. Return SuggestionsResponse
"""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, HTTPException

from ai.fallback import fallback_suggestions
from ai.github_models import LLMUnavailableError, call_llm
from ai.prompts import build_suggestions_prompt
from analyzers.stack_detector import StackResult
from core.config import settings
from core.github_client import parse_github_url
from models.schemas import Suggestion, SuggestionsRequest, SuggestionsResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/suggestions", tags=["suggestions"])


@router.post("/", response_model=SuggestionsResponse)
async def get_suggestions(body: SuggestionsRequest) -> Any:
    """
    Return a list of actionable improvement suggestions for a repository.

    Accepts a pre-computed ``stack`` dict so callers can reuse data from a
    prior /analyze call.
    """

    # ── Validate URL ─────────────────────────────────────────────────────────
    try:
        owner, repo = parse_github_url(body.repo_url)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    repo_name = f"{owner}/{repo}"

    # ── Attempt LLM suggestions ───────────────────────────────────────────────
    raw_suggestions: list[dict] = []
    used_fallback = False

    if settings.GITHUB_MODELS_TOKEN:
        prompt = build_suggestions_prompt(
            repo_name=repo_name,
            stack=body.stack,
            modules=body.modules,
        )
        try:
            raw = await call_llm(prompt, settings.GITHUB_MODELS_TOKEN)
            raw_suggestions = _parse_suggestions(raw)
        except (LLMUnavailableError, json.JSONDecodeError, ValueError) as exc:
            logger.warning("LLM suggestions failed (%s); using fallback", exc)
            used_fallback = True
    else:
        used_fallback = True

    if used_fallback:
        # Build a minimal StackResult so fallback_suggestions can evaluate rules
        stack_result = _dict_to_stack(body.stack)
        raw_suggestions = fallback_suggestions(stack_result)

    # ── Coerce to Suggestion models ───────────────────────────────────────────
    suggestions: list[Suggestion] = []
    for item in raw_suggestions:
        try:
            suggestions.append(
                Suggestion(
                    category=item.get("category", "quality"),
                    severity=item.get("severity", "medium"),
                    title=item.get("title", ""),
                    detail=item.get("detail", ""),
                    file_hint=item.get("file_hint"),
                )
            )
        except Exception as exc:
            logger.warning("Skipping malformed suggestion %r: %s", item, exc)

    return SuggestionsResponse(
        status="ok",
        repo=repo_name,
        suggestions=suggestions,
        used_fallback=used_fallback,
    )


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _parse_suggestions(raw: str) -> list[dict]:
    """
    Parse the LLM response as a JSON array.

    Strips optional markdown fences before parsing.

    Raises:
        json.JSONDecodeError: if the text is not valid JSON.
        ValueError:           if the parsed value is not a list.
    """
    text = raw.strip()
    # Strip ```json ... ``` fences if present
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:] if lines[0].startswith("```") else lines)
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3].rstrip()

    parsed = json.loads(text)
    if not isinstance(parsed, list):
        raise ValueError(f"Expected a JSON array, got {type(parsed).__name__}")
    return parsed


def _dict_to_stack(stack_dict: dict) -> StackResult:
    """Convert a plain dict (from the request body) to a StackResult instance."""
    return StackResult(
        languages=stack_dict.get("languages", []),
        frameworks=stack_dict.get("frameworks", []),
        databases=stack_dict.get("databases", []),
        infra=stack_dict.get("infra", []),
        test_frameworks=stack_dict.get("test_frameworks", []),
        package_manager=stack_dict.get("package_manager"),
    )