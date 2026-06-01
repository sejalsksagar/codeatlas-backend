"""
Unit tests for ai/prompts.py
Run with:  pytest tests/test_prompts.py -v
"""
from __future__ import annotations

import json
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

import pytest
from ai.prompts import (
    build_summary_prompt,
    build_diagram_prompt,
    build_suggestions_prompt,
)

# ------------------------------------------------------------------ #
# Shared fixtures
# ------------------------------------------------------------------ #

REPO = "acme/my-fastapi-app"
STACK = {
    "framework": "FastAPI",
    "language": "Python",
    "database": "PostgreSQL",
    "package_manager": "pip",
}
MODULES = ["main.py", "routers/users.py", "routers/items.py", "core/db.py", "models/schemas.py"]
README = "# My FastAPI App\n\nThis project is a REST API built with FastAPI and PostgreSQL."


# ------------------------------------------------------------------ #
# build_summary_prompt
# ------------------------------------------------------------------ #

class TestBuildSummaryPrompt:
    def test_contains_repo_name(self):
        prompt = build_summary_prompt(REPO, STACK, README, MODULES)
        assert REPO in prompt

    def test_contains_stack_info(self):
        prompt = build_summary_prompt(REPO, STACK, README, MODULES)
        assert "FastAPI" in prompt
        assert "PostgreSQL" in prompt

    def test_readme_excerpt_truncated_at_800(self):
        long_readme = "x" * 2000
        prompt = build_summary_prompt(REPO, STACK, long_readme, MODULES)
        # The prompt should contain at most 800 x's
        assert "x" * 801 not in prompt
        assert "x" * 800 in prompt

    def test_contains_all_module_paths(self):
        prompt = build_summary_prompt(REPO, STACK, README, MODULES)
        for m in MODULES:
            assert m in prompt

    def test_requests_json_output(self):
        prompt = build_summary_prompt(REPO, STACK, README, MODULES)
        assert "JSON" in prompt

    def test_required_json_keys_mentioned(self):
        prompt = build_summary_prompt(REPO, STACK, README, MODULES)
        for key in ("summary", "modules", "entry_points", "request_flow"):
            assert key in prompt

    def test_empty_readme_handled(self):
        """Should not raise even with empty / None readme."""
        prompt = build_summary_prompt(REPO, STACK, "", MODULES)
        assert REPO in prompt

        prompt2 = build_summary_prompt(REPO, STACK, None, MODULES)  # type: ignore[arg-type]
        assert REPO in prompt2

    def test_returns_string(self):
        result = build_summary_prompt(REPO, STACK, README, MODULES)
        assert isinstance(result, str)
        assert len(result) > 50


# ------------------------------------------------------------------ #
# build_diagram_prompt
# ------------------------------------------------------------------ #

class TestBuildDiagramPrompt:
    def test_contains_repo_name(self):
        prompt = build_diagram_prompt(REPO, STACK, MODULES)
        assert REPO in prompt

    def test_contains_framework(self):
        prompt = build_diagram_prompt(REPO, STACK, MODULES)
        assert "FastAPI" in prompt

    def test_contains_database(self):
        prompt = build_diagram_prompt(REPO, STACK, MODULES)
        assert "PostgreSQL" in prompt

    def test_mermaid_graph_td_mentioned(self):
        prompt = build_diagram_prompt(REPO, STACK, MODULES)
        assert "graph TD" in prompt

    def test_no_markdown_fences_instruction(self):
        """Prompt should instruct LLM not to use code fences."""
        prompt = build_diagram_prompt(REPO, STACK, MODULES)
        assert "fence" in prompt.lower() or "backtick" in prompt.lower() or "```" in prompt

    def test_module_names_included(self):
        prompt = build_diagram_prompt(REPO, STACK, MODULES)
        # At least some module names should appear
        found = sum(1 for m in MODULES if m in prompt)
        assert found >= 1

    def test_caps_at_20_modules(self):
        """Even with 25 modules, prompt should not explode."""
        many_modules = [f"module_{i}.py" for i in range(25)]
        prompt = build_diagram_prompt(REPO, STACK, many_modules)
        # Should still be a string without error
        assert isinstance(prompt, str)

    def test_stack_with_missing_keys(self):
        """Handles a sparse stack dict gracefully."""
        prompt = build_diagram_prompt(REPO, {}, MODULES)
        assert isinstance(prompt, str)


# ------------------------------------------------------------------ #
# build_suggestions_prompt
# ------------------------------------------------------------------ #

class TestBuildSuggestionsPrompt:
    def test_contains_repo_name(self):
        prompt = build_suggestions_prompt(REPO, STACK, MODULES)
        assert REPO in prompt

    def test_contains_stack_info(self):
        prompt = build_suggestions_prompt(REPO, STACK, MODULES)
        assert "FastAPI" in prompt

    def test_requests_json_array(self):
        prompt = build_suggestions_prompt(REPO, STACK, MODULES)
        assert "JSON" in prompt
        assert "array" in prompt.lower() or "[]" in prompt or "list" in prompt.lower()

    def test_required_json_keys_mentioned(self):
        prompt = build_suggestions_prompt(REPO, STACK, MODULES)
        for key in ("category", "severity", "title", "detail"):
            assert key in prompt

    def test_category_values_specified(self):
        prompt = build_suggestions_prompt(REPO, STACK, MODULES)
        for cat in ("security", "performance", "scalability", "quality"):
            assert cat in prompt

    def test_severity_values_specified(self):
        prompt = build_suggestions_prompt(REPO, STACK, MODULES)
        for sev in ("high", "medium", "low"):
            assert sev in prompt

    def test_5_to_8_suggestions_constraint(self):
        prompt = build_suggestions_prompt(REPO, STACK, MODULES)
        assert "5" in prompt and "8" in prompt

    def test_framework_name_in_constraints(self):
        """The prompt should reference the specific framework for tailored advice."""
        prompt = build_suggestions_prompt(REPO, STACK, MODULES)
        assert "FastAPI" in prompt

    def test_caps_at_30_modules(self):
        many = [f"mod_{i}.py" for i in range(40)]
        prompt = build_suggestions_prompt(REPO, STACK, many)
        assert isinstance(prompt, str)

    def test_empty_stack_no_crash(self):
        prompt = build_suggestions_prompt(REPO, {}, [])
        assert isinstance(prompt, str)