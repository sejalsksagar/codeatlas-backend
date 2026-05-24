# smoke_test.py
"""
Run:
    python -m tests.smoke_test

Test each error path manually:
Scenario                    How to trigger
RepoNotFoundErrorUse        owner="zzz-does-not-exist-xyz"
RateLimitError              Make 60+ unauthenticated requests, or pass a revoked token
GitHubTimeoutErrorPass      timeout=0.0001 to GitHubClient()
Truncated tree              Any repo with >100k files (rare; linux kernel hits this)

# Force a timeout
async with GitHubClient(timeout=0.00001) as client:
    await client.get_tree("torvalds", "linux")  # raises GitHubTimeoutError
"""
import asyncio
from core.github_client import (
    GitHubClient,
    RepoNotFoundError,
    RateLimitError,
    GitHubTimeoutError,
    parse_github_url,
    get_key_files
)

async def main():
    # Parse URL
    owner, repo = parse_github_url("https://github.com/sejalsksagar/codeatlas-backend")
    # Use a repo guaranteed to be tiny and public
    #owner, repo = "kennethreitz", "setup.cfg"

    async with GitHubClient() as client:  # no token = 60 req/hr, fine for testing
        tree = await client.get_tree(owner, repo)
        print(f"Files ({len(tree)}):", tree[:5], "...")

        key = get_key_files(tree)
        print("Key files:", key)

        content = await client.get_file_content(owner, repo, "main", "README.md")
        print("README (first 100 chars):", content[:100])

asyncio.run(main())