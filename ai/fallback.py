"""
ai/fallback.py
--------------
Pure-heuristic fallback layer for CodeAtlas.

Generates the same data shapes as the AI layer (call_llm + prompts) but using
only in-process logic: no network calls, no exceptions, always returns valid data.

Public API
----------
    fallback_summary(repo_name, stack, readme, top_level_dirs, file_list) -> dict
    fallback_diagram(stack, modules)                                        -> dict
    fallback_suggestions(stack)                                             -> list[dict]
"""

from __future__ import annotations

import re
import sys
import traceback
from pathlib import PurePosixPath
from typing import Any

# StackResult is imported lazily inside each function so that this module can
# be imported (and tested) even in isolation.  We type-hint with a string
# forward reference where needed.

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

# Known entry-point file names, ordered by priority.
# More specific / shallower names come first.
# Files inside `tests/` are listed last — they are valid entry points for
# test runners but should not be shown as the primary application entry point.
_ENTRY_POINT_NAMES: list[str] = [
    # Python
    "main.py", "app.py", "server.py", "asgi.py",
    "manage.py",                    # Django
    "__init__.py",                  # library packages (e.g. fastapi/__init__.py)
    "wsgi.py",                      # WSGI adapter — low priority
    # JavaScript / TypeScript
    "index.js", "index.ts",
    "server.js", "server.ts",
    "app.js", "app.ts",
    # Go
    "main.go", "cmd/main.go",
    # Rust
    "main.rs", "src/main.rs",
    # Java
    "Application.java",
]

# Framework → generic request-flow template
_FLOW_TEMPLATES: dict[str, str] = {
    "FastAPI":      "Request enters FastAPI app → routed via APIRouter → handler calls service layer → {db} layer",
    "Django":       "Request enters Django WSGI/ASGI → URL dispatcher → View/ViewSet → ORM → {db} layer",
    "Flask":        "Request enters Flask app → Blueprint route → view function → {db} layer",
    "Express":      "Request enters Express server → middleware chain → route handler → {db} layer",
    "Next.js":      "Browser request → Next.js routing → page/API route handler → {db} layer",
    "Fastify":      "Request enters Fastify server → plugin/middleware → route handler → {db} layer",
    "Spring Boot":  "Request enters Spring DispatcherServlet → @Controller → @Service → repository → {db} layer",
    "Gin":          "Request enters Gin engine → middleware stack → handler function → {db} layer",
    "Fiber":        "Request enters Fiber app → middleware chain → handler → {db} layer",
    "React":        "User action → React component → state update / API call → {db} layer",
}

_DEFAULT_FLOW = "Request enters {framework} app → processed through route handlers → {db} layer"

# Known top-level directory names → human-readable descriptions.
# Used by fallback_summary to produce useful module descriptions without AI.
_DIR_DESCRIPTIONS: dict[str, str] = {
    "src":          "Primary source code directory.",
    "app":          "Main application package.",
    "lib":          "Shared library code.",
    "core":         "Core business logic and shared utilities.",
    "pkg":          "Internal packages.",
    "internal":     "Private application packages (not exported).",
    "cmd":          "Command-line entry points.",
    "api":          "API route definitions and controllers.",
    "routers":      "Route handlers and URL dispatch.",
    "routes":       "Route definitions.",
    "controllers":  "Request handlers / controllers.",
    "views":        "View templates or view functions.",
    "middleware":   "HTTP middleware components.",
    "handlers":     "Request handler functions.",
    "graphql":      "GraphQL schema and resolvers.",
    "grpc":         "gRPC proto definitions and service implementations.",
    "models":       "Data models and ORM definitions.",
    "schemas":      "Request/response validation schemas.",
    "services":     "Business logic service layer.",
    "repositories": "Data access / repository layer.",
    "db":           "Database migrations, seeds, and query helpers.",
    "migrations":   "Database migration scripts.",
    "domain":       "Domain entities and business rules.",
    "entities":     "Domain entity definitions.",
    "components":   "Reusable UI components.",
    "pages":        "Page-level components or server-rendered pages.",
    "hooks":        "Custom React hooks.",
    "store":        "State management (Redux, Zustand, MobX, etc.).",
    "styles":       "Global stylesheets and design tokens.",
    "assets":       "Static assets: images, fonts, icons.",
    "public":       "Publicly served static files.",
    "static":       "Static files served directly by the web server.",
    "config":       "Application configuration and environment settings.",
    "settings":     "Settings / configuration files.",
    "deploy":       "Deployment manifests and infrastructure-as-code.",
    "infra":        "Infrastructure provisioning scripts.",
    "docker":       "Docker-related configuration files.",
    "k8s":          "Kubernetes manifests.",
    "terraform":    "Terraform infrastructure definitions.",
    ".github":      "GitHub Actions workflows and repository configuration.",
    "ci":           "Continuous integration pipeline configuration.",
    "tests":        "Automated test suite.",
    "test":         "Automated test suite.",
    "__tests__":    "Jest / JavaScript test files.",
    "spec":         "BDD / RSpec test specifications.",
    "e2e":          "End-to-end tests.",
    "integration":  "Integration tests.",
    "fixtures":     "Test fixtures and factory data.",
    "mocks":        "Mock objects and test doubles.",
    "docs":         "Project documentation.",
    "doc":          "Project documentation.",
    "docs_src":     "Source files for the documentation site (e.g. mkdocs).",
    "scripts":      "Utility and automation scripts.",
    "tools":        "Developer tooling and code-generation helpers.",
    "examples":     "Example code and usage demonstrations.",
    "samples":      "Sample projects and code snippets.",
    "notebooks":    "Jupyter notebooks for exploration and analysis.",
    "fastapi":      "FastAPI application — routing, dependency injection, and middleware.",
    "django":       "Django application — models, views, and URL configuration.",
    "flask":        "Flask application — blueprints and route definitions.",
    "backend":      "Backend server application.",
    "frontend":     "Frontend client application.",
    "web":          "Web layer — templates, static files, and HTTP handling.",
    "cli":          "Command-line interface definitions.",
    "workers":      "Background workers and job queues.",
    "tasks":        "Scheduled or async task definitions.",
    "events":       "Event definitions and event-driven handlers.",
    "kafka":        "Kafka producer/consumer configuration and handlers.",
    "proto":        "Protocol Buffer definitions.",
    "utils":        "General-purpose utility functions.",
    "helpers":      "Helper functions and shared utilities.",
    "common":       "Shared code used across multiple modules.",
    "shared":       "Shared code used across multiple modules.",
    "types":        "TypeScript type definitions.",
}


def _describe_dir(name: str) -> str:
    """Return a human-readable description for a top-level directory name."""
    return _DIR_DESCRIPTIONS.get(name, f"Top-level module or package: {name}.")


# --------------------------------------------------------------------------- #
# Internal helpers
# --------------------------------------------------------------------------- #


def _strip_markdown_to_plain(text: str) -> str:
    """
    Convert a Markdown/HTML string to plain prose text suitable for UI display.

    Removes (in order):
      - HTML tags and their content for block elements (<p>, <div>, <a>, <img>…)
      - Remaining HTML tags (keep inner text)
      - Markdown badge lines  [![alt](url)](url)
      - Markdown image lines  ![alt](url)
      - Markdown links        [text](url)  →  text
      - Inline code           `code`       →  code
      - Bold/italic           **x**, *x*, __x__, _x_  →  x
      - Markdown headings     # Title      (whole line removed)
      - Horizontal rules      ---  ===
      - Blockquote markers    > text       →  text
      - Excess whitespace
    """
    # Remove HTML block-level tags and their full content (script, style, etc.)
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", text, flags=re.DOTALL | re.IGNORECASE)
    # Remove remaining HTML tags, keeping inner text
    text = re.sub(r"<[^>]+>", "", text)
    # Badge lines: [![...](...)](#...) — the whole line is a badge row
    text = re.sub(r"^\s*(?:\[!\[.*?\]\(.*?\)\]\(.*?\)\s*)+$", "", text, flags=re.MULTILINE)
    # Standalone images: ![alt](url)
    text = re.sub(r"!\[.*?\]\(.*?\)", "", text)
    # Markdown links: [text](url) → text
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    # Inline code: `code` → code
    text = re.sub(r"`([^`]+)`", r"\1", text)
    # Bold+italic: ***x*** or **x** or *x* or __x__ or _x_
    text = re.sub(r"\*{1,3}([^\*]+)\*{1,3}", r"\1", text)
    text = re.sub(r"_{1,2}([^_]+)_{1,2}", r"\1", text)
    # Markdown headings: # H1 / ## H2 / etc — strip the # prefix, keep the text
    # This handles both "# Heading" (heading alone) and
    # "# Title Some prose" (heading prefix merged with prose on same line)
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    # Horizontal rules: --- / === on their own line → remove the whole line
    text = re.sub(r"^\s*[-=]{3,}\s*$", "", text, flags=re.MULTILINE)
    # Blockquote markers
    text = re.sub(r"^\s*>\s?", "", text, flags=re.MULTILINE)
    # Normalise whitespace
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def _first_paragraph(text: str, max_chars: int = 300) -> str:
    """
    Extract the first meaningful prose paragraph from README text.

    Strategy:
    1. Split the *raw* text on blank lines to get logical blocks.
    2. Discard blocks that consist entirely of headings, horizontal rules,
       badge lines, or HTML block elements (common in README headers).
    3. Strip Markdown/HTML from the first surviving block and return it.

    Falls back to the first ``max_chars`` characters of fully cleaned text
    if no prose block can be isolated.
    """
    if not text:
        return ""

    _HEADING_ONLY = re.compile(r"^\s*#{1,6}\s*\S{0,40}\s*$")  # # Title (short, no sentence)
    _HR          = re.compile(r"^\s*[-=*]{3,}\s*$")
    _BADGE_LINE  = re.compile(r"^\s*(?:\[!\[.*?\]\(.*?\)\]\(.*?\)\s*)+$")
    _HTML_BLOCK  = re.compile(r"^\s*<", re.IGNORECASE)
    _EMPTY       = re.compile(r"^\s*$")

    def _is_non_prose_line(ln: str) -> bool:
        return bool(
            _EMPTY.match(ln)
            or _HEADING_ONLY.match(ln)
            or _HR.match(ln)
            or _BADGE_LINE.match(ln)
            or _HTML_BLOCK.match(ln)
        )

    raw_blocks = re.split(r"\n{2,}", text.strip())

    for raw_block in raw_blocks:
        lines = raw_block.splitlines()
        # A block is "prose" if at least one of its lines is not a non-prose line
        if all(_is_non_prose_line(ln) for ln in lines if ln.strip()):
            continue   # heading-only / rule-only / badge-only block — skip
        # Strip Markdown from this prose block and return it
        cleaned_block = _strip_markdown_to_plain(raw_block)
        paragraph = " ".join(cleaned_block.split())
        if len(paragraph) >= 10:
            return paragraph[:max_chars]

    # Last resort: strip everything and return the first max_chars
    flat = " ".join(_strip_markdown_to_plain(text).split())
    return flat[:max_chars]


def _db_label(stack: Any) -> str:
    """Return the first detected database name or 'data' as a fallback."""
    dbs = getattr(stack, "databases", [])
    return dbs[0] if dbs else "data"


def _primary_framework(stack: Any) -> str:
    """Return the first detected framework or 'the' as a fallback."""
    fws = getattr(stack, "frameworks", [])
    return fws[0] if fws else ""


def _safe_call(func_name: str, default: Any, *args: Any, **kwargs: Any) -> Any:  # noqa: ANN401
    """
    Internal guard: call the decorated function; on ANY exception log to stderr
    and return *default*.  This ensures callers are always protected.
    """
    # (This is used by the public wrappers below, not by the core logic.)
    raise NotImplementedError("_safe_call is a design note, not invoked directly")


# --------------------------------------------------------------------------- #
# 1 – fallback_summary
# --------------------------------------------------------------------------- #


def fallback_summary(
    repo_name: str,
    stack: Any,           # StackResult
    readme: str,
    top_level_dirs: list[str],
    file_list: list[str],
) -> dict:
    """
    Generate a summary dict matching the shape expected by the AI layer.

    Never raises; returns a minimal-but-valid dict on any unexpected input.

    Args:
        repo_name:      ``"owner/repo"`` string.
        stack:          :class:`~analyzers.stack_detector.StackResult` instance.
        readme:         Raw README text (may be empty).
        top_level_dirs: List of top-level directory names (e.g. ``["src","tests"]``).
        file_list:      Full flat list of file paths in the repo.

    Returns:
        Dict with keys: ``summary``, ``modules``, ``entry_points``, ``request_flow``.
    """
    try:
        languages: list[str] = getattr(stack, "languages", [])
        frameworks: list[str] = getattr(stack, "frameworks", [])
        databases: list[str] = getattr(stack, "databases", [])

        # ── summary ─────────────────────────────────────────────────────────
        readme_para = _first_paragraph(readme, max_chars=300)

        tech_parts: list[str] = []
        if languages:
            tech_parts.append(f"languages: {', '.join(languages)}")
        if frameworks:
            tech_parts.append(f"frameworks: {', '.join(frameworks)}")
        if databases:
            tech_parts.append(f"databases: {', '.join(databases)}")

        tech_sentence = (
            f"Built with {'; '.join(tech_parts)}." if tech_parts else ""
        )

        if readme_para and tech_sentence:
            summary = f"{readme_para} {tech_sentence}"
        elif readme_para:
            summary = readme_para
        elif tech_sentence:
            summary = f"{repo_name} — {tech_sentence}"
        else:
            summary = f"{repo_name} — no additional metadata detected."

        # ── modules (from top-level directories) ────────────────────────────
        modules: list[dict] = []
        for d in sorted(set(top_level_dirs)):
            if not d or d.startswith("."):
                continue
            modules.append({
                "name": d,
                "path": d,
                "description": _describe_dir(d),
            })

        # ── entry_points ────────────────────────────────────────────────────
        file_set = set(file_list)
        basename_to_paths: dict[str, list[str]] = {}
        for fp in file_list:
            bn = PurePosixPath(fp).name
            basename_to_paths.setdefault(bn, []).append(fp)

        _TEST_DIRS = {"tests", "test", "spec", "__tests__"}

        def _candidate_key(p: str) -> tuple:
            first = p.split("/")[0] if "/" in p else ""
            in_test = 1 if first in _TEST_DIRS else 0
            return (in_test, p.count("/"), p)

        # Two-pass entry point resolution:
        #   Pass 1 — collect only paths NOT inside a test directory.
        #   Pass 2 — if no entry points found at all, allow test-dir paths as a
        #            last resort (e.g. a repo whose only main.py lives in tests/).
        entry_points: list[str] = []
        seen: set[str] = set()
        deferred: list[str] = []   # test-dir candidates held for pass 2

        for name in _ENTRY_POINT_NAMES:
            # Exact full-path match (non-test only in pass 1)
            if name in file_set:
                first_part = name.split("/")[0] if "/" in name else ""
                in_test = first_part in _TEST_DIRS
                if not in_test and name not in seen:
                    entry_points.append(name)
                    seen.add(name)
                    continue
                elif in_test and name not in seen:
                    deferred.append(name)
                    seen.add(name)
                    continue

            # Basename match
            bn = PurePosixPath(name).name
            if bn in basename_to_paths:
                candidates = sorted(basename_to_paths[bn], key=_candidate_key)
                for c in candidates:
                    if c in seen:
                        continue
                    first_part = c.split("/")[0] if "/" in c else ""
                    if first_part in _TEST_DIRS:
                        # Hold for pass 2 — one deferred per name at most
                        deferred.append(c)
                        seen.add(c)
                        break
                    else:
                        entry_points.append(c)
                        seen.add(c)
                        break

        # Pass 2: only use deferred (test-dir) paths if nothing was found
        if not entry_points:
            entry_points = deferred[:3]

        # ── request_flow ────────────────────────────────────────────────────
        primary_fw = _primary_framework(stack)
        db_label = _db_label(stack)
        template = _FLOW_TEMPLATES.get(primary_fw, _DEFAULT_FLOW)
        request_flow = template.format(
            framework=primary_fw or "application",
            db=db_label,
        )

        return {
            "summary": summary,
            "modules": modules,
            "entry_points": entry_points,
            "request_flow": request_flow,
        }

    except Exception:  # pragma: no cover — safety net
        traceback.print_exc(file=sys.stderr)
        return {
            "summary": f"{repo_name} — summary unavailable.",
            "modules": [],
            "entry_points": [],
            "request_flow": "Request flow unavailable.",
        }


# --------------------------------------------------------------------------- #
# 2 – fallback_diagram
# --------------------------------------------------------------------------- #


def _make_node(node_id: str, label: str) -> dict:
    """Build a node dict in the canonical CodeAtlas shape (matches diagram_parser output)."""
    return {"id": node_id, "label": label}


def _make_edge(source: str, target: str, label: str = "") -> dict:
    """Build an edge dict in the canonical CodeAtlas shape (matches diagram_parser output)."""
    return {"from": source, "to": target, "label": label}


def fallback_diagram(
    stack: Any,           # StackResult
    modules: list[str],
) -> dict:
    """
    Generate a diagram dict matching the shape expected by the AI layer.

    Always produces a ``mermaid_source`` string (``graph TD`` syntax), plus
    ``nodes`` and ``edges`` lists in the canonical CodeAtlas shape::

        nodes: [{"id": str, "label": str}, ...]
        edges: [{"from": str, "to": str, "label": str}, ...]

    The topology is::

        Client → [Framework/API layer] → [Module(s)] → [Database if detected]

    Never raises.

    Args:
        stack:   :class:`~analyzers.stack_detector.StackResult` instance.
        modules: List of module/directory name strings.

    Returns:
        Dict with keys: ``mermaid_source`` (str), ``nodes`` (list), ``edges`` (list).
    """
    try:
        frameworks: list[str] = getattr(stack, "frameworks", [])
        databases: list[str] = getattr(stack, "databases", [])

        primary_fw = frameworks[0] if frameworks else "App"
        primary_db = databases[0] if databases else None

        # ── Choose up to 2 service nodes from modules ────────────────────────
        _SKIP = {"node_modules", ".git", "__pycache__", "venv", ".venv", "dist", "build"}
        service_modules = [m for m in modules if m not in _SKIP][:2]
        if not service_modules:
            service_modules = ["Services"]

        # ── Build node and edge lists ─────────────────────────────────────────
        nodes: list[dict] = []
        edges: list[dict] = []
        mermaid_node_lines: list[str] = []
        mermaid_edge_lines: list[str] = []

        prev_id = "Client"

        # 1. Client
        nodes.append(_make_node("Client", "Client"))
        mermaid_node_lines.append('    Client["Client"]')

        # 2. Framework / API layer
        fw_id = "framework"
        nodes.append(_make_node(fw_id, primary_fw))
        mermaid_node_lines.append(f'    {fw_id}["{primary_fw}"]')
        edges.append(_make_edge(prev_id, fw_id, "HTTP"))
        mermaid_edge_lines.append(f"    {prev_id} -->|HTTP| {fw_id}")
        prev_id = fw_id

        # 3. Service / module nodes
        for idx, mod in enumerate(service_modules):
            mod_id = f"mod_{idx}"
            nodes.append(_make_node(mod_id, mod))
            mermaid_node_lines.append(f'    {mod_id}["{mod}"]')
            edges.append(_make_edge(prev_id, mod_id))
            mermaid_edge_lines.append(f"    {prev_id} --> {mod_id}")
            prev_id = mod_id

        # 4. Database (optional)
        if primary_db:
            db_id = "database"
            nodes.append(_make_node(db_id, primary_db))
            mermaid_node_lines.append(f'    {db_id}[("{primary_db}")]')
            edges.append(_make_edge(prev_id, db_id, "query"))
            mermaid_edge_lines.append(f"    {prev_id} -->|query| {db_id}")

        # ── Assemble Mermaid source ───────────────────────────────────────────
        mermaid_source = "\n".join(
            ["graph TD"] + mermaid_node_lines + mermaid_edge_lines
        )

        return {"mermaid_source": mermaid_source, "nodes": nodes, "edges": edges}

    except Exception:  # pragma: no cover — safety net
        traceback.print_exc(file=sys.stderr)
        return {
            "mermaid_source": 'graph TD\n    Client["Client"] --> App["App"]',
            "nodes": [_make_node("Client", "Client"), _make_node("App", "App")],
            "edges": [_make_edge("Client", "App")],
        }


# --------------------------------------------------------------------------- #
# 3 – fallback_suggestions
# --------------------------------------------------------------------------- #

# Each rule is a tuple of:
#   (condition_key, category, severity, title, detail, file_hint_or_None)
#
# condition_key is matched against the _eval_conditions result dict.

_RULE_BANK: list[tuple[str, str, str, str, str, str | None]] = [
    # ── Security ────────────────────────────────────────────────────────────
    (
        "has_fastapi",
        "security", "high",
        "Add rate limiting with slowapi",
        "FastAPI has no built-in rate limiting. Add `slowapi` (a Starlette-compatible "
        "limiter) to protect public endpoints from abuse and brute-force attacks.",
        "main.py",
    ),
    (
        "has_django",
        "security", "high",
        "Verify DEBUG=False in production",
        "Django's DEBUG=True exposes full stack traces and internal settings to anyone "
        "who triggers a 500 error. Confirm DEBUG is driven by an environment variable "
        "and defaults to False.",
        "settings.py",
    ),
    (
        "has_express",
        "security", "high",
        "Use helmet.js for security headers",
        "Express does not set security-relevant HTTP headers by default. Add the "
        "`helmet` middleware to enable CSP, HSTS, X-Frame-Options, and more with "
        "one line.",
        "index.js",
    ),
    # ── Performance ──────────────────────────────────────────────────────────
    (
        "has_postgres",
        "performance", "medium",
        "Ensure connection pooling is configured",
        "PostgreSQL has a limited connection ceiling. Configure a connection pool "
        "appropriate to your stack — HikariCP (Java/Spring Boot), asyncpg + "
        "SQLAlchemy async engine (Python), or pgbouncer as a sidecar — to avoid "
        "exhausting the server under load.",
        None,
    ),
    (
        "has_mongodb",
        "performance", "medium",
        "Enforce a MongoDB document schema at the application layer",
        "MongoDB's schema-less nature can lead to inconsistent documents over time. "
        "Enforce a schema at the application layer — Mongoose (Node.js), "
        "MongoEngine / Pydantic + Motor (Python), or Spring Data MongoDB "
        "validation annotations (Java/Kotlin) — to improve reliability and query performance.",
        None,
    ),
    # ── Quality ──────────────────────────────────────────────────────────────
    (
        "no_tests",
        "quality", "high",
        "No test framework detected",
        "No testing library was found in the dependency manifests. Add pytest (Python), "
        "Jest/Vitest (JS/TS), or the equivalent for your stack to catch regressions "
        "early and enable safe refactoring.",
        None,
    ),
    (
        "docker_no_compose",
        "quality", "low",
        "Consider docker-compose for local development",
        "A Dockerfile is present but no docker-compose.yml was found. Adding a Compose "
        "file makes it easy to spin up the full stack (app + database + cache) with a "
        "single command, reducing onboarding friction.",
        "docker-compose.yml",
    ),
    (
        "no_ci",
        "quality", "medium",
        "Add a CI pipeline",
        "No CI configuration was detected (GitHub Actions, GitLab CI, CircleCI, etc.). "
        "A CI pipeline that runs tests and linting on every pull request is one of the "
        "highest-ROI investments for long-term code quality.",
        ".github/workflows/ci.yml",
    ),
    # ── Scalability ──────────────────────────────────────────────────────────
    (
        "has_docker",
        "scalability", "low",
        "Define resource limits in container config",
        "Container orchestrators (Docker Swarm, Kubernetes) benefit from explicit CPU "
        "and memory limits. Add `mem_limit` / `cpus` in docker-compose.yml or "
        "resource requests/limits in Kubernetes manifests to prevent noisy-neighbour "
        "issues.",
        "docker-compose.yml",
    ),
    (
        "has_kafka",
        "scalability", "medium",
        "Tune Kafka consumer group concurrency",
        "Kafka is present but default consumer-group parallelism is often left at 1. "
        "Match the number of consumers to the partition count for the topic to maximise "
        "throughput and minimise consumer lag.",
        None,
    ),
]

# Universal fallback suggestions used when fewer than 3 rules match
_UNIVERSAL_FALLBACKS: list[dict] = [
    {
        "category": "quality",
        "severity": "medium",
        "title": "Add or improve inline documentation",
        "detail": (
            "Well-documented code reduces onboarding time and maintenance cost. "
            "Add docstrings to all public functions and classes, and keep a "
            "concise CONTRIBUTING.md at the repository root."
        ),
    },
    {
        "category": "security",
        "severity": "medium",
        "title": "Store secrets in environment variables",
        "detail": (
            "Never commit credentials, API keys, or connection strings to source "
            "control. Use a .env file (git-ignored) locally and inject secrets via "
            "environment variables or a secrets manager in production."
        ),
    },
    {
        "category": "performance",
        "severity": "low",
        "title": "Profile before optimising",
        "detail": (
            "Premature optimisation is costly. Use a profiler (cProfile, py-spy, "
            "clinic.js, pprof) on a realistic workload first, then address the "
            "actual hot-paths rather than guessing."
        ),
    },
]


def _eval_conditions(stack: Any) -> dict[str, bool]:
    """
    Evaluate all rule conditions against *stack* and return a bool dict.

    This is extracted into its own function to make testing trivial.
    """
    frameworks: list[str] = getattr(stack, "frameworks", [])
    databases: list[str] = getattr(stack, "databases", [])
    infra: list[str] = getattr(stack, "infra", [])
    test_fws: list[str] = getattr(stack, "test_frameworks", [])

    fw_set = {f.lower() for f in frameworks}
    db_set = {d.lower() for d in databases}
    infra_set = {i.lower() for i in infra}

    has_docker = "docker" in infra_set
    has_compose = "docker compose" in infra_set
    has_ci = (
        "github actions" in infra_set
        or any("ci" in i for i in infra_set)
    )

    return {
        "has_fastapi":       "fastapi" in fw_set,
        "has_django":        "django" in fw_set,
        "has_express":       "express" in fw_set,
        "has_postgres":      "postgresql" in db_set,
        "has_mongodb":       "mongodb" in db_set,
        "no_tests":          len(test_fws) == 0,
        "docker_no_compose": has_docker and not has_compose,
        "no_ci":             not has_ci,
        "has_docker":        has_docker,
        "has_kafka":         "kafka" in infra_set,
    }


def fallback_suggestions(stack: Any) -> list[dict]:
    """
    Return a list of improvement suggestions derived from the detected stack.

    Matches the shape expected by the AI layer::

        [
          {
            "category":  "security|performance|scalability|quality",
            "severity":  "high|medium|low",
            "title":     "Short title",
            "detail":    "1-2 sentence explanation and fix.",
            "file_hint": "path/to/file"   # may be absent
          },
          ...
        ]

    Always returns at least 3 suggestions regardless of stack. Never raises.

    Args:
        stack: :class:`~analyzers.stack_detector.StackResult` instance.

    Returns:
        List of suggestion dicts, ordered by severity (high → medium → low).
    """
    try:
        conditions = _eval_conditions(stack)
        matched: list[dict] = []

        for condition_key, category, severity, title, detail, file_hint in _RULE_BANK:
            if conditions.get(condition_key, False):
                suggestion: dict = {
                    "category": category,
                    "severity": severity,
                    "title": title,
                    "detail": detail,
                }
                if file_hint:
                    suggestion["file_hint"] = file_hint
                matched.append(suggestion)

        # Pad with universal fallbacks until we have at least 3
        fallback_iter = iter(_UNIVERSAL_FALLBACKS)
        while len(matched) < 3:
            try:
                matched.append(next(fallback_iter))
            except StopIteration:
                # Should never happen as _UNIVERSAL_FALLBACKS has 3 entries,
                # but guard just in case.
                break

        # Sort: high → medium → low
        _SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}
        matched.sort(key=lambda s: _SEVERITY_ORDER.get(s["severity"], 9))

        return matched

    except Exception:  # pragma: no cover — safety net
        traceback.print_exc(file=sys.stderr)
        return list(_UNIVERSAL_FALLBACKS)