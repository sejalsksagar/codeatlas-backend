from __future__ import annotations

import json


# ------------------------------------------------------------------ #
# 1. Summary prompt
# ------------------------------------------------------------------ #


def build_summary_prompt(
    repo_name: str,
    stack: dict,
    readme: str,
    modules: list[str],
) -> str:
    """
    Build a prompt that asks the LLM to return a JSON object describing the repo.

    Expected JSON shape::

        {
          "summary": "<2-3 sentence overview>",
          "modules": [{"name": "...", "path": "...", "description": "..."}],
          "entry_points": ["main.py", "app/server.py"],
          "request_flow": "<1 sentence describing how a request travels through the code>"
        }
    """
    readme_excerpt = (readme or "")[:800]
    stack_json = json.dumps(stack, indent=2)
    modules_list = "\n".join(f"  - {m}" for m in modules)

    return f"""You are a senior software engineer analysing a GitHub repository.

Repository: {repo_name}

Detected tech stack:
{stack_json}

README (first 800 characters):
\"\"\"
{readme_excerpt}
\"\"\"

Module / directory listing:
{modules_list}

Your task: return ONLY a valid JSON object — no explanation, no markdown fences, \
no extra text before or after the JSON.

The JSON object must have exactly these keys:
  "summary"      : string — 2-3 sentences describing what the project does and who it is for.
  "modules"      : array of objects, each with "name" (string), "path" (string), \
"description" (string, 1 sentence).
  "entry_points" : array of file path strings that serve as the main entry points.
  "request_flow" : string — 1 sentence tracing the path of an inbound request \
from network to response (or the equivalent for non-web projects).

Output the JSON object now:"""


# ------------------------------------------------------------------ #
# 2. Diagram prompt
# ------------------------------------------------------------------ #


def build_diagram_prompt(
    repo_name: str,
    stack: dict,
    modules: list[str],
) -> str:
    """
    Build a prompt that asks the LLM to return a Mermaid.js ``graph TD`` diagram.

    The response must be raw Mermaid text — no fences, no explanation.
    """
    framework = stack.get("framework") or stack.get("frameworks") or "unknown"
    db = stack.get("database") or stack.get("db") or "none detected"
    module_names = ", ".join(modules[:20])  # cap to avoid token bloat

    return f"""You are a software architecture expert.

Repository: {repo_name}
Primary framework: {framework}
Database / storage: {db}
Key modules / directories: {module_names}

Your task: return ONLY valid Mermaid.js graph TD syntax that visualises the \
high-level architecture of this project.

Rules:
  - Start directly with "graph TD" — no code fences, no backticks, no explanation.
  - Show the main components (entry points, routers/controllers, services, \
data layer, external APIs) as nodes.
  - Use meaningful node IDs and labels derived from the actual module names above.
  - Add directional arrows to show data / request flow.
  - Keep it concise: 6-14 nodes maximum.

Output the Mermaid diagram now:"""


# ------------------------------------------------------------------ #
# 3. Suggestions prompt
# ------------------------------------------------------------------ #


def build_suggestions_prompt(
    repo_name: str,
    stack: dict,
    modules: list[str],
) -> str:
    """
    Build a prompt that asks the LLM to return a JSON array of improvement suggestions.

    Expected JSON shape::

        [
          {
            "category": "security",          // security|performance|scalability|quality
            "severity": "high",              // high|medium|low
            "title": "Short title",
            "detail": "1-2 sentence explanation and recommendation.",
            "file_hint": "path/to/file.py"  // optional, omit if not applicable
          },
          ...
        ]
    """
    stack_json = json.dumps(stack, indent=2)
    modules_list = ", ".join(modules[:30])

    return f"""You are a senior code-review engineer conducting an architectural review.

Repository: {repo_name}

Detected tech stack:
{stack_json}

Key modules / files: {modules_list}

Your task: return ONLY a valid JSON array — no explanation, no markdown fences, \
no extra text before or after the JSON.

Each element in the array must be an object with these keys:
  "category"  : one of "security", "performance", "scalability", "quality"
  "severity"  : one of "high", "medium", "low"
  "title"     : short string (≤10 words) naming the issue or suggestion
  "detail"    : string — 1-2 sentences explaining the problem and a concrete fix
  "file_hint" : string — a relevant file or directory path (omit key if not applicable)

Constraints:
  - Return between 5 and 8 suggestions.
  - Base suggestions on the ACTUAL stack detected above (e.g. flag known \
vulnerabilities or anti-patterns specific to {stack.get("framework", "the detected framework")}).
  - At least one suggestion must be "high" severity.
  - Spread suggestions across at least 3 different categories.
  - Do NOT invent modules that are not listed.

Output the JSON array now:"""