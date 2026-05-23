from __future__ import annotations

import httpx

from core.config import settings

GITHUB_API_BASE = "https://api.github.com"


class GitHubClient:
    """Async GitHub REST API client."""

    def __init__(self) -> None:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if settings.GITHUB_TOKEN:
            headers["Authorization"] = f"Bearer {settings.GITHUB_TOKEN}"

        self._client = httpx.AsyncClient(
            base_url=GITHUB_API_BASE,
            headers=headers,
            timeout=30.0,
        )

    async def get_repo(self, owner: str, repo: str) -> dict:
        """Fetch repository metadata. Not yet implemented."""
        return {"status": "not implemented"}

    async def get_tree(self, owner: str, repo: str, branch: str = "HEAD") -> dict:
        """Fetch the full file tree for a repository. Not yet implemented."""
        return {"status": "not implemented"}

    async def get_file_content(self, owner: str, repo: str, path: str) -> dict:
        """Fetch the contents of a single file. Not yet implemented."""
        return {"status": "not implemented"}

    async def close(self) -> None:
        await self._client.aclose()

    # ------------------------------------------------------------------ #
    # Context-manager support
    # ------------------------------------------------------------------ #

    async def __aenter__(self) -> "GitHubClient":
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()


# Module-level singleton (closed on app shutdown via lifespan)
github_client = GitHubClient()
