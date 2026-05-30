"""
routers/analyze.py
------------------
POST /analyze  — full repository analysis endpoint.

Flow
~~~~
1. Validate & parse the GitHub URL → owner/repo
2. Fetch the full file tree via GitHubClient.get_tree()
3. Fetch contents of "key" files (package.json, requirements.txt, etc.)
4. Run the heuristic stack detector
5. Try the LLM for a rich summary; fall back to heuristics on any failure
6. Return AnalyzeResponse
"""

from __future__ import annotations

import json
import logging
from pathlib import PurePosixPath
from typing import Any

from fastapi import APIRouter, HTTPException

from ai.fallback import fallback_summary
from ai.github_models import LLMUnavailableError, call_llm
from ai.prompts import build_summary_prompt
from analyzers.stack_detector import detect_stack
from core.config import settings
from core.github_client import (
    GitHubClient,
    GitHubClientError,
    RateLimitError,
    RepoNotFoundError,
    get_key_files,
    parse_github_url,
)
from models.schemas import AnalyzeRequest, AnalyzeResponse, StackInfo

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analyze", tags=["analyze"])


# --------------------------------------------------------------------------- #
# Internal helpers
# --------------------------------------------------------------------------- #


def _top_level_dirs(paths: list[str]) -> list[str]:
    """Return sorted unique top-level directory names from a flat file list."""
    dirs: set[str] = set()
    for p in paths:
        parts = PurePosixPath(p).parts
        if len(parts) > 1:
            dirs.add(parts[0])
    return sorted(dirs)


def _module_list(paths: list[str]) -> list[str]:
    """
    Return a deduplicated list of interesting top-level paths for prompt context.
    Caps at 40 entries to stay within token budget.
    """
    top = _top_level_dirs(paths)
    # add root-level files for small / flat repos
    root_files = [p for p in paths if "/" not in p]
    return sorted(set(top + root_files))[:40]


# --------------------------------------------------------------------------- #
# Route
# --------------------------------------------------------------------------- #


@router.post("/", response_model=AnalyzeResponse)
async def analyze_repo(body: AnalyzeRequest) -> Any:
    """
    Full repository analysis.

    - Parses the GitHub URL and fetches the file tree.
    - Detects the technology stack heuristically.
    - Requests an AI-generated summary (falls back to heuristics on failure).
    - Returns a structured AnalyzeResponse.
    """

    # ── 1. Validate & parse URL ─────────────────────────────────────────────
    try:
        owner, repo = parse_github_url(body.repo_url)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    repo_name = f"{owner}/{repo}"

    # ── 2. Fetch file tree ───────────────────────────────────────────────────
    try:
        async with GitHubClient(token=settings.GITHUB_TOKEN) as gh:
            try:
                file_paths = await gh.get_tree(owner, repo, body.branch)
            except RepoNotFoundError:
                raise HTTPException(
                    status_code=404,
                    detail=f"Repository '{repo_name}' not found or is private. "
                    "Ensure the repo is public and the URL is correct.",
                )
            except RateLimitError as exc:
                raise HTTPException(
                    status_code=429,
                    detail=str(exc),
                ) from exc

            # ── 3. Fetch key file contents ───────────────────────────────────
            key_paths = get_key_files(file_paths)
            file_contents: dict[str, str] = {}
            for path in key_paths:
                try:
                    file_contents[path] = await gh.get_file_content(
                        owner, repo, body.branch, path
                    )
                except GitHubClientError as exc:
                    # Non-fatal: log and skip missing/unreadable files
                    logger.warning("Could not fetch %s/%s: %s", repo_name, path, exc)

    except HTTPException:
        raise
    except GitHubClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except RuntimeError as exc:
        # get_tree raises RuntimeError when GitHub truncates the response
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Unexpected error fetching repo %s", repo_name)
        raise HTTPException(status_code=500, detail=f"Unexpected error: {exc}") from exc

    # ── 4. Detect stack ──────────────────────────────────────────────────────
    stack_result = await detect_stack(file_paths, file_contents)

    # ── 5. AI summary (with fallback) ────────────────────────────────────────
    readme = file_contents.get("README.md", "")
    modules = _module_list(file_paths)
    top_dirs = _top_level_dirs(file_paths)

    summary_data: dict[str, Any] = {}
    used_fallback = False

    if settings.GITHUB_MODELS_TOKEN:
        prompt = build_summary_prompt(
            repo_name=repo_name,
            stack=stack_result.model_dump(),
            readme=readme,
            modules=modules,
        )
        try:
            raw = await call_llm(prompt, settings.GITHUB_MODELS_TOKEN)
            summary_data = json.loads(raw)
        except (LLMUnavailableError, json.JSONDecodeError) as exc:
            logger.warning("LLM summary failed (%s); using fallback", exc)
            used_fallback = True
    else:
        used_fallback = True

    if used_fallback:
        summary_data = fallback_summary(
            repo_name=repo_name,
            stack=stack_result,
            readme=readme,
            top_level_dirs=top_dirs,
            file_list=file_paths,
        )

    # ── 6. Build response ────────────────────────────────────────────────────
    stack_info = StackInfo(
        languages=stack_result.languages,
        frameworks=stack_result.frameworks,
        databases=stack_result.databases,
        infra=stack_result.infra,
        test_frameworks=stack_result.test_frameworks,
        package_manager=stack_result.package_manager,
    )

    return AnalyzeResponse(
        status="ok",
        repo=repo_name,
        branch=body.branch,
        stack=stack_info,
        summary=summary_data.get("summary"),
        modules=summary_data.get("modules", []),
        entry_points=summary_data.get("entry_points", []),
        request_flow=summary_data.get("request_flow"),
        used_fallback=used_fallback,
    )