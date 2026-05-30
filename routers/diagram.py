"""
routers/diagram.py
------------------
POST /diagram  — generate a Mermaid architecture diagram for a repository.

Flow
~~~~
1. Validate the request body
2. Try the LLM with build_diagram_prompt → raw Mermaid text
3. Parse the Mermaid source into nodes + edges via diagram_parser
4. Fall back to fallback_diagram on any LLM / parse failure
5. Return DiagramResponse
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException

from ai.fallback import fallback_diagram
from ai.github_models import LLMUnavailableError, call_llm
from ai.prompts import build_diagram_prompt
from analyzers.diagram_parser import parse_mermaid
from core.config import settings
from core.github_client import parse_github_url
from models.schemas import DiagramRequest, DiagramResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/diagram", tags=["diagram"])


@router.post("/", response_model=DiagramResponse)
async def generate_diagram(body: DiagramRequest) -> Any:
    """
    Generate a Mermaid.js architecture diagram for a repository.

    Accepts a pre-computed ``stack`` dict and ``modules`` list so the caller
    (e.g. the frontend) can reuse data from a prior /analyze call without
    re-fetching the repository.
    """

    # ── Validate URL (non-GitHub URLs rejected early) ────────────────────────
    try:
        owner, repo = parse_github_url(body.repo_url)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    repo_name = f"{owner}/{repo}"

    # ── Attempt LLM diagram generation ───────────────────────────────────────
    mermaid_source: str = ""
    nodes: list[dict] = []
    edges: list[dict] = []
    used_fallback = False

    if settings.GITHUB_MODELS_TOKEN:
        prompt = build_diagram_prompt(
            repo_name=repo_name,
            stack=body.stack,
            modules=body.modules,
        )
        try:
            mermaid_source = await call_llm(prompt, settings.GITHUB_MODELS_TOKEN)
            # Strip stray markdown fences the model occasionally emits
            mermaid_source = _strip_fences(mermaid_source)
            nodes, edges = parse_mermaid(mermaid_source)
        except (LLMUnavailableError, Exception) as exc:
            logger.warning("LLM diagram failed (%s); using fallback", exc)
            used_fallback = True
    else:
        used_fallback = True

    if used_fallback:
        # fallback_diagram uses getattr() so needs a StackResult, not a plain dict
        from analyzers.stack_detector import StackResult as _SR
        stack_obj = _SR(
            languages=body.stack.get("languages", []),
            frameworks=body.stack.get("frameworks", []),
            databases=body.stack.get("databases", []),
            infra=body.stack.get("infra", []),
            test_frameworks=body.stack.get("test_frameworks", []),
            package_manager=body.stack.get("package_manager"),
        )
        fallback = fallback_diagram(stack=stack_obj, modules=body.modules)
        mermaid_source = fallback.get("mermaid_source", "")
        nodes = fallback.get("nodes", [])
        edges = fallback.get("edges", [])

    return DiagramResponse(
        status="ok",
        repo=repo_name,
        mermaid_source=mermaid_source,
        nodes=nodes,
        edges=edges,
        used_fallback=used_fallback,
    )


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _strip_fences(text: str) -> str:
    """
    Remove leading/trailing markdown code fences that models sometimes emit
    despite being told not to.

    Handles both:
        ```mermaid\\n...\\n```
        ```\\n...\\n```
    """
    lines = text.strip().splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()