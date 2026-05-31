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


def build_diagram_prompt(repo_name: str, stack: dict, modules: list[str]) -> str:
    framework = stack.get("framework") or stack.get("frameworks") or "unknown"
    db = stack.get("database") or stack.get("db") or "none detected"
    module_names = ", ".join(modules[:30])

    return f"""
You are a senior software architecture reverse-engineering expert.

Your task is to infer the TRUE high-level architecture of a code repository and output it as a Mermaid "graph TD" diagram.

Repository: {repo_name}
Detected framework(s): {framework}
Database / storage: {db}
Available modules/directories:
{module_names}

IMPORTANT ARCHITECTURE ABSTRACTION RULE:

You are NOT restricted to directory names.

You MUST map code structure → system components.

Allowed transformations:
- fastapi/ → FastAPI core framework
- routing/ → routing subsystem
- security/ → auth/security subsystem
- openapi/ → schema generation system

DO NOT treat:
- tests, docs, scripts as architecture nodes unless they participate in runtime behavior

Tests/docs/scripts should be placed ONLY as side nodes disconnected from core system flow.

------------------------------------------------------------
CRITICAL RULES
------------------------------------------------------------

1. OUTPUT FORMAT
- Output ONLY Mermaid graph TD
- No explanations, no markdown, no backticks
- Must start with: graph TD

2. NO CYCLICAL GRAPHS
- The graph MUST be a Directed Acyclic Graph (DAG)
- NO cycles, NO bidirectional edges
- If a relationship is bidirectional, choose ONLY the dominant direction

3. NO FORCED PIPELINE STRUCTURE
- Do NOT assume architecture is linear (A → B → C → D)
- Do NOT default to "entry → routing → service → data"
- Only use linear flow IF the repo explicitly behaves like a pipeline system

------------------------------------------------------------
STEP 1: CLASSIFY ARCHITECTURE TYPE
------------------------------------------------------------

Infer ONE primary architecture style:

A. HUB-AND-SPOKE (frameworks like FastAPI, Express, Django)
   - Central core with multiple independent subsystems

B. LAYERED (traditional backend apps)
   - entry → routing → business logic → data access

C. MODULAR / PLUGIN-BASED (libraries, extensible systems)
   - core engine → plugins/extensions/modules

D. EVENT-DRIVEN (async systems, messaging systems)
   - event source → dispatcher → handlers → sinks

E. PIPELINE (ONLY if explicitly sequential processing)
   - strict step-by-step transformation flow

F. CLI / TOOLING
   - CLI entry → parser → commands → utilities

G. FRONTEND ARCHITECTURE
   - entry → components → state → API layer

------------------------------------------------------------
STEP 2: BUILD GRAPH BASED ON STYLE (IMPORTANT)
------------------------------------------------------------

IF HUB-AND-SPOKE:
- Create ONE central node (core/framework)
- Connect it to independent subsystems
- Subsystems should NOT depend on each other unless clearly implied

IF LAYERED:
- Build top-down layers
- Each layer may depend on lower layers only

IF MODULAR / PLUGIN:
- core engine → modules/plugins/utilities
- plugins should NOT form chains unless explicitly implied

IF EVENT-DRIVEN:
- event source → dispatcher/bus → handlers → external systems
- avoid linear chains

IF PIPELINE:
- ONLY then use strict linear flow

IF CLI:
- CLI entry → parser → commands → utilities → external calls

IF FRONTEND:
- UI entry → components → state → API client → backend

------------------------------------------------------------
STEP 3: NODE RULES
------------------------------------------------------------

- Nodes MUST come from actual module names OR clearly inferred architectural roles
- You MAY group folders into meaningful components (e.g., "routing/", "auth/")
- Do NOT invent unrelated layers

------------------------------------------------------------
STEP 4: EDGE RULES
------------------------------------------------------------

Edges represent ONLY:
- runtime flow OR
- import dependency OR
- initialization order OR
- control flow

DO NOT:
- force sequential chains
- connect everything to everything
- create artificial "step-by-step pipelines"

------------------------------------------------------------
STEP 5: SIZE CONSTRAINT
------------------------------------------------------------

- 6 to 14 nodes total
- Prefer hub or modular structure over long chains

------------------------------------------------------------
FINAL OUTPUT RULES
------------------------------------------------------------

- Must be valid Mermaid graph TD
- Must be DAG
- Must reflect correct architecture type
- Must avoid artificial linearization

Now generate the architecture diagram:
"""


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