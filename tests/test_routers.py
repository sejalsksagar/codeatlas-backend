"""
tests/test_routers.py
---------------------
Unit tests for the three FastAPI routers and the diagram parser.

Run:
    pytest tests/test_routers.py -v

All external I/O (GitHubClient, call_llm) is patched with unittest.mock so
these tests run without a network connection or valid tokens.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# --------------------------------------------------------------------------- #
# Minimal FastAPI app fixture
# --------------------------------------------------------------------------- #
# We build a thin app that mounts only the three routers so tests are isolated.


@pytest.fixture(scope="module")
def app():
    from fastapi import FastAPI
    from routers.analyze import router as analyze_router
    from routers.diagram import router as diagram_router
    from routers.suggestions import router as suggestions_router

    application = FastAPI()
    application.include_router(analyze_router)
    application.include_router(diagram_router)
    application.include_router(suggestions_router)
    return application


@pytest.fixture(scope="module")
def client(app):
    return TestClient(app)


# --------------------------------------------------------------------------- #
# Shared mock data
# --------------------------------------------------------------------------- #

_REPO_URL = "https://github.com/testowner/testrepo"
_FILE_PATHS = [
    "README.md",
    "requirements.txt",
    "main.py",
    "src/api/routes.py",
    "src/models/user.py",
    "tests/test_main.py",
]
_FILE_CONTENTS = {
    "README.md": "# TestRepo\nA sample FastAPI project.",
    "requirements.txt": "fastapi\nuvicorn\npytest\npsycopg2-binary\n",
}
_STACK_DICT = {
    "languages": ["Python"],
    "frameworks": ["FastAPI"],
    "databases": ["PostgreSQL"],
    "infra": ["Docker"],
    "test_frameworks": ["pytest"],
    "package_manager": "pip",
}
_LLM_SUMMARY = json.dumps(
    {
        "summary": "A FastAPI web service for managing users.",
        "modules": [{"name": "src", "path": "src", "description": "Application source."}],
        "entry_points": ["main.py"],
        "request_flow": "HTTP → FastAPI router → handler → PostgreSQL.",
    }
)
_LLM_DIAGRAM = "graph TD\n    A[Client] --> B[FastAPI]\n    B --> C[(PostgreSQL)]"
_LLM_SUGGESTIONS = json.dumps(
    [
        {
            "category": "security",
            "severity": "high",
            "title": "Rotate secrets regularly",
            "detail": "Use environment variables and rotate them on a schedule.",
        }
    ]
    * 5
)


# =========================================================================== #
# /analyze  tests
# =========================================================================== #


class TestAnalyzeRouter:

    def _patch_github(self):
        """Return a context manager that patches GitHubClient with happy-path data."""
        mock_gh = AsyncMock()
        mock_gh.get_tree.return_value = _FILE_PATHS
        mock_gh.get_file_content.side_effect = lambda o, r, b, p: _FILE_CONTENTS.get(p, "")
        mock_gh.__aenter__ = AsyncMock(return_value=mock_gh)
        mock_gh.__aexit__ = AsyncMock(return_value=None)
        return patch("routers.analyze.GitHubClient", return_value=mock_gh)

    def test_happy_path_with_llm(self, client):
        """LLM returns valid JSON → AnalyzeResponse with used_fallback=False."""
        with (
            self._patch_github(),
            patch("routers.analyze.call_llm", new=AsyncMock(return_value=_LLM_SUMMARY)),
            patch("routers.analyze.settings") as mock_settings,
        ):
            mock_settings.GITHUB_TOKEN = ""
            mock_settings.GITHUB_MODELS_TOKEN = "tok"

            resp = client.post("/analyze/", json={"repo_url": _REPO_URL, "branch": "main"})

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["repo"] == "testowner/testrepo"
        assert data["used_fallback"] is False
        assert "FastAPI" in data["stack"]["frameworks"]
        assert data["summary"] == "A FastAPI web service for managing users."

    def test_happy_path_fallback_on_llm_error(self, client):
        """LLMUnavailableError → used_fallback=True, valid response."""
        from ai.github_models import LLMUnavailableError

        with (
            self._patch_github(),
            patch("routers.analyze.call_llm", side_effect=LLMUnavailableError("down")),
            patch("routers.analyze.settings") as mock_settings,
        ):
            mock_settings.GITHUB_TOKEN = ""
            mock_settings.GITHUB_MODELS_TOKEN = "tok"

            resp = client.post("/analyze/", json={"repo_url": _REPO_URL})

        assert resp.status_code == 200
        data = resp.json()
        assert data["used_fallback"] is True
        assert data["summary"] is not None

    def test_no_token_uses_fallback(self, client):
        """When GITHUB_MODELS_TOKEN is empty, skip LLM and use fallback."""
        with (
            self._patch_github(),
            patch("routers.analyze.settings") as mock_settings,
        ):
            mock_settings.GITHUB_TOKEN = ""
            mock_settings.GITHUB_MODELS_TOKEN = ""

            resp = client.post("/analyze/", json={"repo_url": _REPO_URL})

        assert resp.status_code == 200
        assert resp.json()["used_fallback"] is True

    def test_invalid_url_returns_422(self, client):
        resp = client.post("/analyze/", json={"repo_url": "https://gitlab.com/foo/bar"})
        assert resp.status_code == 422

    def test_repo_not_found_returns_404(self, client):
        from core.github_client import RepoNotFoundError

        mock_gh = AsyncMock()
        mock_gh.get_tree.side_effect = RepoNotFoundError("testowner", "testrepo")
        mock_gh.__aenter__ = AsyncMock(return_value=mock_gh)
        mock_gh.__aexit__ = AsyncMock(return_value=None)

        with (
            patch("routers.analyze.GitHubClient", return_value=mock_gh),
            patch("routers.analyze.settings") as mock_settings,
        ):
            mock_settings.GITHUB_TOKEN = ""
            mock_settings.GITHUB_MODELS_TOKEN = ""

            resp = client.post("/analyze/", json={"repo_url": _REPO_URL})

        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_rate_limit_returns_429(self, client):
        from core.github_client import RateLimitError

        mock_gh = AsyncMock()
        mock_gh.get_tree.side_effect = RateLimitError(403)
        mock_gh.__aenter__ = AsyncMock(return_value=mock_gh)
        mock_gh.__aexit__ = AsyncMock(return_value=None)

        with (
            patch("routers.analyze.GitHubClient", return_value=mock_gh),
            patch("routers.analyze.settings") as mock_settings,
        ):
            mock_settings.GITHUB_TOKEN = ""
            mock_settings.GITHUB_MODELS_TOKEN = ""

            resp = client.post("/analyze/", json={"repo_url": _REPO_URL})

        assert resp.status_code == 429

    def test_json_decode_error_falls_back(self, client):
        """If LLM returns non-JSON, fallback silently kicks in."""
        with (
            self._patch_github(),
            patch("routers.analyze.call_llm", new=AsyncMock(return_value="not json")),
            patch("routers.analyze.settings") as mock_settings,
        ):
            mock_settings.GITHUB_TOKEN = ""
            mock_settings.GITHUB_MODELS_TOKEN = "tok"

            resp = client.post("/analyze/", json={"repo_url": _REPO_URL})

        assert resp.status_code == 200
        assert resp.json()["used_fallback"] is True

    def test_default_branch_is_head(self, client):
        with (
            self._patch_github(),
            patch("routers.analyze.settings") as mock_settings,
        ):
            mock_settings.GITHUB_TOKEN = ""
            mock_settings.GITHUB_MODELS_TOKEN = ""

            resp = client.post("/analyze/", json={"repo_url": _REPO_URL})

        assert resp.json()["branch"] == "HEAD"


# =========================================================================== #
# /diagram  tests
# =========================================================================== #


class TestDiagramRouter:

    def test_happy_path_with_llm(self, client):
        with (
            patch("routers.diagram.call_llm", new=AsyncMock(return_value=_LLM_DIAGRAM)),
            patch("routers.diagram.settings") as mock_settings,
        ):
            mock_settings.GITHUB_MODELS_TOKEN = "tok"

            resp = client.post(
                "/diagram/",
                json={"repo_url": _REPO_URL, "stack": _STACK_DICT, "modules": ["src", "tests"]},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "graph TD" in data["mermaid_source"]
        assert data["used_fallback"] is False

        node_map = {n["id"]: n["label"] for n in data["nodes"]}
        assert "A" in node_map, f"Expected node 'A', got ids: {list(node_map)}"
        assert node_map["A"] == "Client"   # inline label extracted from A[Client]
        assert node_map["B"] == "FastAPI"

        edge_pairs = {(e["from"], e["to"]) for e in data["edges"]}
        assert ("A", "B") in edge_pairs
        assert ("B", "C") in edge_pairs

    def test_llm_failure_uses_fallback(self, client):
        from ai.github_models import LLMUnavailableError

        with (
            patch("routers.diagram.call_llm", side_effect=LLMUnavailableError("err")),
            patch("routers.diagram.settings") as mock_settings,
            patch("routers.diagram.fallback_diagram", return_value={
                "mermaid_source": "graph TD\n  A --> B",
                "nodes": [{"id": "A", "label": "A"}, {"id": "B", "label": "B"}],
                "edges": [{"from": "A", "to": "B", "label": ""}],
            }),
        ):
            mock_settings.GITHUB_MODELS_TOKEN = "tok"

            resp = client.post(
                "/diagram/",
                json={"repo_url": _REPO_URL, "stack": _STACK_DICT, "modules": []},
            )

        assert resp.status_code == 200
        assert resp.json()["used_fallback"] is True

    def test_no_token_uses_fallback(self, client):
        with (
            patch("routers.diagram.settings") as mock_settings,
            patch("routers.diagram.fallback_diagram", return_value={
                "mermaid_source": "graph TD\n  A --> B",
                "nodes": [],
                "edges": [],
            }),
        ):
            mock_settings.GITHUB_MODELS_TOKEN = ""

            resp = client.post(
                "/diagram/",
                json={"repo_url": _REPO_URL, "stack": {}, "modules": []},
            )

        assert resp.status_code == 200
        assert resp.json()["used_fallback"] is True

    def test_modules_as_objects_coerced(self, client):
        """
        /diagram must accept the ModuleInfo object array returned by /analyze,
        not just plain strings.  Previously caused HTTP 422.
        """
        module_objects = [
            {"name": "fastapi", "path": "fastapi", "description": "Core module."},
            {"name": "tests",   "path": "tests",   "description": "Test suite."},
        ]
        with (
            patch("routers.diagram.settings") as mock_settings,
            patch("routers.diagram.fallback_diagram", return_value={
                "mermaid_source": "graph TD\n  A --> B",
                "nodes": [],
                "edges": [],
            }),
        ):
            mock_settings.GITHUB_MODELS_TOKEN = ""
            resp = client.post(
                "/diagram/",
                json={"repo_url": _REPO_URL, "stack": {}, "modules": module_objects},
            )
        # Must be 200, not 422
        assert resp.status_code == 200

    def test_stack_dict_converted_to_stack_result_for_fallback(self, client):
        """
        When no LLM token is set, fallback_diagram receives a StackResult
        (not a raw dict), so body.stack.frameworks resolves correctly and
        the framework label is never the default 'App' when one was provided.
        """
        with (
            patch("routers.diagram.settings") as mock_settings,
            patch("routers.diagram.fallback_diagram") as mock_fallback,
        ):
            mock_settings.GITHUB_MODELS_TOKEN = ""
            mock_fallback.return_value = {
                "mermaid_source": "graph TD\n  A --> B",
                "nodes": [{"id": "A", "label": "Spring Boot"}, {"id": "B", "label": "backend"}],
                "edges": [{"from": "A", "to": "B", "label": ""}],
            }
            resp = client.post(
                "/diagram/",
                json={
                    "repo_url": _REPO_URL,
                    "stack": {"frameworks": ["Spring Boot"], "databases": ["PostgreSQL"]},
                    "modules": ["backend"],
                },
            )

        assert resp.status_code == 200
        # Verify fallback_diagram was called with a StackResult-like object,
        # not a plain dict — confirmed by checking it has .frameworks attribute
        call_kwargs = mock_fallback.call_args
        stack_arg = call_kwargs.kwargs.get("stack") or call_kwargs.args[0]
        assert hasattr(stack_arg, "frameworks"), (
            "fallback_diagram must receive a StackResult with .frameworks, not a dict"
        )
        assert stack_arg.frameworks == ["Spring Boot"]
        assert stack_arg.databases == ["PostgreSQL"]

    def test_invalid_url_returns_422(self, client):
        resp = client.post("/diagram/", json={"repo_url": "not-a-url"})
        assert resp.status_code == 422

    def test_fenced_mermaid_is_stripped(self, client):
        fenced = "```mermaid\ngraph TD\n    A --> B\n```"
        with (
            patch("routers.diagram.call_llm", new=AsyncMock(return_value=fenced)),
            patch("routers.diagram.settings") as mock_settings,
        ):
            mock_settings.GITHUB_MODELS_TOKEN = "tok"

            resp = client.post(
                "/diagram/",
                json={"repo_url": _REPO_URL, "stack": {}, "modules": []},
            )

        data = resp.json()
        assert not data["mermaid_source"].startswith("```")


# =========================================================================== #
# /suggestions  tests
# =========================================================================== #


class TestSuggestionsRouter:

    def test_happy_path_with_llm(self, client):
        with (
            patch("routers.suggestions.call_llm", new=AsyncMock(return_value=_LLM_SUGGESTIONS)),
            patch("routers.suggestions.settings") as mock_settings,
        ):
            mock_settings.GITHUB_MODELS_TOKEN = "tok"

            resp = client.post(
                "/suggestions/",
                json={"repo_url": _REPO_URL, "stack": _STACK_DICT, "modules": ["src"]},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["used_fallback"] is False
        assert len(data["suggestions"]) >= 1
        first = data["suggestions"][0]
        assert "category" in first
        assert "severity" in first
        assert "title" in first
        assert "detail" in first

    def test_llm_failure_uses_fallback(self, client):
        from ai.github_models import LLMUnavailableError

        with (
            patch("routers.suggestions.call_llm", side_effect=LLMUnavailableError("down")),
            patch("routers.suggestions.settings") as mock_settings,
        ):
            mock_settings.GITHUB_MODELS_TOKEN = "tok"

            resp = client.post(
                "/suggestions/",
                json={"repo_url": _REPO_URL, "stack": _STACK_DICT, "modules": []},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["used_fallback"] is True
        # fallback_suggestions always returns ≥ 3
        assert len(data["suggestions"]) >= 3

    def test_json_parse_failure_uses_fallback(self, client):
        with (
            patch("routers.suggestions.call_llm", new=AsyncMock(return_value="not json")),
            patch("routers.suggestions.settings") as mock_settings,
        ):
            mock_settings.GITHUB_MODELS_TOKEN = "tok"

            resp = client.post(
                "/suggestions/",
                json={"repo_url": _REPO_URL, "stack": {}, "modules": []},
            )

        assert resp.status_code == 200
        assert resp.json()["used_fallback"] is True

    def test_llm_returns_non_array_uses_fallback(self, client):
        with (
            patch(
                "routers.suggestions.call_llm",
                new=AsyncMock(return_value=json.dumps({"oops": "dict not list"})),
            ),
            patch("routers.suggestions.settings") as mock_settings,
        ):
            mock_settings.GITHUB_MODELS_TOKEN = "tok"

            resp = client.post(
                "/suggestions/",
                json={"repo_url": _REPO_URL, "stack": {}, "modules": []},
            )

        assert resp.status_code == 200
        assert resp.json()["used_fallback"] is True

    def test_no_token_uses_fallback(self, client):
        with patch("routers.suggestions.settings") as mock_settings:
            mock_settings.GITHUB_MODELS_TOKEN = ""

            resp = client.post(
                "/suggestions/",
                json={"repo_url": _REPO_URL, "stack": _STACK_DICT, "modules": []},
            )

        assert resp.status_code == 200
        assert resp.json()["used_fallback"] is True

    def test_modules_as_objects_coerced(self, client):
        """Mirrors the /diagram fix — modules array from /analyze must be accepted."""
        module_objects = [
            {"name": "src", "path": "src", "description": "Source."},
        ]
        with patch("routers.suggestions.settings") as mock_settings:
            mock_settings.GITHUB_MODELS_TOKEN = ""
            resp = client.post(
                "/suggestions/",
                json={"repo_url": _REPO_URL, "stack": _STACK_DICT, "modules": module_objects},
            )
        assert resp.status_code == 200

    def test_invalid_url_returns_422(self, client):
        resp = client.post("/suggestions/", json={"repo_url": "ftp://notgithub.com/foo"})
        assert resp.status_code == 422


# =========================================================================== #
# diagram_parser  unit tests
# =========================================================================== #


class TestDiagramParser:
    """Tests for analyzers/diagram_parser.py — no FastAPI involved."""

    def _parse(self, source: str):
        from analyzers.diagram_parser import parse_mermaid
        return parse_mermaid(source)

    def test_simple_arrows(self):
        source = "graph TD\n    A --> B\n    B --> C"
        nodes, edges = self._parse(source)
        node_ids = {n["id"] for n in nodes}
        assert {"A", "B", "C"} == node_ids
        assert {"from": "A", "to": "B", "label": ""} in edges
        assert {"from": "B", "to": "C", "label": ""} in edges

    def test_labelled_edge(self):
        source = "graph TD\n    A -->|sends request| B"
        _, edges = self._parse(source)
        assert edges[0]["label"] == "sends request"

    def test_inline_text_edge(self):
        source = "graph TD\n    A -- calls --> B"
        _, edges = self._parse(source)
        assert edges[0]["from"] == "A"
        assert edges[0]["to"] == "B"

    def test_node_labels_parsed(self):
        source = "graph TD\n    A[My Label]\n    B(Rounded)\n    A --> B"
        nodes, _ = self._parse(source)
        lbl_map = {n["id"]: n["label"] for n in nodes}
        assert lbl_map["A"] == "My Label"
        assert lbl_map["B"] == "Rounded"

    def test_comments_skipped(self):
        source = "graph TD\n    %% this is a comment\n    A --> B"
        nodes, edges = self._parse(source)
        assert len(edges) == 1

    def test_duplicate_edges_deduplicated(self):
        source = "graph TD\n    A --> B\n    A --> B"
        _, edges = self._parse(source)
        assert len(edges) == 1

    def test_empty_source_returns_empty(self):
        nodes, edges = self._parse("")
        assert nodes == []
        assert edges == []

    def test_fenced_source_still_parsed_after_stripping(self):
        """Parser itself doesn't strip fences; the router does. Verify parser is tolerant."""
        # Without stripping, the ``` line is an unrecognised line → skipped silently
        source = "```mermaid\ngraph TD\n    A --> B\n```"
        _, edges = self._parse(source)
        # Either 1 edge (if parser skips unknown lines) or 0 — must not crash
        assert isinstance(edges, list)

    def test_complex_diagram(self):
        source = """graph TD
    Client[Browser] --> API[FastAPI]
    API -->|query| DB[(PostgreSQL)]
    API --> Cache[Redis]
    Cache --> API
"""
        nodes, edges = self._parse(source)
        node_ids = {n["id"] for n in nodes}
        node_labels = {n["id"]: n["label"] for n in nodes}

        # All four IDs must be present
        assert "Client" in node_ids, f"Got ids: {node_ids}"
        assert "API" in node_ids
        assert "DB" in node_ids
        assert "Cache" in node_ids

        # Inline labels must be extracted correctly
        assert node_labels["Client"] == "Browser"
        assert node_labels["API"] == "FastAPI"
        assert node_labels["Cache"] == "Redis"

        # All four edges present
        edge_pairs = {(e["from"], e["to"]) for e in edges}
        assert ("Client", "API") in edge_pairs
        assert ("API", "DB") in edge_pairs
        assert ("API", "Cache") in edge_pairs
        assert ("Cache", "API") in edge_pairs

        # Labelled edge preserved
        labelled = [e for e in edges if e["from"] == "API" and e["to"] == "DB"]
        assert labelled and labelled[0]["label"] == "query"


# =========================================================================== #
# fallback.py  unit tests
# =========================================================================== #


class _FakeStack:
    """Minimal stand-in for StackResult."""
    def __init__(self, **kwargs):
        self.languages = kwargs.get("languages", [])
        self.frameworks = kwargs.get("frameworks", [])
        self.databases = kwargs.get("databases", [])
        self.infra = kwargs.get("infra", [])
        self.test_frameworks = kwargs.get("test_frameworks", [])
        self.package_manager = kwargs.get("package_manager", None)


class TestFallbackSummary:

    def _call(self, readme="", dirs=None, files=None, stack=None):
        from ai.fallback import fallback_summary
        return fallback_summary(
            repo_name="owner/repo",
            stack=stack or _FakeStack(),
            readme=readme,
            top_level_dirs=dirs or [],
            file_list=files or [],
        )

    def test_plain_readme_used_as_summary(self):
        result = self._call(readme="A simple REST API built with FastAPI and PostgreSQL.")
        assert "simple REST API" in result["summary"]
        assert "<" not in result["summary"]
        assert "![" not in result["summary"]

    def test_badge_heavy_readme_stripped(self):
        readme = (
            "[![Build](https://ci.example.com/badge.svg)](https://ci.example.com)\n\n"
            "<p align='center'><img src='logo.png'></p>\n\n"
            "FastAPI is a modern web framework for building APIs with Python."
        )
        result = self._call(readme=readme)
        assert "FastAPI is a modern web framework" in result["summary"]
        assert "[![" not in result["summary"]
        assert "<p" not in result["summary"]

    def test_html_anchor_stripped(self):
        readme = (
            "<p align='center'>"
            "<a href='https://fastapi.tiangolo.com'>"
            "<img src='logo.png'></a></p>\n\n"
            "FastAPI framework, high performance, easy to learn."
        )
        result = self._call(readme=readme)
        assert "FastAPI framework" in result["summary"]
        assert "<" not in result["summary"]

    def test_tech_sentence_appended(self):
        result = self._call(
            readme="A web service.",
            stack=_FakeStack(languages=["Python"], frameworks=["FastAPI"]),
        )
        assert "FastAPI" in result["summary"]

    def test_modules_use_known_descriptions(self):
        result = self._call(dirs=["src", "tests", "docs", "unknowndir"])
        desc_map = {m["name"]: m["description"] for m in result["modules"]}
        assert desc_map["src"] == "Primary source code directory."
        assert desc_map["tests"] == "Automated test suite."
        assert desc_map["docs"] == "Project documentation."
        assert "unknowndir" in desc_map["unknowndir"]

    def test_entry_points_prefer_non_test_paths(self):
        files = [
            "tests/main.py",
            "tests/test_validate/app.py",
            "fastapi/__init__.py",
            "fastapi/middleware/wsgi.py",
        ]
        result = self._call(files=files)
        eps = result["entry_points"]
        # Non-test library entry point must be present
        assert "fastapi/__init__.py" in eps, f"Expected fastapi/__init__.py in {eps}"
        # test-dir main.py must be excluded when non-test candidates exist
        assert "tests/main.py" not in eps, f"tests/main.py must be excluded: {eps}"
        # __init__.py must rank above wsgi.py when both present
        if "fastapi/middleware/wsgi.py" in eps:
            assert eps.index("fastapi/__init__.py") < eps.index("fastapi/middleware/wsgi.py")

    def test_entry_points_fallback_to_test_dirs_when_no_other_match(self):
        # When the only entry points are inside test dirs, they should still be returned
        files = ["tests/main.py", "tests/conftest.py", "README.md"]
        result = self._call(files=files)
        eps = result["entry_points"]
        assert "tests/main.py" in eps, f"Expected tests/main.py as last resort: {eps}"

    def test_entry_points_java_application_file(self):
        # Application.java deeply nested in a Java project should be found
        files = [
            "backend/src/main/java/com/example/Application.java",
            "backend/pom.xml",
            "README.md",
        ]
        result = self._call(files=files)
        eps = result["entry_points"]
        assert "backend/src/main/java/com/example/Application.java" in eps, f"Got: {eps}"

    def test_no_readme_falls_back_to_tech_sentence(self):
        result = self._call(stack=_FakeStack(languages=["Go"], frameworks=["Gin"]))
        assert "Go" in result["summary"] or "Gin" in result["summary"]

    def test_empty_inputs_return_valid_dict(self):
        result = self._call()
        assert isinstance(result["summary"], str)
        assert isinstance(result["modules"], list)
        assert isinstance(result["entry_points"], list)
        assert isinstance(result["request_flow"], str)


class TestFallbackDiagram:

    def _call(self, stack=None, modules=None):
        from ai.fallback import fallback_diagram
        return fallback_diagram(stack=stack or _FakeStack(), modules=modules or [])

    def test_returns_canonical_node_shape(self):
        result = self._call(stack=_FakeStack(frameworks=["FastAPI"]), modules=["src"])
        for node in result["nodes"]:
            assert "id" in node
            assert "label" in node
            assert "data" not in node,     "React Flow 'data' must not be present"
            assert "position" not in node, "React Flow 'position' must not be present"
            assert "type" not in node,     "React Flow 'type' must not be present"

    def test_returns_canonical_edge_shape(self):
        result = self._call(stack=_FakeStack(frameworks=["FastAPI"]), modules=["api"])
        for edge in result["edges"]:
            assert "from" in edge
            assert "to" in edge
            assert "label" in edge
            assert "source" not in edge, "React Flow 'source' must not be present"
            assert "target" not in edge, "React Flow 'target' must not be present"
            assert "id" not in edge,     "React Flow edge 'id' must not be present"

    def test_client_and_framework_nodes_present(self):
        result = self._call(stack=_FakeStack(frameworks=["Django"]))
        node_ids = {n["id"] for n in result["nodes"]}
        assert "Client" in node_ids
        assert "framework" in node_ids

    def test_database_node_added_when_detected(self):
        result = self._call(
            stack=_FakeStack(frameworks=["FastAPI"], databases=["PostgreSQL"]),
            modules=["api"],
        )
        node_ids = {n["id"] for n in result["nodes"]}
        assert "database" in node_ids
        db_node = next(n for n in result["nodes"] if n["id"] == "database")
        assert db_node["label"] == "PostgreSQL"

    def test_mermaid_starts_with_graph_td(self):
        assert self._call()["mermaid_source"].startswith("graph TD")

    def test_all_edge_ids_reference_real_nodes(self):
        result = self._call(
            stack=_FakeStack(frameworks=["Spring Boot"], databases=["MongoDB"]),
            modules=["backend"],
        )
        node_ids = {n["id"] for n in result["nodes"]}
        for edge in result["edges"]:
            assert edge["from"] in node_ids
            assert edge["to"] in node_ids

    def test_empty_modules_uses_services_placeholder(self):
        result = self._call(stack=_FakeStack(frameworks=["Express"]), modules=[])
        labels = {n["label"] for n in result["nodes"]}
        assert "Services" in labels


class TestFallbackSuggestions:

    def _call(self, **kwargs):
        from ai.fallback import fallback_suggestions
        return fallback_suggestions(_FakeStack(**kwargs))

    def test_fastapi_rate_limit_suggestion(self):
        titles = [s["title"] for s in self._call(frameworks=["FastAPI"])]
        assert any("rate limit" in t.lower() for t in titles)

    def test_always_at_least_3(self):
        assert len(self._call()) >= 3
        assert len(self._call(frameworks=["FastAPI"])) >= 3
        assert len(self._call(databases=["PostgreSQL", "MongoDB"])) >= 3

    def test_postgres_suggestion_mentions_hikaricp_and_pgbouncer(self):
        results = self._call(databases=["PostgreSQL"])
        pg = next((s for s in results if "pool" in s["title"].lower()), None)
        assert pg is not None, "Expected a connection pooling suggestion"
        assert "HikariCP" in pg["detail"]
        assert "pgbouncer" in pg["detail"]

    def test_mongodb_suggestion_covers_multiple_languages(self):
        results = self._call(databases=["MongoDB"])
        mg = next(
            (s for s in results if "mongo" in s["title"].lower() or "schema" in s["title"].lower()),
            None,
        )
        assert mg is not None
        assert "Mongoose" in mg["detail"]
        assert "Spring Data" in mg["detail"]

    def test_no_ci_fires_without_github_actions(self):
        titles = [s["title"] for s in self._call(infra=[])]
        assert any("CI" in t or "pipeline" in t.lower() for t in titles)

    def test_no_ci_suppressed_with_github_actions(self):
        titles = [s["title"] for s in self._call(infra=["GitHub Actions"])]
        assert "Add a CI pipeline" not in titles

    def test_sorted_by_severity(self):
        results = self._call(frameworks=["FastAPI"], databases=["PostgreSQL"], infra=["Docker"])
        order = {"high": 0, "medium": 1, "low": 2}
        severities = [s["severity"] for s in results]
        assert severities == sorted(severities, key=lambda s: order.get(s, 9))


class TestDiagramRouterFallbackStackCoercion:
    """
    Regression tests for the bug where fallback_diagram received body.stack
    as a plain dict instead of a StackResult, causing getattr() to return []
    for all fields and the framework label to show "App" instead of the real name.
    """

    def test_framework_label_in_fallback_diagram(self, client):
        # body.stack is a plain dict (as sent by the frontend)
        stack_dict = {
            "languages": ["Java"],
            "frameworks": ["Spring Boot"],
            "databases": ["PostgreSQL"],
            "infra": ["Docker Compose"],
            "test_frameworks": ["JUnit"],
            "package_manager": None,
        }
        module_objs = [{"name": "backend", "path": "backend", "description": "Backend."}]

        with patch("routers.diagram.settings") as mock_settings:
            mock_settings.GITHUB_MODELS_TOKEN = ""  # force fallback path

            resp = client.post(
                "/diagram/",
                json={"repo_url": _REPO_URL, "stack": stack_dict, "modules": module_objs},
            )

        assert resp.status_code == 200
        data = resp.json()
        node_labels = {n["label"] for n in data["nodes"]}
        # Framework node must show the real name, not the "App" fallback
        assert "Spring Boot" in node_labels, (
            f"Expected 'Spring Boot' in node labels, got: {node_labels}. "
            "This means body.stack dict was not coerced to StackResult before passing to fallback_diagram."
        )
        # Database node must also be populated
        assert "PostgreSQL" in node_labels, f"Expected 'PostgreSQL' in node labels, got: {node_labels}"

    def test_empty_stack_dict_does_not_crash(self, client):
        with patch("routers.diagram.settings") as mock_settings:
            mock_settings.GITHUB_MODELS_TOKEN = ""

            resp = client.post(
                "/diagram/",
                json={"repo_url": _REPO_URL, "stack": {}, "modules": []},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert len(data["nodes"]) >= 2   # Client + at least one other