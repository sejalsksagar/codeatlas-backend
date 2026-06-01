"""
analyzers/file_tree.py
----------------------
Build and flatten a nested file-tree representation of a repository.

Public API
~~~~~~~~~~
    build_file_tree(paths)   -> dict   nested directory structure
    flatten_tree(tree)       -> list[str]  sorted flat path list (round-trip)
"""

from __future__ import annotations

from pathlib import PurePosixPath


def build_file_tree(paths: list[str]) -> dict:
    """
    Convert a flat list of file paths into a nested dict tree.

    Each directory is a dict whose keys are its children (files or dirs).
    Files are represented as ``None`` values; directories are nested dicts.

    Example::

        build_file_tree(["src/api/routes.py", "src/models/user.py", "README.md"])
        # →
        {
            "src": {
                "api":    {"routes.py": None},
                "models": {"user.py":   None},
            },
            "README.md": None,
        }

    Args:
        paths: Flat list of relative file paths (as returned by
               ``GitHubClient.get_tree``).

    Returns:
        Nested dict representing the directory structure.
    """
    root: dict = {}
    for path in sorted(paths):
        parts = PurePosixPath(path).parts
        node = root
        for part in parts[:-1]:          # walk / create intermediate dirs
            node = node.setdefault(part, {})
        node[parts[-1]] = None           # leaf file → None
    return root


def flatten_tree(tree: dict, _prefix: str = "") -> list[str]:
    """
    Flatten a nested file-tree dict back into a sorted list of relative paths.

    This is the inverse of :func:`build_file_tree`.

    Args:
        tree:    Nested dict as returned by ``build_file_tree``.
        _prefix: Internal — callers should leave this at its default ``""``.

    Returns:
        Sorted list of relative file paths.
    """
    paths: list[str] = []
    for name, subtree in tree.items():
        full = f"{_prefix}{name}" if not _prefix else f"{_prefix}/{name}"
        if subtree is None:
            paths.append(full)
        else:
            paths.extend(flatten_tree(subtree, full))
    return sorted(paths)