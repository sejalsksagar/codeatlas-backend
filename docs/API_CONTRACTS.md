# CodeAtlas API Contract

Base URL: `http://localhost:8000` (development)

All requests and responses use `Content-Type: application/json`.
All routes return `{"detail": "..."}` on error with the appropriate HTTP status code.

---

## Common data shapes

These sub-objects appear in multiple responses. They are documented once here and referenced below.

### `StackInfo`

Detected technology stack. All fields default to empty lists / null if not detected.

```json
{
  "languages":       ["Python"],
  "frameworks":      ["FastAPI"],
  "databases":       ["PostgreSQL"],
  "infra":           ["Docker Compose", "GitHub Actions"],
  "test_frameworks": ["pytest"],
  "package_manager": "pip"
}
```

### `ModuleInfo`

Represents one top-level module or directory.

```json
{
  "name":        "src",
  "path":        "src",
  "description": "Primary source code directory."
}
```

### `Suggestion`

One architectural improvement suggestion.

```json
{
  "category":  "security",
  "severity":  "high",
  "title":     "Add rate limiting",
  "detail":    "FastAPI has no built-in rate limiting. Add slowapi to protect public endpoints.",
  "file_hint": "main.py"
}
```

`category` is one of: `security` · `performance` · `scalability` · `quality`  
`severity` is one of: `high` · `medium` · `low`  
`file_hint` is optional — omitted when no specific file is applicable.

### `DiagramNode`

One node in the architecture graph.

```json
{ "id": "A", "label": "FastAPI Entry Point" }
```

`id` is the Mermaid node identifier (single letter or short string).  
`label` is the human-readable display name.  
**No React Flow keys** (`data`, `position`, `type`) are included. The frontend is responsible for layout enrichment.

### `DiagramEdge`

One directed edge in the architecture graph.

```json
{ "from": "A", "to": "B", "label": "HTTP" }
```

`label` is an empty string `""` when the edge is unlabelled.  
**No React Flow keys** (`id`, `source`, `target`, `type`) are included.

---

## `GET /health`

Health check.

**Response 200**

```json
{ "status": "ok" }
```

---

## `POST /analyze`

Full repository analysis. Fetches the file tree, detects the technology stack, and returns an AI-generated (or heuristic fallback) summary.

**Request body**

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `repo_url` | string | ✅ | — | Public GitHub repository URL |
| `branch` | string | | `"HEAD"` | Branch name, tag, or commit SHA |
| `question` | string | | `null` | Reserved for `/ask` — ignored by this endpoint |

```json
{
  "repo_url": "https://github.com/tiangolo/fastapi",
  "branch": "master"
}
```

**Response 200**

```json
{
  "status": "ok",
  "repo": "tiangolo/fastapi",
  "branch": "master",
  "stack": {
    "languages":       ["Python", "JavaScript/TypeScript"],
    "frameworks":      ["FastAPI"],
    "databases":       [],
    "infra":           ["GitHub Actions"],
    "test_frameworks": ["pytest"],
    "package_manager": "uv"
  },
  "summary": "FastAPI is a modern, high-performance web framework for building APIs with Python 3.6+ based on standard Python type hints.",
  "modules": [
    { "name": "fastapi",  "path": "fastapi",  "description": "FastAPI application — routing, dependency injection, and middleware." },
    { "name": "tests",    "path": "tests",    "description": "Automated test suite." },
    { "name": "docs",     "path": "docs",     "description": "Project documentation." },
    { "name": "scripts",  "path": "scripts",  "description": "Utility and automation scripts." }
  ],
  "entry_points": ["fastapi/__init__.py"],
  "request_flow": "An inbound request is received by the FastAPI application, routed to the appropriate endpoint, processed by the handler, and a response is returned.",
  "used_fallback": false
}
```

| Field | Type | Notes |
|---|---|---|
| `status` | `"ok"` | Always `"ok"` on 200 |
| `repo` | string | `"owner/repo"` normalised form |
| `branch` | string | Echoes request branch |
| `stack` | `StackInfo` | See common shapes |
| `summary` | string | 2–3 sentence plain-text overview. Never contains raw Markdown or HTML |
| `modules` | `ModuleInfo[]` | Top-level directories with descriptions |
| `entry_points` | string[] | Relative file paths. Test-directory paths are excluded unless no other entry point exists |
| `request_flow` | string | One sentence tracing a request through the system |
| `used_fallback` | boolean | `true` if AI was unavailable and heuristics were used |

**Fallback example** (`used_fallback: true`)

```json
{
  "status": "ok",
  "repo": "tiangolo/fastapi",
  "branch": "master",
  "stack": { "...": "same as above" },
  "summary": "FastAPI framework, high performance, easy to learn, fast to code, ready for production. Built with languages: Python; frameworks: FastAPI.",
  "modules": [
    { "name": "fastapi",   "path": "fastapi",   "description": "FastAPI application — routing, dependency injection, and middleware." },
    { "name": "docs_src",  "path": "docs_src",  "description": "Source files for the documentation site (e.g. mkdocs)." },
    { "name": "tests",     "path": "tests",     "description": "Automated test suite." }
  ],
  "entry_points": ["fastapi/__init__.py"],
  "request_flow": "Request enters FastAPI app → routed via APIRouter → handler calls service layer → data layer",
  "used_fallback": true
}
```

**Error responses**

| Status | Condition | Example body |
|---|---|---|
| 422 | Non-GitHub URL or malformed body | `{"detail": "Not a GitHub URL: 'https://gitlab.com/...'"}`|
| 404 | Repo not found or private | `{"detail": "Repository 'owner/repo' not found or is private."}` |
| 429 | GitHub API rate limit exceeded | `{"detail": "GitHub rate limit exceeded (HTTP 403)"}` |
| 502 | GitHub API unreachable | `{"detail": "..."}` |
| 500 | Unexpected server error | `{"detail": "Unexpected error: ..."}` |

---

## `POST /diagram`

Generate a Mermaid architecture diagram for a repository. Accepts the `stack` and `modules` output from `/analyze` directly — no re-fetching required.

**Request body**

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `repo_url` | string | ✅ | — | Public GitHub URL (used for validation and labelling only) |
| `stack` | object | | `{}` | `StackInfo`-shaped dict from `/analyze` |
| `modules` | array | | `[]` | Module name strings **or** `ModuleInfo` objects from `/analyze` — both accepted |

```json
{
  "repo_url": "https://github.com/tiangolo/fastapi",
  "stack": {
    "languages":       ["Python"],
    "frameworks":      ["FastAPI"],
    "databases":       [],
    "infra":           ["GitHub Actions"],
    "test_frameworks": ["pytest"],
    "package_manager": "uv"
  },
  "modules": [
    { "name": "fastapi", "path": "fastapi", "description": "..." },
    { "name": "tests",   "path": "tests",   "description": "..." }
  ]
}
```

Note: `modules` also accepts plain strings — `["fastapi", "tests"]` — for convenience.

**Response 200**

```json
{
  "status": "ok",
  "repo": "tiangolo/fastapi",
  "mermaid_source": "graph TD\n    A[Entry Point] --> B[FastAPI Routers]\n    B --> C[Controllers]\n    C --> D[Services]",
  "nodes": [
    { "id": "A", "label": "Entry Point" },
    { "id": "B", "label": "FastAPI Routers" },
    { "id": "C", "label": "Controllers" },
    { "id": "D", "label": "Services" }
  ],
  "edges": [
    { "from": "A", "to": "B", "label": "" },
    { "from": "B", "to": "C", "label": "" },
    { "from": "C", "to": "D", "label": "" }
  ],
  "used_fallback": false
}
```

**Fallback example** (`used_fallback: true`)

The fallback produces a simpler Client → Framework → Module → Database waterfall. Node IDs are descriptive strings, not single letters.

```json
{
  "status": "ok",
  "repo": "sejalsksagar/pos-emi-reward-negotiation-system",
  "mermaid_source": "graph TD\n    Client[\"Client\"]\n    framework[\"Spring Boot\"]\n    mod_0[\"backend\"]\n    database[(\"PostgreSQL\")]\n    Client -->|HTTP| framework\n    framework --> mod_0\n    mod_0 -->|query| database",
  "nodes": [
    { "id": "Client",    "label": "Client" },
    { "id": "framework", "label": "Spring Boot" },
    { "id": "mod_0",     "label": "backend" },
    { "id": "database",  "label": "PostgreSQL" }
  ],
  "edges": [
    { "from": "Client",    "to": "framework", "label": "HTTP" },
    { "from": "framework", "to": "mod_0",     "label": "" },
    { "from": "mod_0",     "to": "database",  "label": "query" }
  ],
  "used_fallback": true
}
```

| Field | Type | Notes |
|---|---|---|
| `mermaid_source` | string | Raw `graph TD` Mermaid syntax. No fences, no backticks |
| `nodes` | `DiagramNode[]` | See common shapes. Never contains `data`/`position`/`type` |
| `edges` | `DiagramEdge[]` | See common shapes. Never contains `id`/`source`/`target` |
| `used_fallback` | boolean | `true` if AI was unavailable |

**Error responses**

| Status | Condition |
|---|---|
| 422 | Non-GitHub URL or malformed body |
| 500 | Unexpected server error |

---

## `POST /suggestions`

Return a list of actionable architectural improvement suggestions for a repository.

**Request body**

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `repo_url` | string | ✅ | — | Public GitHub URL (validation and labelling only) |
| `stack` | object | | `{}` | `StackInfo`-shaped dict from `/analyze` |
| `modules` | array | | `[]` | Module strings or `ModuleInfo` objects — both accepted |

```json
{
  "repo_url": "https://github.com/sejalsksagar/pos-emi-reward-negotiation-system",
  "stack": {
    "languages":       ["Java"],
    "frameworks":      ["Spring Boot"],
    "databases":       ["PostgreSQL", "MongoDB"],
    "infra":           ["Docker Compose", "Kafka"],
    "test_frameworks": ["Spring Boot Test", "JUnit"],
    "package_manager": null
  },
  "modules": [
    { "name": "backend", "path": "backend", "description": "..." }
  ]
}
```

**Response 200**

```json
{
  "status": "ok",
  "repo": "sejalsksagar/pos-emi-reward-negotiation-system",
  "suggestions": [
    {
      "category":  "security",
      "severity":  "high",
      "title":     "Use HTTPS for API endpoints",
      "detail":    "Ensure all API endpoints are served over HTTPS. Configure SSL in your Spring Boot application via application.properties.",
      "file_hint": "src/main/resources/application.properties"
    },
    {
      "category":  "performance",
      "severity":  "medium",
      "title":     "Optimize database queries",
      "detail":    "Review and add indexes in PostgreSQL for frequently queried columns. Use Spring Data JPA's @Query annotation for custom optimised queries.",
      "file_hint": "src/main/java/com/example/repository"
    },
    {
      "category":  "scalability",
      "severity":  "medium",
      "title":     "Implement caching for frequent data",
      "detail":    "Introduce Redis caching for hot data to reduce PostgreSQL load and improve response times.",
      "file_hint": "src/main/java/com/example/service"
    }
  ],
  "used_fallback": false
}
```

**Fallback example** (`used_fallback: true`)

The fallback fires rule-based suggestions derived from the detected stack. Rules are stack-agnostic where possible (e.g. the PostgreSQL pooling suggestion covers HikariCP for Java, asyncpg for Python, and pgbouncer for any stack). Suggestions are sorted `high → medium → low`.

```json
{
  "status": "ok",
  "repo": "sejalsksagar/pos-emi-reward-negotiation-system",
  "suggestions": [
    {
      "category":  "performance",
      "severity":  "medium",
      "title":     "Ensure connection pooling is configured",
      "detail":    "PostgreSQL has a limited connection ceiling. Configure a connection pool appropriate to your stack — HikariCP (Java/Spring Boot), asyncpg + SQLAlchemy async engine (Python), or pgbouncer as a sidecar — to avoid exhausting the server under load.",
      "file_hint": null
    },
    {
      "category":  "performance",
      "severity":  "medium",
      "title":     "Enforce a MongoDB document schema at the application layer",
      "detail":    "MongoDB's schema-less nature can lead to inconsistent documents over time. Enforce a schema — Mongoose (Node.js), MongoEngine / Pydantic + Motor (Python), or Spring Data MongoDB validation annotations (Java/Kotlin) — to improve reliability and query performance.",
      "file_hint": null
    },
    {
      "category":  "quality",
      "severity":  "medium",
      "title":     "Add a CI pipeline",
      "detail":    "No CI configuration was detected. A CI pipeline that runs tests and linting on every pull request is one of the highest-ROI investments for long-term code quality.",
      "file_hint": ".github/workflows/ci.yml"
    },
    {
      "category":  "scalability",
      "severity":  "medium",
      "title":     "Tune Kafka consumer group concurrency",
      "detail":    "Kafka is present but default consumer-group parallelism is often left at 1. Match the number of consumers to the partition count to maximise throughput.",
      "file_hint": null
    }
  ],
  "used_fallback": true
}
```

| Field | Type | Notes |
|---|---|---|
| `suggestions` | `Suggestion[]` | 5–8 items (AI path) or 3–8 items (fallback path). Sorted `high → medium → low` |
| `used_fallback` | boolean | `true` if AI was unavailable |

**Error responses**

| Status | Condition |
|---|---|
| 422 | Non-GitHub URL or malformed body |
| 500 | Unexpected server error |

---

## Frontend integration notes

### Typical call sequence

```
POST /analyze   →  receive stack + modules
POST /diagram   →  pass stack + modules from above (ModuleInfo objects accepted directly)
POST /suggestions → pass stack + modules from above
```

### `used_fallback` flag

Every response includes `"used_fallback": true | false`. The frontend should use this to optionally display a subtle indicator (e.g. "Generated with heuristics") so users understand the quality level without it being alarming.

### Diagram rendering

`mermaid_source` is always clean `graph TD` syntax — no fences, no backtick wrappers. Pass it directly to `mermaid.render()` or the Mermaid React component.

`nodes` and `edges` use a flat canonical shape. To render with React Flow, enrich them client-side:

```js
const rfNodes = nodes.map((n, i) => ({
  id: n.id,
  data: { label: n.label },
  position: { x: 250, y: 50 + i * 100 },
  type: i === 0 ? "input" : "default",
}));

const rfEdges = edges.map((e, i) => ({
  id: `e-${i}`,
  source: e.from,
  target: e.to,
  label: e.label || undefined,
  type: "smoothstep",
}));
```

### Module coercion

`/diagram` and `/suggestions` accept `modules` as either `string[]` or the `ModuleInfo[]` array returned by `/analyze`. No transformation needed — pass the response directly:

```js
const analyze = await post("/analyze", { repo_url, branch });
const diagram = await post("/diagram", {
  repo_url,
  stack: analyze.stack,
  modules: analyze.modules,   // ModuleInfo[] — accepted as-is
});
```

---

## Running tests

```bash
# All tests
pytest tests/ -v

# With coverage
pytest tests/ -v --cov=. --cov-report=term-missing

# Specific test files
pytest tests/test_routers.py -v    # router + diagram parser tests
pytest tests/test_fallback.py -v   # fallback logic unit tests
```
