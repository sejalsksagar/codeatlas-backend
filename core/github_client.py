"""
core/github_client.py
---------------------
Async GitHub REST API client for CodeAtlas.

Public surface
~~~~~~~~~~~~~~
Exceptions:
    GitHubClientError       – base for all errors raised by this module
    RepoNotFoundError       – HTTP 404 from the GitHub API
    RateLimitError          – HTTP 403 / 429 (rate-limit or token missing)
    GitHubTimeoutError      – request timed out

Helpers:
    parse_github_url(url)   -> tuple[str, str]          owner, repo
    get_key_files(paths)    -> list[str]                 filter to known key files

Client:
    GitHubClient            – async context manager / singleton-friendly class
        .get_tree(owner, repo, branch) -> list[str]
        .get_file_content(owner, repo, branch, path) -> str
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

import httpx

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

_GITHUB_API_BASE = "https://api.github.com"
_RAW_BASE = "https://raw.githubusercontent.com"
_DEFAULT_TIMEOUT = 20.0  # seconds

# Files considered "key" for stack detection / AI summarisation
_KEY_FILE_NAMES: frozenset[str] = frozenset(
    [
        "package.json",
        "requirements.txt",
        "go.mod",
        "pom.xml",
        "Cargo.toml",
        "docker-compose.yml",
        "Dockerfile",
        ".env.example",
        "README.md",
        "main.py",
        "app.py",
        "index.js",
        "index.ts",
        "main.go",
        "main.rs",
    ]
)


# --------------------------------------------------------------------------- #
# Custom exceptions
# --------------------------------------------------------------------------- #


class GitHubClientError(Exception):
    """Base class for all errors raised by GitHubClient."""


class RepoNotFoundError(GitHubClientError):
    """Raised when the GitHub API returns 404 for a repository or resource."""

    def __init__(self, owner: str, repo: str, path: str = "") -> None:
        location = f"{owner}/{repo}" + (f"/{path}" if path else "")
        super().__init__(f"GitHub resource not found: {location}")
        self.owner = owner
        self.repo = repo
        self.path = path


class RateLimitError(GitHubClientError):
    """
    Raised when the GitHub API returns 403 or 429.

    GitHub uses 403 (not 429) for primary rate-limit exhaustion and for
    secondary rate limits; 429 may appear on some endpoints.
    """

    def __init__(self, status_code: int, reset_epoch: int | None = None) -> None:
        msg = f"GitHub rate limit exceeded (HTTP {status_code})"
        if reset_epoch is not None:
            msg += f"; resets at epoch {reset_epoch}"
        super().__init__(msg)
        self.status_code = status_code
        self.reset_epoch = reset_epoch


class GitHubTimeoutError(GitHubClientError):
    """Raised when an HTTP request to GitHub times out."""

    def __init__(self, url: str) -> None:
        super().__init__(f"Request timed out: {url}")
        self.url = url


# --------------------------------------------------------------------------- #
# Pure helpers (no I/O)
# --------------------------------------------------------------------------- #


def parse_github_url(url: str) -> tuple[str, str]:
    """
    Extract the owner and repository name from a GitHub URL.

    Accepts both HTTPS and SSH forms, with or without a trailing '.git':
        https://github.com/owner/repo
        https://github.com/owner/repo.git
        git@github.com:owner/repo.git

    Returns:
        (owner, repo) as plain strings.

    Raises:
        ValueError: if the URL cannot be parsed as a GitHub repo URL.
    """
    url = url.strip()

    # SSH form: git@github.com:owner/repo[.git]
    ssh_match = re.match(r"^git@github\.com:([^/]+)/([^/]+?)(?:\.git)?$", url)
    if ssh_match:
        return ssh_match.group(1), ssh_match.group(2)

    # HTTPS form
    parsed = urlparse(url)
    if parsed.netloc not in {"github.com", "www.github.com"}:
        raise ValueError(f"Not a GitHub URL: {url!r}")

    # Strip leading '/', optional trailing '.git', and split on '/'
    path_parts = parsed.path.lstrip("/").rstrip("/")
    if path_parts.endswith(".git"):
        path_parts = path_parts[:-4]

    parts = [p for p in path_parts.split("/") if p]
    if len(parts) < 2:  # noqa: PLR2004
        raise ValueError(
            f"Could not extract owner/repo from GitHub URL: {url!r}. "
            "Expected https://github.com/owner/repo"
        )

    return parts[0], parts[1]


def get_key_files(file_list: list[str]) -> list[str]:
    """
    Filter *file_list* to paths whose basename is one of the known key files.

    The comparison is case-sensitive and matches only the final path component
    (e.g. ``src/main.py`` matches because ``main.py`` is a key file).

    Args:
        file_list: Flat list of relative file paths, as returned by
                   ``GitHubClient.get_tree``.

    Returns:
        Sorted list of matching paths, preserving the original path prefix.
    """
    matched = [p for p in file_list if p.split("/")[-1] in _KEY_FILE_NAMES]
    return sorted(matched)


# --------------------------------------------------------------------------- #
# Internal helpers
# --------------------------------------------------------------------------- #


def _rate_limit_reset(headers: httpx.Headers) -> int | None:
    """Return the X-RateLimit-Reset epoch from response headers, or None."""
    raw = headers.get("X-RateLimit-Reset") or headers.get("x-ratelimit-reset")
    if raw and raw.isdigit():
        return int(raw)
    return None


def _raise_for_github_status(
    response: httpx.Response,
    owner: str,
    repo: str,
    path: str = "",
) -> None:
    """
    Inspect *response* and raise a domain-specific exception when appropriate.

    Must be called before ``response.raise_for_status()`` so our custom
    exceptions take priority over httpx's generic ``HTTPStatusError``.
    """
    code = response.status_code
    if code == 404:  # noqa: PLR2004
        raise RepoNotFoundError(owner, repo, path)
    if code in {403, 429}:
        raise RateLimitError(code, _rate_limit_reset(response.headers))
    # Delegate all other non-2xx statuses to httpx
    response.raise_for_status()


# --------------------------------------------------------------------------- #
# Client
# --------------------------------------------------------------------------- #


class GitHubClient:
    """
    Async GitHub REST API client.

    Usage — as an async context manager (recommended):

        async with GitHubClient(token="ghp_...") as client:
            paths = await client.get_tree("torvalds", "linux")

    Usage — as a long-lived singleton (e.g. FastAPI lifespan):

        client = GitHubClient(token=settings.GITHUB_TOKEN)
        # … use client …
        await client.close()   # on app shutdown

    Args:
        token:   GitHub personal-access token.  Optional for public repos but
                 significantly raises the rate limit (60 → 5 000 req/hr).
        timeout: Per-request timeout in seconds (default 20 s).
    """

    def __init__(
        self,
        token: str = "",
        timeout: float = _DEFAULT_TIMEOUT,
    ) -> None:
        headers: dict[str, str] = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"

        self._api_client = httpx.AsyncClient(
            base_url=_GITHUB_API_BASE,
            headers=headers,
            timeout=timeout,
            follow_redirects=True,
        )
        # Separate client for raw.githubusercontent.com (no Accept / version headers)
        self._raw_client = httpx.AsyncClient(
            base_url=_RAW_BASE,
            headers={"Authorization": f"Bearer {token}"} if token else {},
            timeout=timeout,
            follow_redirects=True,
        )

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    async def get_tree(
        self,
        owner: str,
        repo: str,
        branch: str = "HEAD",
    ) -> list[str]:
        """
        Return a flat list of every *blob* (file) path in the repository.

        Uses the Git Trees API with ``?recursive=1`` so a single request
        retrieves the entire tree regardless of depth.  Directories (trees)
        are excluded; only file paths are returned.

        When GitHub truncates the response (repos with > ~100 000 entries),
        a ``RuntimeError`` is raised with a descriptive message rather than
        silently returning an incomplete list.

        Args:
            owner:  GitHub username or organisation (e.g. ``"torvalds"``).
            repo:   Repository name (e.g. ``"linux"``).
            branch: Branch name, tag, or commit SHA (default: ``"HEAD"``).

        Returns:
            Sorted list of relative file paths, e.g.
            ``["README.md", "src/main.py", ...]``.

        Raises:
            RepoNotFoundError:  Repository or branch does not exist.
            RateLimitError:     API rate limit exceeded.
            GitHubTimeoutError: Request timed out.
        """
        url = f"/repos/{owner}/{repo}/git/trees/{branch}"
        params = {"recursive": "1"}

        response = await self._get_api(url, params=params, owner=owner, repo=repo)
        data: dict[str, Any] = response.json()

        if data.get("truncated"):
            raise RuntimeError(
                f"GitHub truncated the tree for {owner}/{repo}@{branch}. "
                "The repository has too many files to fetch in a single request."
            )

        paths = [
            item["path"]
            for item in data.get("tree", [])
            if item.get("type") == "blob"
        ]
        return sorted(paths)

    async def get_file_content(
        self,
        owner: str,
        repo: str,
        branch: str,
        path: str,
    ) -> str:
        """
        Fetch the raw text content of a single file.

        Retrieves from ``raw.githubusercontent.com`` which avoids the 1 MB
        Base64 payload limit imposed by the Contents API.

        Args:
            owner:  GitHub username or organisation.
            repo:   Repository name.
            branch: Branch name, tag, or commit SHA.
            path:   Relative file path within the repository
                    (e.g. ``"src/main.py"``).

        Returns:
            Raw file content as a UTF-8 string.

        Raises:
            RepoNotFoundError:  File, branch, or repository does not exist.
            RateLimitError:     Rate limit exceeded.
            GitHubTimeoutError: Request timed out.
        """
        url = f"/{owner}/{repo}/{branch}/{path}"

        try:
            response = await self._raw_client.get(url)
        except httpx.TimeoutException:
            raise GitHubTimeoutError(f"{_RAW_BASE}{url}")

        _raise_for_github_status(response, owner, repo, path)
        return response.text

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #

    async def close(self) -> None:
        """Release underlying HTTP connections.  Safe to call multiple times."""
        await self._api_client.aclose()
        await self._raw_client.aclose()

    async def __aenter__(self) -> "GitHubClient":
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    # ------------------------------------------------------------------ #
    # Private helpers
    # ------------------------------------------------------------------ #

    async def _get_api(
        self,
        path: str,
        *,
        params: dict[str, str] | None = None,
        owner: str = "",
        repo: str = "",
    ) -> httpx.Response:
        """
        Perform a GET request against the GitHub REST API.

        Centralises timeout handling and status-code mapping so every public
        method benefits automatically.
        """
        try:
            response = await self._api_client.get(path, params=params)
        except httpx.TimeoutException:
            raise GitHubTimeoutError(f"{_GITHUB_API_BASE}{path}")

        _raise_for_github_status(response, owner, repo)
        return response