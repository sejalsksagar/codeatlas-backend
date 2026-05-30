#!/usr/bin/env python3
"""
Manual integration test — calls the REAL GitHub Models API.

Usage:
    export GITHUB_MODELS_TOKEN="ghp_..."
    python tests/integration_llm.py

Requires a valid GitHub Models PAT. Will cost a small number of tokens.
"""
from __future__ import annotations

import asyncio
import os
import sys
import json
import pathlib
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from ai.github_models import call_llm, LLMUnavailableError
from ai.prompts import build_summary_prompt, build_diagram_prompt, build_suggestions_prompt

TOKEN = os.environ.get("GITHUB_MODELS_TOKEN", "")

SAMPLE_STACK = {"framework": "FastAPI", "language": "Python", "database": "PostgreSQL"}
SAMPLE_MODULES = ["main.py", "routers/users.py", "core/db.py", "models/schemas.py"]
SAMPLE_README = "# Demo App\n\nA FastAPI REST API backed by PostgreSQL."


async def test_raw_call():
    print("\n── Raw call_llm ──")
    reply = await call_llm("Reply with exactly: PONG", token=TOKEN)
    print(f"  Response: {reply!r}")
    assert "PONG" in reply.upper(), "Expected PONG in response"
    print("  ✓ PASSED")


async def test_summary_prompt():
    print("\n── Summary prompt ──")
    prompt = build_summary_prompt("acme/demo", SAMPLE_STACK, SAMPLE_README, SAMPLE_MODULES)
    raw = await call_llm(prompt, token=TOKEN)
    print(f"  Raw response (first 300 chars): {raw[:300]}")
    parsed = json.loads(raw)
    assert "summary" in parsed
    assert "modules" in parsed
    assert "entry_points" in parsed
    assert "request_flow" in parsed
    print(f"  Summary: {parsed['summary']}")
    print("  ✓ PASSED")


async def test_diagram_prompt():
    print("\n── Diagram prompt ──")
    prompt = build_diagram_prompt("acme/demo", SAMPLE_STACK, SAMPLE_MODULES)
    raw = await call_llm(prompt, token=TOKEN)
    print(f"  Raw response:\n{raw[:500]}")
    assert "graph TD" in raw, "Expected Mermaid graph TD"
    assert "```" not in raw, "Response should not contain markdown fences"
    print("  ✓ PASSED")


async def test_suggestions_prompt():
    print("\n── Suggestions prompt ──")
    prompt = build_suggestions_prompt("acme/demo", SAMPLE_STACK, SAMPLE_MODULES)
    raw = await call_llm(prompt, token=TOKEN)
    print(f"  Raw response (first 400 chars): {raw[:400]}")
    parsed = json.loads(raw)
    assert isinstance(parsed, list)
    assert 5 <= len(parsed) <= 8, f"Expected 5-8 suggestions, got {len(parsed)}"
    for item in parsed:
        assert item["category"] in ("security", "performance", "scalability", "quality")
        assert item["severity"] in ("high", "medium", "low")
        assert "title" in item
        assert "detail" in item
    print(f"  Got {len(parsed)} suggestions")
    print("  ✓ PASSED")


async def main():
    if not TOKEN:
        print("ERROR: GITHUB_MODELS_TOKEN environment variable not set.")
        print("See README for how to get a token.")
        sys.exit(1)

    tests = [test_raw_call, test_summary_prompt, test_diagram_prompt, test_suggestions_prompt]
    passed = 0
    for t in tests:
        try:
            await t()
            passed += 1
        except LLMUnavailableError as e:
            print(f"  ✗ LLMUnavailableError: {e}")
        except AssertionError as e:
            print(f"  ✗ Assertion failed: {e}")
        except json.JSONDecodeError as e:
            print(f"  ✗ JSON parse error: {e}")

    print(f"\n{'='*40}")
    print(f"Results: {passed}/{len(tests)} passed")
    sys.exit(0 if passed == len(tests) else 1)


if __name__ == "__main__":
    asyncio.run(main())