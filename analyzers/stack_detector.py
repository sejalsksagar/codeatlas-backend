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
    Return the content for *key*, preferring the shallowest (most root-level)
    match when multiple files share the same basename.

    e.g. key="requirements.txt" will prefer "requirements.txt" over
    "docs/requirements.txt" or "tests/requirements.txt".

    Returns an empty string when no match is found.
    """
    key_lower = key.lower()

    # Collect all matches with their depth (number of path segments - 1)
    matches: list[tuple[int, str]] = []
    for stored_key, content in file_contents.items():
        normalised = stored_key.replace("\\", "/")
        if PurePosixPath(normalised).name.lower() == key_lower:
            depth = normalised.count("/")
            matches.append((depth, content))

    if not matches:
        return ""

    # Return content of the shallowest file (lowest depth wins)
    matches.sort(key=lambda t: t[0])
    return matches[0][1].lower()


def _all_file_contents(key: str, file_contents: dict[str, str]) -> list[str]:
    """
    Return lowercased content for *every* file whose basename matches *key*.
    Used when we want to scan all copies (e.g. all requirements.txt files).
    """
    key_lower = key.lower()
    return [
        content.lower()
        for stored_key, content in file_contents.items()
        if PurePosixPath(stored_key.replace("\\", "/")).name.lower() == key_lower
    ]


def _contains(content: str, *terms: str) -> bool:
    """True when ALL terms appear in content (content is pre-lowered)."""
    return all(term.lower() in content for term in terms)


def _any_contains(content: str, *terms: str) -> bool:
    """True when ANY term appears in content (content is pre-lowered)."""
    return any(term.lower() in content for term in terms)


def _any_file_contains(key: str, file_contents: dict[str, str], *terms: str) -> bool:
    """
    True when ANY copy of *key* (by basename) contains ANY of *terms*.
    Useful for files like requirements.txt that may exist at multiple depths.
    """
    return any(
        _any_contains(content, *terms)
        for content in _all_file_contents(key, file_contents)
    )


def _path_set(file_paths: Sequence[str]) -> set[str]:
    """Normalise to forward-slash, lower-case."""
    return {p.replace("\\", "/").lower() for p in file_paths}


def _basenames(file_paths: Sequence[str]) -> set[str]:
    return {PurePosixPath(p).name.lower() for p in file_paths}


# ──────────────────────────────────────────────────────────────────────────────
# Detection sub-routines
# ──────────────────────────────────────────────────────────────────────────────


def _detect_languages(file_paths: Sequence[str]) -> list[str]:
    """
    Count file extensions; return languages sorted by descending frequency.
    """
    EXT_MAP: dict[str, str] = {
        ".py":  "Python",
        ".js":  "JavaScript/TypeScript",
        ".ts":  "JavaScript/TypeScript",
        ".jsx": "JavaScript/TypeScript",
        ".tsx": "JavaScript/TypeScript",
        ".go":  "Go",
        ".java":"Java",
        ".rs":  "Rust",
        ".rb":  "Ruby",
        ".cs":  "C#",
        ".php": "PHP",
    }

    counts: dict[str, int] = {}
    for path in file_paths:
        suffix = PurePosixPath(path).suffix.lower()
        if suffix in EXT_MAP:
            lang = EXT_MAP[suffix]
            counts[lang] = counts.get(lang, 0) + 1

    return [lang for lang, _ in sorted(counts.items(), key=lambda kv: -kv[1])]


def _detect_frameworks(file_contents: dict[str, str]) -> list[str]:
    frameworks: list[str] = []
    found: set[str] = set()

    def _add(fw: str) -> None:
        if fw not in found:
            found.add(fw)
            frameworks.append(fw)

    # ── Root-level config files (shallowest copy wins) ────────────────────────
    pkg     = _file_content("package.json",    file_contents)
    req     = _file_content("requirements.txt", file_contents)
    pyproj  = _file_content("pyproject.toml",  file_contents)
    pom     = _file_content("pom.xml",         file_contents)
    go_mod  = _file_content("go.mod",          file_contents)

    # ── JavaScript / TypeScript (Next before React — order matters) ───────────
    if pkg:
        if _contains(pkg, '"next"'):
            _add("Next.js")
        elif _contains(pkg, '"react"'):
            _add("React")
        if _contains(pkg, '"express"'):
            _add("Express")
        if _contains(pkg, '"fastify"'):
            _add("Fastify")

    # ── Python — check requirements.txt AND pyproject.toml ───────────────────
    # We also scan ALL copies of requirements.txt (root + extras like
    # requirements-dev.txt won't match, but multiple requirements.txt files
    # in subdirectories will).
    python_sources = [req, pyproj] + _all_file_contents("requirements.txt", file_contents)

    for src in python_sources:
        if not src:
            continue
        if _contains(src, "fastapi"):
            _add("FastAPI")
        if _contains(src, "django"):
            _add("Django")
        if _contains(src, "flask"):
            _add("Flask")

    # ── Java ─────────────────────────────────────────────────────────────────
    if pom and _contains(pom, "spring-boot"):
        _add("Spring Boot")

    # ── Go ───────────────────────────────────────────────────────────────────
    if go_mod:
        if _contains(go_mod, "gin-gonic"):
            _add("Gin")
        if _contains(go_mod, "fiber"):
            _add("Fiber")

    return frameworks


def _detect_databases(
    file_paths: Sequence[str],
    file_contents: dict[str, str],
) -> list[str]:
    databases: list[str] = []
    found: set[str] = set()

    def _add(db: str) -> None:
        if db not in found:
            found.add(db)
            databases.append(db)

    pkg     = _file_content("package.json",      file_contents)
    compose = _file_content("docker-compose.yml", file_contents)
    pom     = _file_content("pom.xml",            file_contents)

    # Python: requirements.txt + pyproject.toml
    pyproj     = _file_content("pyproject.toml", file_contents)
    py_sources = _all_file_contents("requirements.txt", file_contents) + [pyproj]
    for src in py_sources:
        if not src:
            continue
        if _any_contains(src, "sqlalchemy", "psycopg"):
            _add("PostgreSQL")
        if _contains(src, "pymongo"):
            _add("MongoDB")
        if _contains(src, "redis"):
            _add("Redis")

    # Java: pom.xml — match XML artifactId / groupId patterns
    if pom:
        if _any_contains(pom, ">postgresql<", "org.postgresql", "pgjdbc"):
            _add("PostgreSQL")
        if _any_contains(pom, ">mysql-connector", "com.mysql", ">r2dbc-mysql<"):
            _add("MySQL")
        if _any_contains(pom, "data-mongodb", "flapdoodle.embed.mongo"):
            _add("MongoDB")
        if _any_contains(pom, "data-redis", ">jedis<", ">lettuce-core<"):
            _add("Redis")
        if _any_contains(pom, ">h2<", "com.h2database"):
            _add("H2 (in-memory)")
        if _any_contains(pom, "data-cassandra", "cassandra-driver"):
            _add("Cassandra")

    # JavaScript: package.json
    if pkg:
        if _contains(pkg, '"mongoose"'):
            _add("MongoDB")
        if _contains(pkg, '"prisma"'):
            prisma_schema = _file_content("schema.prisma", file_contents)
            if not prisma_schema or _contains(prisma_schema, "postgresql"):
                _add("PostgreSQL")
        if _any_contains(pkg, '"pg"', '"postgres"', '"@neondatabase/serverless"'):
            _add("PostgreSQL")
        if _any_contains(pkg, '"mysql2"', '"mysql"'):
            _add("MySQL")
        if _any_contains(pkg, '"ioredis"', '"redis"'):
            _add("Redis")

    # docker-compose.yml: image names
    if compose:
        if _any_contains(compose, "image: mysql", "image: mariadb"):
            _add("MySQL")
        if _any_contains(compose, "image: postgres", "image: postgis"):
            _add("PostgreSQL")
        if _any_contains(compose, "image: mongo", "image: bitnami/mongodb"):
            _add("MongoDB")
        if _any_contains(compose, "image: redis", "image: bitnami/redis"):
            _add("Redis")

    return databases



def _detect_infra(file_paths: Sequence[str], file_contents: dict[str, str] = {}) -> list[str]:
    infra: list[str] = []
    found: set[str] = set()

    def _add(item: str) -> None:
        if item not in found:
            found.add(item)
            infra.append(item)

    paths = _path_set(file_paths)
    names = _basenames(file_paths)

    if "dockerfile" in names:
        _add("Docker")
    if "docker-compose.yml" in names or "docker-compose.yaml" in names:
        _add("Docker Compose")
    if any(p.startswith(".github/workflows/") for p in paths):
        _add("GitHub Actions")
    if any(seg in ("kubernetes", "k8s") for p in paths for seg in p.split("/")):
        _add("Kubernetes")
    if any("terraform" in p.split("/") for p in paths):
        _add("Terraform")

    # Kafka: pom.xml, package.json, requirements.txt, or docker-compose image
    pom     = _file_content("pom.xml",            file_contents)
    pkg     = _file_content("package.json",        file_contents)
    compose = _file_content("docker-compose.yml",  file_contents)
    py_srcs = _all_file_contents("requirements.txt", file_contents)

    if pom and _any_contains(pom, "spring-kafka", "kafka-clients", "kafka-streams"):
        _add("Kafka")
    if pkg and _any_contains(pkg, '"kafkajs"', '"kafka-node"', '"@confluentinc/kafka-javascript"'):
        _add("Kafka")
    if any(_contains(s, "kafka-python") or _contains(s, "confluent-kafka") for s in py_srcs if s):
        _add("Kafka")
    if compose and _any_contains(compose, "image: confluentinc/cp-kafka", "image: bitnami/kafka",
                                  "image: apache/kafka", "confluentinc/cp-zookeeper"):
        _add("Kafka")

    return infra


def _detect_test_frameworks(file_contents: dict[str, str]) -> list[str]:
    test_frameworks: list[str] = []
    found: set[str] = set()

    def _add(tf: str) -> None:
        if tf not in found:
            found.add(tf)
            test_frameworks.append(tf)

    pkg    = _file_content("package.json",   file_contents)
    pyproj = _file_content("pyproject.toml", file_contents)
    pom    = _file_content("pom.xml",        file_contents)

    # Python: requirements.txt files + pyproject.toml
    py_sources = _all_file_contents("requirements.txt", file_contents) + [pyproj]
    for src in py_sources:
        if src and _contains(src, "pytest"):
            _add("pytest")

    # Java: pom.xml test-scoped dependencies
    if pom:
        # JUnit 5 (jupiter) or JUnit 4
        if _any_contains(pom, "junit-jupiter", "junit-vintage", ">junit<"):
            _add("JUnit")
        # Mockito
        if _contains(pom, "mockito"):
            _add("Mockito")
        # Spring Boot Test — canonical starter OR individual *-test starters
        # (some projects list spring-boot-starter-data-jpa-test etc. individually)
        if _any_contains(pom, "spring-boot-starter-test", "spring-boot-test",
                         "starter-data-jpa-test", "starter-webmvc-test",
                         "starter-kafka-test", "starter-web-test"):
            _add("Spring Boot Test")
        # maven-surefire is the standard JUnit runner in Maven builds
        if _contains(pom, "maven-surefire-plugin"):
            _add("JUnit")
        # Testcontainers
        if _contains(pom, "testcontainers"):
            _add("Testcontainers")

    # JavaScript / TypeScript
    if pkg:
        if _contains(pkg, '"jest"'):
            _add("Jest")
        if _contains(pkg, '"vitest"'):
            _add("Vitest")
        if _contains(pkg, '"mocha"'):
            _add("Mocha")
        if _contains(pkg, '"jasmine"'):
            _add("Jasmine")

    return test_frameworks


def _detect_package_manager(
    file_paths: Sequence[str],
    file_contents: dict[str, str],
) -> str | None:
    """
    Infer the primary package manager.
    Priority: lock files > manifest files.
    """
    names = _basenames(file_paths)

    # Python — check pyproject.toml build-backend to distinguish poetry vs pip
    if "poetry.lock" in names:
        return "poetry"
    if "pipfile.lock" in names or "pipfile" in names:
        return "pipenv"
    if "uv.lock" in names:
        return "uv"
    if "pyproject.toml" in names:
        pyproj = _file_content("pyproject.toml", file_contents)
        if pyproj and "poetry" in pyproj:
            return "poetry"
        return "pip"
    if "requirements.txt" in names or "setup.py" in names:
        return "pip"

    # JavaScript / TypeScript
    if "pnpm-lock.yaml" in names:
        return "pnpm"
    if "yarn.lock" in names:
        return "yarn"
    if "package-lock.json" in names or "package.json" in names:
        return "npm"

    # Go / Rust / Ruby
    if "go.sum" in names or "go.mod" in names:
        return "go modules"
    if "cargo.lock" in names or "cargo.toml" in names:
        return "cargo"
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
        Mapping of ``{path: raw_text}`` for files whose content was fetched.
        Typically the output of fetching ``get_key_files()`` paths.

    Returns
    -------
    StackResult
        Populated with only the items that were positively detected.
    """
    return StackResult(
        languages=_detect_languages(file_paths),
        frameworks=_detect_frameworks(file_contents),
        databases=_detect_databases(file_paths, file_contents),
        infra=_detect_infra(file_paths, file_contents),
        test_frameworks=_detect_test_frameworks(file_contents),
        package_manager=_detect_package_manager(file_paths, file_contents),
    )


def detect_stack_sync(
    file_paths: Sequence[str],
    file_contents: dict[str, str],
) -> StackResult:
    """Synchronous thin wrapper around :func:`detect_stack`."""
    import asyncio
    return asyncio.run(detect_stack(file_paths, file_contents))