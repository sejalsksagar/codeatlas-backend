# test_github_client.py
"""
Run:
    pip install pytest pytest-asyncio respx
    python -m pytest tests/test_github_client.py
"""
import pytest
import respx
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
async def test_get_tree_resolves_default_branch():

    repo_route = respx.get(
        "https://api.github.com/repos/owner/repo"
    ).mock(
        return_value=httpx.Response(
            200,
            json={"default_branch": "develop"}
        )
    )

    tree_route = respx.get(
        "https://api.github.com/repos/owner/repo/git/trees/develop"
    ).mock(
        return_value=httpx.Response(
            200,
            json={"truncated": False, "tree": []}
        )
    )

    async with GitHubClient(token="fake") as client:
        await client.get_tree("owner", "repo")

    assert repo_route.called
    assert tree_route.called
    
@respx.mock
@pytest.mark.asyncio
async def test_get_tree_404_raises():

    respx.get("https://api.github.com/repos/owner/repo").mock(
        return_value=httpx.Response(404)
    )

    async with GitHubClient(token="fake") as client:
        with pytest.raises(RepoNotFoundError):
            await client.get_tree("owner", "repo")