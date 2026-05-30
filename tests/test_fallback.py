"""
tests/test_fallback.py
----------------------
Unit tests for ai/fallback.py.

These tests validate the *canonical* output shapes agreed in the API contract:

  Nodes : {"id": str, "label": str}
  Edges : {"from": str, "to": str, "label": str}

The old React-Flow shape (data/position/source/target) was removed from the
backend in a prior refactor; the frontend is responsible for any layout
enrichment needed by its renderer.

Run:
    pytest tests/test_fallback.py -v
"""

from __future__ import annotations

import pytest


# --------------------------------------------------------------------------- #
# Shared helpers
# --------------------------------------------------------------------------- #


class _FakeStack:
    """Minimal stand-in for StackResult — avoids importing the real class."""

    def __init__(self, **kwargs):
        self.languages = kwargs.get("languages", [])
        self.frameworks = kwargs.get("frameworks", [])
        self.databases = kwargs.get("databases", [])
        self.infra = kwargs.get("infra", [])
        self.test_frameworks = kwargs.get("test_frameworks", [])
        self.package_manager = kwargs.get("package_manager", None)


# --------------------------------------------------------------------------- #
# _first_paragraph / _strip_markdown_to_plain
# --------------------------------------------------------------------------- #


class TestFirstParagraph:

    def _fp(self, text: str) -> str:
        from ai.fallback import _first_paragraph
        return _first_paragraph(text)

    def test_returns_first_real_paragraph(self):
        # "# Title" is its own block; after stripping it becomes "Title" (<40 chars
        # min), so the paragraph loop advances to "This is the intro." — the first
        # real prose block.  "Second paragraph." must never appear before it.
        text = "# Title\n\nThis is the intro.\n\nSecond paragraph."
        result = self._fp(text)
        assert "This is the intro." in result, repr(result)
        assert "Second paragraph." not in result, repr(result)
        assert "#" not in result, repr(result)

    def test_skips_headings(self):
        text = "# Heading\n## Sub\n\nActual content here."
        result = self._fp(text)
        assert "#" not in result, repr(result)
        assert "Actual content here." in result

    def test_heading_prefix_stripped_not_line_skipped(self):
        """
        '# Title Some prose' should yield 'Title Some prose', not be skipped
        entirely (old bug: the whole line was discarded).
        """
        result = self._fp("# Title Some prose\n\nSecond paragraph.")
        assert "#" not in result
        assert "Title Some prose" in result

    def test_badge_lines_removed(self):
        text = (
            "[![Build](https://ci.example.com/badge.svg)](https://ci.example.com)\n\n"
            "Real description here."
        )
        result = self._fp(text)
        assert "Real description here." in result
        assert "[![" not in result

    def test_html_tags_removed(self):
        text = "<p align='center'><img src='logo.png'></p>\n\nReal description."
        result = self._fp(text)
        assert "<" not in result
        assert "Real description." in result

    def test_inline_links_converted(self):
        text = "See [the docs](https://example.com) for details."
        result = self._fp(text)
        assert "the docs" in result
        assert "https://example.com" not in result
        assert "[" not in result

    def test_horizontal_rules_skipped(self):
        # _strip_markdown_to_plain removes standalone "---" / "===" lines before
        # paragraph splitting; the result must be plain prose only.
        text = "---\n\nContent here."
        result = self._fp(text)
        assert "---" not in result, repr(result)
        assert "Content here." in result, repr(result)

    def test_empty_string_returns_empty(self):
        assert self._fp("") == ""

    def test_max_chars_respected(self):
        from ai.fallback import _first_paragraph
        long_text = "A" * 1000
        assert len(_first_paragraph(long_text, max_chars=100)) <= 100

    def test_plain_prose_unchanged(self):
        text = "A simple REST API built with FastAPI."
        result = self._fp(text)
        assert "A simple REST API built with FastAPI." in result


# --------------------------------------------------------------------------- #
# fallback_summary
# --------------------------------------------------------------------------- #


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

    def test_returns_required_keys(self):
        result = self._call()
        for key in ("summary", "modules", "entry_points", "request_flow"):
            assert key in result, f"Missing key: {key}"

    def test_summary_is_clean_prose(self):
        readme = (
            "[![CI](https://img.shields.io/badge/ci-passing-green)](https://ci.test)\n\n"
            "<p align='center'><img src='logo.png'></p>\n\n"
            "FastAPI is a high-performance web framework for building APIs."
        )
        result = self._call(readme=readme)
        s = result["summary"]
        assert "#" not in s
        assert "<" not in s
        assert "[![" not in s
        assert "FastAPI is a high-performance" in s

    def test_tech_sentence_appended_when_stack_known(self):
        result = self._call(
            readme="Short description.",
            stack=_FakeStack(languages=["Python"], frameworks=["FastAPI"]),
        )
        assert "FastAPI" in result["summary"]

    def test_modules_have_required_fields(self):
        result = self._call(dirs=["src", "tests", "docs"])
        for mod in result["modules"]:
            assert "name" in mod
            assert "path" in mod
            assert "description" in mod
            assert isinstance(mod["description"], str)
            assert len(mod["description"]) > 0

    def test_known_dirs_get_meaningful_descriptions(self):
        result = self._call(dirs=["src", "tests", "docs", "api"])
        desc_map = {m["name"]: m["description"] for m in result["modules"]}
        assert desc_map["src"] == "Primary source code directory."
        assert desc_map["tests"] == "Automated test suite."
        assert desc_map["docs"] == "Project documentation."
        assert desc_map["api"] == "API route definitions and controllers."

    def test_unknown_dir_gets_fallback_description(self):
        result = self._call(dirs=["weirdmodulename"])
        desc = result["modules"][0]["description"]
        assert "weirdmodulename" in desc

    def test_entry_points_prefer_non_test_paths(self):
        files = [
            "tests/main.py",
            "tests/test_validate/app.py",
            "fastapi/__init__.py",
            "fastapi/middleware/wsgi.py",
        ]
        result = self._call(files=files)
        eps = result["entry_points"]
        assert "fastapi/__init__.py" in eps, f"Expected fastapi/__init__.py in {eps}"
        assert "tests/main.py" not in eps, f"tests/main.py must be excluded: {eps}"

    def test_entry_points_fallback_to_test_dirs_when_nothing_else(self):
        files = ["tests/main.py", "tests/conftest.py", "README.md"]
        result = self._call(files=files)
        assert "tests/main.py" in result["entry_points"]

    def test_entry_points_java_application_file(self):
        files = [
            "backend/src/main/java/com/example/Application.java",
            "backend/pom.xml",
        ]
        result = self._call(files=files)
        assert "backend/src/main/java/com/example/Application.java" in result["entry_points"]

    def test_request_flow_is_string(self):
        result = self._call(stack=_FakeStack(frameworks=["FastAPI"]))
        assert isinstance(result["request_flow"], str)
        assert len(result["request_flow"]) > 0

    def test_empty_inputs_do_not_raise(self):
        result = self._call()
        assert isinstance(result["summary"], str)
        assert isinstance(result["modules"], list)
        assert isinstance(result["entry_points"], list)


# --------------------------------------------------------------------------- #
# fallback_diagram — canonical node/edge shape
# --------------------------------------------------------------------------- #


class TestFallbackDiagram:

    def _call(self, stack=None, modules=None):
        from ai.fallback import fallback_diagram
        return fallback_diagram(
            stack=stack or _FakeStack(),
            modules=modules or [],
        )

    # ── Node shape ─────────────────────────────────────────────────────────

    def test_nodes_have_required_fields(self):
        """Canonical shape: {"id": str, "label": str} — no React Flow keys."""
        result = self._call(stack=_FakeStack(frameworks=["FastAPI"]), modules=["src"])
        assert len(result["nodes"]) > 0
        for node in result["nodes"]:
            assert "id" in node,    f"Missing 'id' in node: {node}"
            assert "label" in node, f"Missing 'label' in node: {node}"
            # React Flow keys must NOT be present
            assert "data" not in node,     f"Unexpected 'data' key: {node}"
            assert "position" not in node, f"Unexpected 'position' key: {node}"
            assert "type" not in node,     f"Unexpected 'type' key: {node}"

    def test_client_node_is_first(self):
        result = self._call(stack=_FakeStack(frameworks=["FastAPI"]))
        first = result["nodes"][0]
        assert first["id"] == "Client"
        assert first["label"] == "Client"

    def test_framework_node_uses_detected_framework(self):
        result = self._call(stack=_FakeStack(frameworks=["Django"]))
        labels = {n["label"] for n in result["nodes"]}
        assert "Django" in labels

    def test_no_framework_uses_app_fallback(self):
        result = self._call(stack=_FakeStack(frameworks=[]))
        labels = {n["label"] for n in result["nodes"]}
        assert "App" in labels

    def test_database_node_present_when_detected(self):
        result = self._call(
            stack=_FakeStack(frameworks=["FastAPI"], databases=["PostgreSQL"]),
            modules=["api"],
        )
        node_ids = {n["id"] for n in result["nodes"]}
        assert "database" in node_ids
        db = next(n for n in result["nodes"] if n["id"] == "database")
        assert db["label"] == "PostgreSQL"

    def test_skips_node_modules_dir(self):
        result = self._call(
            stack=_FakeStack(frameworks=["Express"]),
            modules=["node_modules", "src"],
        )
        labels = {n["label"] for n in result["nodes"]}
        assert "node_modules" not in labels

    def test_empty_modules_uses_default_service_node(self):
        result = self._call(stack=_FakeStack(frameworks=["Express"]), modules=[])
        labels = {n["label"] for n in result["nodes"]}
        assert "Services" in labels

    # ── Edge shape ─────────────────────────────────────────────────────────

    def test_edges_have_required_fields(self):
        """Canonical shape: {"from": str, "to": str, "label": str} — no React Flow keys."""
        result = self._call(stack=_FakeStack(frameworks=["FastAPI"]), modules=["api"])
        assert len(result["edges"]) > 0
        for edge in result["edges"]:
            assert "from" in edge,  f"Missing 'from' in edge: {edge}"
            assert "to" in edge,    f"Missing 'to' in edge: {edge}"
            assert "label" in edge, f"Missing 'label' in edge: {edge}"
            # React Flow keys must NOT be present
            assert "id" not in edge,     f"Unexpected 'id' key: {edge}"
            assert "source" not in edge, f"Unexpected 'source' key: {edge}"
            assert "target" not in edge, f"Unexpected 'target' key: {edge}"

    def test_edges_connect_nodes(self):
        result = self._call(
            stack=_FakeStack(frameworks=["FastAPI"], databases=["PostgreSQL"]),
            modules=["api"],
        )
        node_ids = {n["id"] for n in result["nodes"]}
        for edge in result["edges"]:
            assert edge["from"] in node_ids, f"from={edge['from']} not in nodes"
            assert edge["to"] in node_ids,   f"to={edge['to']} not in nodes"

    def test_client_to_framework_edge_has_http_label(self):
        result = self._call(stack=_FakeStack(frameworks=["FastAPI"]))
        client_fw_edges = [
            e for e in result["edges"]
            if e["from"] == "Client" and e["to"] == "framework"
        ]
        assert len(client_fw_edges) == 1
        assert client_fw_edges[0]["label"] == "HTTP"

    def test_database_edge_has_query_label(self):
        result = self._call(
            stack=_FakeStack(frameworks=["Spring Boot"], databases=["MongoDB"]),
            modules=["backend"],
        )
        db_edges = [e for e in result["edges"] if e["to"] == "database"]
        assert len(db_edges) == 1
        assert db_edges[0]["label"] == "query"

    # ── Mermaid source ─────────────────────────────────────────────────────

    def test_mermaid_source_starts_with_graph_td(self):
        assert self._call()["mermaid_source"].startswith("graph TD")

    def test_mermaid_source_no_fences(self):
        source = self._call()["mermaid_source"]
        assert "```" not in source

    def test_mermaid_nodes_match_returned_nodes(self):
        """Every node id returned must appear somewhere in the mermaid source."""
        result = self._call(
            stack=_FakeStack(frameworks=["FastAPI"], databases=["PostgreSQL"]),
            modules=["api"],
        )
        for node in result["nodes"]:
            assert node["id"] in result["mermaid_source"], (
                f"Node id {node['id']!r} not found in mermaid_source"
            )


# --------------------------------------------------------------------------- #
# fallback_suggestions
# --------------------------------------------------------------------------- #


class TestFallbackSuggestions:

    def _call(self, **kwargs):
        from ai.fallback import fallback_suggestions
        return fallback_suggestions(_FakeStack(**kwargs))

    def test_returns_list(self):
        assert isinstance(self._call(), list)

    def test_always_at_least_3(self):
        assert len(self._call()) >= 3
        assert len(self._call(frameworks=["FastAPI"])) >= 3
        assert len(self._call(databases=["PostgreSQL", "MongoDB"])) >= 3

    def test_each_suggestion_has_required_fields(self):
        results = self._call(frameworks=["FastAPI"], databases=["PostgreSQL"])
        for s in results:
            assert "category" in s
            assert "severity" in s
            assert "title" in s
            assert "detail" in s
            assert s["category"] in {"security", "performance", "scalability", "quality"}
            assert s["severity"] in {"high", "medium", "low"}

    def test_sorted_high_before_low(self):
        results = self._call(frameworks=["FastAPI"], databases=["PostgreSQL"])
        order = {"high": 0, "medium": 1, "low": 2}
        severities = [s["severity"] for s in results]
        assert severities == sorted(severities, key=lambda x: order[x])

    def test_fastapi_rate_limit_suggestion(self):
        titles = [s["title"] for s in self._call(frameworks=["FastAPI"])]
        assert any("rate limit" in t.lower() for t in titles)

    def test_postgres_suggestion_stack_agnostic(self):
        result = self._call(databases=["PostgreSQL"])
        pg = next((s for s in result if "pool" in s["title"].lower()), None)
        assert pg is not None
        assert "HikariCP" in pg["detail"]
        assert "pgbouncer" in pg["detail"]

    def test_mongodb_suggestion_covers_multiple_stacks(self):
        result = self._call(databases=["MongoDB"])
        mg = next(
            (s for s in result if "mongo" in s["title"].lower()
             or "schema" in s["title"].lower()), None
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

    def test_kafka_suggestion_when_kafka_detected(self):
        titles = [s["title"] for s in self._call(infra=["Kafka"])]
        assert any("kafka" in t.lower() or "consumer" in t.lower() for t in titles)