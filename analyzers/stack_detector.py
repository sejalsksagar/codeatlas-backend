from __future__ import annotations


async def detect_stack(file_tree: list[str]) -> dict:
    """
    Infer the technology stack from a list of file paths.

    Args:
        file_tree: List of relative file paths from the repository root.

    Returns:
        A dict describing detected languages, frameworks, and tools.
        Not yet implemented.
    """
    return {"status": "not implemented"}


async def detect_stack_from_repo(owner: str, repo: str) -> dict:
    """
    Convenience wrapper: fetch the tree then run detect_stack.
    Not yet implemented.
    """
    return {"status": "not implemented"}
