"""
analyzers/stack_detector.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~
Heuristic stack detector: infers languages, frameworks, databases,
infrastructure tooling, and test frameworks from a repository's file
tree and the content of a small set of key files.

Public API
----------
detect_stack(file_paths, file_contents) -> StackResult
"""

from __future__ import annotations

import re
from pathlib import PurePosixPath
from typing import Sequence

from pydantic import BaseModel, Field


# ──────────────────────────────────────────────────────────────────────────────
# Output model
# ──────────────────────────────────────────────────────────────────────────────


class StackResult(BaseModel):
    """Detected technology stack for a repository."""

    languages: list[str] = Field(default_factory=list)
    frameworks: list[str] = Field(default_factory=list)
    databases: list[str] = Field(default_factory=list)
    infra: list[str] = Field(default_factory=list)
    test_frameworks: list[str] = Field(default_factory=list)
    package_manager: str | None = None


# ──────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────────────────────────────────────


def _file_content(key: str, file_contents: dict[str, str]) -> str:
    """
    Return the content for *key*, case-insensitively matching the basename.
    Returns an empty string when the key is absent.
    """
    # Exact match first (fastest path)
    if key in file_contents:
        return file_contents[key].lower()

    # Basename-only fallback: e.g. caller passes "requirements.txt"
    # and the dict key is "backend/requirements.txt"
    key_lower = key.lower()
    for stored_key, content in file_contents.items():
        if PurePosixPath(stored_key).name.lower() == key_lower:
            return content.lower()

    return ""


def _contains(content: str, *terms: str) -> bool:
    """True when *all* terms appear in content (case-insensitive; content is pre-lowered)."""
    return all(term.lower() in content for term in terms)


def _any_contains(content: str, *terms: str) -> bool:
    """True when *any* term appears in content (case-insensitive; content is pre-lowered)."""
    return any(term.lower() in content for term in terms)


def _path_set(file_paths: Sequence[str]) -> set[str]:
    """Normalise every path to forward-slash, lower-case for prefix / name matching."""
    return {p.replace("\\", "/").lower() for p in file_paths}


def _basenames(file_paths: Sequence[str]) -> set[str]:
    return {PurePosixPath(p).name.lower() for p in file_paths}


# ──────────────────────────────────────────────────────────────────────────────
# Detection sub-routines
# ──────────────────────────────────────────────────────────────────────────────


def _detect_languages(file_paths: Sequence[str]) -> list[str]:
    """
    Count file extensions and return the languages that appear at least once,
    ordered by descending frequency.
    """
    EXT_MAP: dict[str, str] = {
        ".py": "Python",
        ".js": "JavaScript/TypeScript",
        ".ts": "JavaScript/TypeScript",
        ".jsx": "JavaScript/TypeScript",
        ".tsx": "JavaScript/TypeScript",
        ".go": "Go",
        ".java": "Java",
        ".rs": "Rust",
        ".rb": "Ruby",
        ".cs": "C#",
        ".php": "PHP",
    }

    counts: dict[str, int] = {}
    for path in file_paths:
        suffix = PurePosixPath(path).suffix.lower()
        if suffix in EXT_MAP:
            lang = EXT_MAP[suffix]
            counts[lang] = counts.get(lang, 0) + 1

    # Sort by frequency (desc) so the dominant language comes first
    return [lang for lang, _ in sorted(counts.items(), key=lambda kv: -kv[1])]


def _detect_frameworks(file_contents: dict[str, str]) -> list[str]:
    frameworks: list[str] = []

    pkg = _file_content("package.json", file_contents)
    req = _file_content("requirements.txt", file_contents)
    pom = _file_content("pom.xml", file_contents)
    go_mod = _file_content("go.mod", file_contents)

    # JavaScript / TypeScript frameworks (order matters: Next before React)
    if pkg:
        if _contains(pkg, '"next"'):
            frameworks.append("Next.js")
        elif _contains(pkg, '"react"'):
            # React-only: confirmed absent of Next
            frameworks.append("React")

        if _contains(pkg, '"express"'):
            frameworks.append("Express")
        if _contains(pkg, '"fastify"'):
            frameworks.append("Fastify")

    # Python frameworks
    if req:
        if _contains(req, "fastapi"):
            frameworks.append("FastAPI")
        if _contains(req, "django"):
            frameworks.append("Django")
        if _contains(req, "flask"):
            frameworks.append("Flask")

    # Java frameworks
    if pom and _contains(pom, "spring-boot"):
        frameworks.append("Spring Boot")

    # Go frameworks
    if go_mod:
        if _contains(go_mod, "gin-gonic"):
            frameworks.append("Gin")
        if _contains(go_mod, "fiber"):
            frameworks.append("Fiber")

    return frameworks


def _detect_databases(
    file_paths: Sequence[str],
    file_contents: dict[str, str],
) -> list[str]:
    databases: list[str] = []
    found: set[str] = set()  # de-duplicate (e.g. pg detected twice)

    req = _file_content("requirements.txt", file_contents)
    pkg = _file_content("package.json", file_contents)
    compose = _file_content("docker-compose.yml", file_contents)

    def _add(db: str) -> None:
        if db not in found:
            found.add(db)
            databases.append(db)

    # Python deps
    if req:
        if _any_contains(req, "sqlalchemy", "psycopg"):
            _add("PostgreSQL")
        if _contains(req, "pymongo"):
            _add("MongoDB")
        if _contains(req, "redis"):
            _add("Redis")

    # JS deps
    if pkg:
        if _contains(pkg, '"mongoose"'):
            _add("MongoDB")
        if _contains(pkg, '"prisma"'):
            # Confirm via schema.prisma if available
            prisma_schema = _file_content("schema.prisma", file_contents)
            if not prisma_schema or _contains(prisma_schema, "postgresql") or not prisma_schema:
                # Default assumption for Prisma is PostgreSQL (its default provider)
                _add("PostgreSQL")

    # docker-compose
    if compose:
        if _contains(compose, "mysql"):
            _add("MySQL")
        if _contains(compose, "postgres"):
            _add("PostgreSQL")

    return databases


def _detect_infra(file_paths: Sequence[str]) -> list[str]:
    infra: list[str] = []
    paths = _path_set(file_paths)
    names = _basenames(file_paths)

    if "dockerfile" in names:
        infra.append("Docker")

    if "docker-compose.yml" in names or "docker-compose.yaml" in names:
        infra.append("Docker Compose")

    # GitHub Actions: any file under .github/workflows/
    if any(p.startswith(".github/workflows/") for p in paths):
        infra.append("GitHub Actions")

    # Kubernetes: a directory named kubernetes/ or k8s/ at any depth
    if any(
        segment in ("kubernetes", "k8s")
        for p in paths
        for segment in p.split("/")
    ):
        infra.append("Kubernetes")

    # Terraform: a directory named terraform/ at any depth
    if any("terraform" in p.split("/") for p in paths):
        infra.append("Terraform")

    return infra


def _detect_test_frameworks(file_contents: dict[str, str]) -> list[str]:
    test_frameworks: list[str] = []

    req = _file_content("requirements.txt", file_contents)
    pkg = _file_content("package.json", file_contents)

    if req and _contains(req, "pytest"):
        test_frameworks.append("pytest")
    if pkg:
        if _contains(pkg, '"jest"'):
            test_frameworks.append("Jest")
        if _contains(pkg, '"vitest"'):
            test_frameworks.append("Vitest")

    return test_frameworks


def _detect_package_manager(
    file_paths: Sequence[str],
    file_contents: dict[str, str],
) -> str | None:
    """
    Infer the primary package manager from lock files and config files.
    Priority: language-specific lock files > manifest presence.
    """
    names = _basenames(file_paths)

    # Python
    if "poetry.lock" in names:
        return "poetry"
    if "pipfile.lock" in names or "pipfile" in names:
        return "pipenv"
    if "requirements.txt" in names or "setup.py" in names or "pyproject.toml" in names:
        return "pip"

    # JavaScript / TypeScript
    if "pnpm-lock.yaml" in names:
        return "pnpm"
    if "yarn.lock" in names:
        return "yarn"
    if "package-lock.json" in names or "package.json" in names:
        return "npm"

    # Go
    if "go.sum" in names or "go.mod" in names:
        return "go modules"

    # Rust
    if "cargo.lock" in names or "cargo.toml" in names:
        return "cargo"

    # Ruby
    if "gemfile.lock" in names or "gemfile" in names:
        return "bundler"

    return None


# ──────────────────────────────────────────────────────────────────────────────
# Public entry point
# ──────────────────────────────────────────────────────────────────────────────


async def detect_stack(
    file_paths: Sequence[str],
    file_contents: dict[str, str],
) -> StackResult:
    """
    Analyse a repository's file tree and key file contents to infer its
    technology stack.

    Parameters
    ----------
    file_paths:
        Every file path in the repository (relative, forward-slash separated).
    file_contents:
        A mapping of ``{filename_or_relative_path: raw_text_content}`` for
        files whose content was fetched (e.g. ``package.json``,
        ``requirements.txt``).  Unknown / unbuffered files are simply absent.

    Returns
    -------
    StackResult
        Populated with only the items that were positively detected.
    """
    return StackResult(
        languages=_detect_languages(file_paths),
        frameworks=_detect_frameworks(file_contents),
        databases=_detect_databases(file_paths, file_contents),
        infra=_detect_infra(file_paths),
        test_frameworks=_detect_test_frameworks(file_contents),
        package_manager=_detect_package_manager(file_paths, file_contents),
    )


# ──────────────────────────────────────────────────────────────────────────────
# Convenience sync wrapper (useful in tests / CLI without an event loop)
# ──────────────────────────────────────────────────────────────────────────────


def detect_stack_sync(
    file_paths: Sequence[str],
    file_contents: dict[str, str],
) -> StackResult:
    """Synchronous thin wrapper around :func:`detect_stack`."""
    import asyncio

    return asyncio.run(detect_stack(file_paths, file_contents))