from __future__ import annotations


async def build_file_tree(owner: str, repo: str, branch: str = "HEAD") -> dict:
    """
    Build a structured file-tree representation of the repository.

    Args:
        owner:  GitHub username or organisation.
        repo:   Repository name.
        branch: Branch / ref to inspect (default: HEAD).

    Returns:
        A nested dict representing the directory structure.
        Not yet implemented.
    """
    return {"status": "not implemented"}


async def flatten_tree(tree: dict) -> list[str]:
    """
    Flatten a nested file-tree dict into a sorted list of relative paths.
    Not yet implemented.
    """
    return []
