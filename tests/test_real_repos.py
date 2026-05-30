"""
tests/test_real_repos.py
~~~~~~~~~~~~~~~~~~~~~~~~
Integration tests that hit the real GitHub API and pipe results through
the stack detector.

These tests are SKIPPED automatically when GITHUB_TOKEN is not set in the
environment (or .env), so they never break CI on machines without a token.
They are meant to be run manually during development:

    # minimal — uses unauthenticated API (60 req/hr limit)
    pytest tests/test_real_repos.py -v -s

    # recommended — authenticated (5 000 req/hr)
    GITHUB_TOKEN=ghp_... pytest tests/test_real_repos.py -v -s

    # run only one repo
    pytest tests/test_real_repos.py -v -s -k "fastapi"

What each test does
-------------------
1.  Calls GitHubClient.get_tree()  → list of all file paths
2.  Calls get_key_files()          → filters to known important files
3.  Fetches each key file content  → dict[path, content]
4.  Calls detect_stack()           → StackResult
5.  Prints a formatted report      → human-readable in -s mode
6.  Asserts the expected stack     → fails loudly if detection regresses
"""

from __future__ import annotations

import asyncio
import os
import sys
import pathlib
import textwrap
import datetime
from pathlib import PurePosixPath

import pytest

# ── Make project root importable when running from any directory ───────────────
ROOT = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from core.github_client import (
    GitHubClient,
    GitHubClientError,
    RateLimitError,
    RepoNotFoundError,
    get_key_files,
    parse_github_url,
)
from analyzers.stack_detector import StackResult, detect_stack

# ── Load .env if present (so GITHUB_TOKEN can live there) ─────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass  # python-dotenv optional here

# ── Shared token (may be empty string for unauthenticated) ────────────────────
GITHUB_TOKEN: str = os.getenv("GITHUB_TOKEN", "")

# ── Skip marker: applied to every test in this file ───────────────────────────
# Remove the condition to force-run even without a token (uses 60 req/hr limit)
pytestmark = pytest.mark.skipif(
    os.getenv("GITHUB_TOKEN", "") == "" and os.getenv("RUN_REAL_REPO_TESTS", "") == "",
    reason=(
        "Skipping real-repo tests. "
        "Set GITHUB_TOKEN=ghp_... or RUN_REAL_REPO_TESTS=1 to enable."
    ),
)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _hr(char: str = "─", width: int = 60) -> str:
    return char * width


def _print_report(
    repo_url: str,
    file_count: int,
    key_files: list[str],
    file_contents: dict[str, str],
    result: StackResult,
) -> None:
    """Pretty-print a detection report to stdout (visible with pytest -s)."""
    print()
    print(_hr("═"))
    print(f"  REPO   : {repo_url}")
    print(f"  FILES  : {file_count} total, {len(key_files)} key files fetched")
    print(_hr())
    print(f"  languages      : {result.languages or '—'}")
    print(f"  frameworks     : {result.frameworks or '—'}")
    print(f"  databases      : {result.databases or '—'}")
    print(f"  infra          : {result.infra or '—'}")
    print(f"  test_frameworks: {result.test_frameworks or '—'}")
    print(f"  package_manager: {result.package_manager or '—'}")
    print(_hr())
    print("  Key files fetched:")
    for kf in key_files:
        size = len(file_contents.get(kf, ""))
        print(f"    {kf:45s}  ({size:,} bytes)")
    print(_hr("═"))


def _prioritised_key_paths(key_paths: list[str], max_per_basename: int = 3) -> list[str]:
    """
    For each basename, keep only the *shallowest* copies (up to max_per_basename).

    This prevents fetching 15 copies of main.py from a large monorepo while
    still collecting the root-level file that matters for stack detection.

    Config files (package.json, requirements.txt, pyproject.toml, go.mod, …)
    get a tighter cap of 1 — there should only ever be one authoritative copy.
    """
    # Files where only the root copy is meaningful
    ROOT_ONLY: frozenset[str] = frozenset([
        "package.json", "requirements.txt", "pyproject.toml",
        "go.mod", "pom.xml", "cargo.toml", "docker-compose.yml",
        "docker-compose.yaml", "dockerfile", "schema.prisma",
    ])

    from collections import defaultdict
    by_basename: dict[str, list[str]] = defaultdict(list)
    for p in key_paths:
        by_basename[PurePosixPath(p).name.lower()].append(p)

    selected: list[str] = []
    for basename, paths in by_basename.items():
        # Sort by depth (fewest slashes first = closest to root)
        paths_sorted = sorted(paths, key=lambda p: (p.count("/"), p))
        cap = 1 if basename in ROOT_ONLY else max_per_basename
        selected.extend(paths_sorted[:cap])

    return sorted(selected)


async def _analyse(repo_url: str, branch: str = "HEAD") -> tuple[StackResult, dict]:
    """
    Full pipeline: tree → key files → detect_stack.
    Returns (StackResult, metadata_dict).
    """
    owner, repo = parse_github_url(repo_url)

    async with GitHubClient(token=GITHUB_TOKEN) as client:
        # Step 1: full file tree
        all_paths = await client.get_tree(owner, repo, branch)

        # Step 2: filter to key files, then prioritise shallowest copies
        raw_key_paths = get_key_files(all_paths)
        key_paths = _prioritised_key_paths(raw_key_paths)

        # Step 3: fetch each key file (skip on 404 — e.g. submodules)
        file_contents: dict[str, str] = {}
        for path in key_paths:
            try:
                content = await client.get_file_content(owner, repo, branch, path)
                file_contents[path] = content
            except RepoNotFoundError:
                pass

        # Step 4: detect stack
        result = await detect_stack(all_paths, file_contents)

    meta = {
        "file_count": len(all_paths),
        "key_files": key_paths,
        "file_contents": file_contents,
    }
    return result, meta


def run(coro):
    return asyncio.run(coro)


# ─────────────────────────────────────────────────────────────────────────────
# Test fixtures — well-known public repos with predictable stacks
# ─────────────────────────────────────────────────────────────────────────────

REPOS = {
    # ── Python / FastAPI ──────────────────────────────────────────────────────
    # fastapi uses pyproject.toml (not requirements.txt) for its own package
    # but has requirements/*.txt for dev deps including pytest
    "fastapi": {
        "url": "https://github.com/tiangolo/fastapi",
        "branch": "master",
        "expect": {
            "languages": ["Python"],
            "frameworks": ["FastAPI"],
            "test_frameworks": ["pytest"],
        },
    },
    # ── Next.js ───────────────────────────────────────────────────────────────
    "nextjs_example": {
        "url": "https://github.com/vercel/next.js",
        "branch": "canary",
        "expect": {
            "languages": ["JavaScript/TypeScript"],
            "frameworks": ["Next.js"],
            "package_manager": "pnpm",
        },
    },
    # ── Go / Gin ─────────────────────────────────────────────────────────────
    "gin": {
        "url": "https://github.com/gin-gonic/gin",
        "branch": "master",
        "expect": {
            "languages": ["Go"],
            "frameworks": ["Gin"],
            "package_manager": "go modules",
        },
    },
    # ── Express (Node) ────────────────────────────────────────────────────────
    "express": {
        "url": "https://github.com/expressjs/express",
        "branch": "master",
        "expect": {
            "languages": ["JavaScript/TypeScript"],
            "frameworks": ["Express"],
        },
    },
    # ── Spring Boot + Kafka + PostgreSQL + MongoDB ───────────────────────────
    "pos_emi_springboot": {
        "url": "https://github.com/sejalsksagar/pos-emi-reward-negotiation-system",
        "branch": "HEAD",
        "expect": {
            "languages": ["Java"],
            "frameworks": ["Spring Boot"],
            "databases": ["PostgreSQL", "MongoDB"],
            "infra": ["Kafka", "Docker Compose"],
            "test_frameworks": ["Spring Boot Test", "JUnit"],
        },
    },
    # ── Django ────────────────────────────────────────────────────────────────
    # Django's own repo uses setup.cfg / pyproject.toml, not requirements.txt
    "django": {
        "url": "https://github.com/django/django",
        "branch": "main",
        "expect": {
            "languages": ["Python"],
            "frameworks": ["Django"],
        },
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# Parametrised tests — one per repo entry above
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("repo_key", list(REPOS.keys()))
def test_detect_stack_real_repo(repo_key: str) -> None:
    """
    For each well-known repo: fetch tree + key files, run detect_stack,
    then assert expected fields are a *subset* of what was detected.

    Subset semantics mean the detector can return *extra* items (e.g. extra
    infra tools) without failing — only the listed expectations must be met.
    """
    spec = REPOS[repo_key]
    url: str = spec["url"]
    branch: str = spec.get("branch", "HEAD")
    expectations: dict = spec["expect"]

    try:
        result, meta = run(_analyse(url, branch))
    except RateLimitError as exc:
        pytest.skip(f"GitHub rate limit hit: {exc}")
    except GitHubClientError as exc:
        pytest.fail(f"GitHub client error for {url}: {exc}")

    _print_report(
        url,
        meta["file_count"],
        meta["key_files"],
        meta["file_contents"],
        result,
    )

    # Assert each expected field is a subset of what was detected
    for field, expected_values in expectations.items():
        if field == "package_manager":
            assert result.package_manager == expected_values, (
                f"[{repo_key}] package_manager: "
                f"expected {expected_values!r}, got {result.package_manager!r}"
            )
        else:
            actual: list = getattr(result, field)
            missing = [v for v in expected_values if v not in actual]
            assert not missing, (
                f"[{repo_key}] {field}: expected to find {missing} in {actual}"
            )


# ─────────────────────────────────────────────────────────────────────────────
# Standalone script mode  —  python tests/test_real_repos.py [url] [branch]
# ─────────────────────────────────────────────────────────────────────────────


async def _main_async(repo_url: str, branch: str) -> None:
    print(f"\nAnalysing {repo_url} @ {branch} …")
    try:
        result, meta = await _analyse(repo_url, branch)
    except RateLimitError as exc:
        print(f"\n⚠  Rate limit: {exc}")
        print("   Set GITHUB_TOKEN=ghp_... to get 5 000 req/hr instead of 60.")
        sys.exit(1)
    except RepoNotFoundError as exc:
        print(f"\n✗  Not found: {exc}")
        sys.exit(1)
    except GitHubClientError as exc:
        print(f"\n✗  GitHub error: {exc}")
        sys.exit(1)

    _print_report(
        repo_url,
        meta["file_count"],
        meta["key_files"],
        meta["file_contents"],
        result,
    )


if __name__ == "__main__":
    # Usage:
    #   python tests/test_real_repos.py
    #   python tests/test_real_repos.py https://github.com/owner/repo
    #   python tests/test_real_repos.py https://github.com/owner/repo main
    url = sys.argv[1] if len(sys.argv) > 1 else "https://github.com/tiangolo/fastapi"
    branch = sys.argv[2] if len(sys.argv) > 2 else "HEAD"
    asyncio.run(_main_async(url, branch))