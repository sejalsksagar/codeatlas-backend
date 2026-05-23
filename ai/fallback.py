from __future__ import annotations


async def heuristic_summary(repo_meta: dict, stack: dict) -> dict:
    """
    Produce a rule-based summary when the AI model is unavailable.
    Not yet implemented.
    """
    return {"status": "not implemented"}


async def is_ai_available() -> bool:
    """
    Health-check: return True when the GitHub Models endpoint is reachable.
    Not yet implemented.
    """
    return False
