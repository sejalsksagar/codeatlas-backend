# test_github_client.py
"""
Run:
    pip install pytest pytest-asyncio respx
    python -m pytest tests/test_github_client.py
"""
import pytest
import respx  # type: ignore[import]
import httpx
from core.github_client import (
    GitHubClient,
    RepoNotFoundError,
    RateLimitError,
    GitHubTimeoutError,
    parse_github_url,
    get_key_files
)

@respx.mock
@pytest.mark.asyncio
async def test_get_tree_success():
    respx.get("https://api.github.com/repos/owner/repo/git/trees/HEAD").mock(
        return_value=httpx.Response(200, json={
            "truncated": False,
            "tree": [
                {"path": "README.md", "type": "blob"},
                {"path": "src", "type": "tree"},  # should be excluded
                {"path": "src/main.py", "type": "blob"},
            ]
        })
    )
    async with GitHubClient(token="fake") as client:
        result = await client.get_tree("owner", "repo")
    assert result == ["README.md", "src/main.py"]

@respx.mock
@pytest.mark.asyncio
async def test_get_tree_404_raises():
    respx.get("https://api.github.com/repos/owner/repo/git/trees/HEAD").mock(
        return_value=httpx.Response(404)
    )
    async with GitHubClient(token="fake") as client:
        with pytest.raises(RepoNotFoundError):
            await client.get_tree("owner", "repo")