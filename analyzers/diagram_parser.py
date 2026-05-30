"""
analyzers/diagram_parser.py
---------------------------
Regex-based Mermaid graph TD parser.

Parses a raw Mermaid ``graph TD`` (or ``graph LR``) string into plain Python
dicts that can be serialised into the DiagramResponse.

Supported syntax subset
~~~~~~~~~~~~~~~~~~~~~~~~
Node definitions::

    A[Label]          rectangle
    A(Label)          rounded rectangle
    A((Label))        circle
    A{Label}          diamond
    A>Label]          asymmetric
    A["Label"]        quoted label

Edge definitions::

    A --> B
    A -->|label| B
    A -- label --> B
    A --- B           (undirected, treated as directed)
    A -.-> B          (dotted)
    A ==> B           (thick)

Lines starting with ``%%`` are comments and are skipped.
``graph TD``, ``graph LR``, ``flowchart TD``, ``flowchart LR`` header lines are skipped.

Public API
~~~~~~~~~~
    parse_mermaid(source: str) -> tuple[list[dict], list[dict]]

    Returns:
        nodes  – list of {"id": str, "label": str}
        edges  – list of {"from": str, "to": str, "label": str}
"""

from __future__ import annotations

import re

# --------------------------------------------------------------------------- #
# Compiled patterns
# --------------------------------------------------------------------------- #

# Header lines: graph/flowchart direction declarations
_HEADER = re.compile(r"^\s*(?:graph|flowchart)\s+(?:TD|LR|TB|RL|BT)\s*$", re.IGNORECASE)

# Comment lines
_COMMENT = re.compile(r"^\s*%%")

# --------------------------------------------------------------------------- #
# Node shape suffix — matches the bracket/paren/brace decoration after an ID.
# Used both for standalone node definitions AND for inline labels on edge lines.
# Captures the display label in group 1.
# --------------------------------------------------------------------------- #
_NODE_SHAPE = re.compile(
    r'\s*(?:'
    r'\[\[([^\]]*)\]\]'      # [[text]] — subroutine
    r'|\[\(([^)]*)\)\]'      # [(text)] — cylindrical / database
    r'|\(\(([^)]*)\)\)'      # ((text)) — circle
    r'|\[([^\]]*)\]'         # [text]   — rectangle   ← most common
    r'|\(([^)]*)\)'          # (text)   — rounded
    r'|\{([^}]*)\}'          # {text}   — diamond
    r'|>([^\]]*)\]'          # >text]   — asymmetric
    r')'
)

# Strips node shape decorations from a line, but ONLY when they immediately
# follow a word character (the end of a node ID).  Uses a lookbehind so that
# arrow syntax like `-->` and `|label|` is preserved.
_SHAPE_ONLY = re.compile(
    r'(?<=\w)'            # must be preceded by a word char (end of node ID)
    r'\s*(?:'
    r'\[\[[^\]]*\]\]'     # [[text]] — subroutine
    r'|\[\([^)]*\)\]'     # [(text)] — cylindrical / database
    r'|\(\([^)]*\)\)'     # ((text)) — circle
    r'|\[[^\]]*\]'        # [text]   — rectangle   ← most common
    r'|\([^)]*\)'         # (text)   — rounded
    r'|\{[^}]*\}'         # {text}   — diamond
    r'|>[^\]]*\]'         # >text]   — asymmetric
    r')'
)

# Full edge line — node tokens on each side of an arrow.
# We pre-process the line to strip shape decorations before matching,
# so the regex only needs to handle bare IDs.
_EDGE = re.compile(
    r"^\s*"
    r"(\w[\w-]*)"                        # from node id (bare, after stripping shapes)
    r"\s*"
    r"(?:--[->.]?[->]?|==+>)"           # arrow shaft (-->, ---, -.->, ==>)
    r"(?:\|([^|]*)\|)?"                  # optional |label|
    r"\s*"
    r"(\w[\w-]*)"                        # to node id (bare)
    r"\s*$"
)

# Inline text between arrow and destination: A -- some text --> B
_EDGE_WITH_TEXT = re.compile(
    r"^\s*"
    r"(\w[\w-]*)"                        # from id
    r"\s+--\s+"
    r"([^-]+?)"                          # inline label text
    r"\s*-->\s*"
    r"(\w[\w-]*)"                        # to id
    r"\s*$"
)

# Standalone node definition (whole line is just a node, no arrow).
_NODE_DEF = re.compile(
    r"^\s*(\w[\w-]*)"                    # node id
    + _NODE_SHAPE.pattern
    + r"\s*$"
)


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #


def parse_mermaid(source: str) -> tuple[list[dict], list[dict]]:
    """
    Parse a Mermaid ``graph TD`` string into node and edge dicts.

    Unknown or unsupported lines are silently skipped so the parser is
    tolerant of LLM output that doesn't perfectly follow the spec.

    Args:
        source: Raw Mermaid text.

    Returns:
        (nodes, edges) where
        ``nodes`` is a list of ``{"id": str, "label": str}`` dicts and
        ``edges`` is a list of ``{"from": str, "to": str, "label": str}`` dicts.
    """
    node_map: dict[str, str] = {}  # id → label
    edges: list[dict] = []
    seen_edges: set[tuple[str, str, str]] = set()

    for raw_line in source.splitlines():
        line = raw_line.strip()

        if not line:
            continue
        if _COMMENT.match(line):
            continue
        if _HEADER.match(line):
            continue

        # ── Check whether the line contains an arrow (edge line) ─────────
        is_edge_line = "--" in line or "==>" in line

        if is_edge_line:
            # Extract and register inline node labels BEFORE stripping shapes.
            # e.g. "Client[Browser] --> API[FastAPI]" → register Client→"Browser"
            _extract_inline_node_labels(line, node_map)

            # Strip all shape decorations so the bare-ID edge regex can match.
            # "Client[Browser] --> API[FastAPI]" → "Client --> API"
            stripped = _strip_node_shapes(line)

            # ── Try inline-text edge first (A -- text --> B) ──────────────
            m = _EDGE_WITH_TEXT.match(stripped)
            if m:
                from_id, label, to_id = m.group(1), m.group(2).strip(), m.group(3)
                _register_nodes(node_map, from_id, to_id)
                _add_edge(edges, seen_edges, from_id, to_id, label)
                continue

            # ── Try standard edge (A --> B  /  A -->|label| B) ───────────
            m = _EDGE.match(stripped)
            if m:
                from_id, label, to_id = m.group(1), (m.group(2) or "").strip(), m.group(3)
                _register_nodes(node_map, from_id, to_id)
                _add_edge(edges, seen_edges, from_id, to_id, label)
                continue

        # ── Standalone node definition ────────────────────────────────────
        m = _NODE_DEF.match(line)
        if m:
            node_id = m.group(1)
            label = next(
                (g for g in m.groups()[1:] if g is not None),
                node_id,
            )
            label = label.strip().strip('"').strip("'")
            node_map[node_id] = label or node_id

    # Build final node list, preserving insertion order from node_map
    nodes = [{"id": nid, "label": lbl} for nid, lbl in node_map.items()]
    return nodes, edges


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _strip_node_shapes(line: str) -> str:
    """
    Remove Mermaid node-shape decorations from *line* while preserving
    arrow syntax (``-->``, ``|label|``, etc.).

    Uses a lookbehind so only brackets/parens that immediately follow a word
    character (i.e. the end of a node ID) are removed.

    ``"Client[Browser] --> API[FastAPI]"``  →  ``"Client --> API"``
    ``"API -->|query| DB[(PostgreSQL)]"``   →  ``"API -->|query| DB"``
    """
    return _SHAPE_ONLY.sub("", line).strip()


def _extract_inline_node_labels(line: str, node_map: dict[str, str]) -> None:
    """
    Walk *line* left-to-right finding every ``ID[Label]``-style token and
    register the label in *node_map* (without overwriting an existing entry
    that was set by a standalone node definition).

    This handles the common LLM output pattern where nodes are defined
    inline on edge lines rather than on separate lines.
    """
    # Scan each word boundary for a node token (ID + optional shape)
    for m in re.finditer(r"(\w[\w-]*)" + _NODE_SHAPE.pattern, line):
        node_id = m.group(1)
        # groups()[1:] are the shape capture groups
        label = next((g for g in m.groups()[1:] if g is not None), None)
        if label is not None:
            label = label.strip().strip('"').strip("'")
            # Don't overwrite a label that came from a standalone node def
            if node_id not in node_map:
                node_map[node_id] = label or node_id


def _register_nodes(node_map: dict[str, str], *ids: str) -> None:
    """Register node IDs that appear in edges but have no explicit definition."""
    for nid in ids:
        if nid not in node_map:
            node_map[nid] = nid  # use id as label until we see a definition


def _add_edge(
    edges: list[dict],
    seen: set[tuple[str, str, str]],
    from_id: str,
    to_id: str,
    label: str,
) -> None:
    """Append a unique edge dict to *edges*."""
    key = (from_id, to_id, label)
    if key not in seen:
        seen.add(key)
        edges.append({"from": from_id, "to": to_id, "label": label})