"""
models/schemas.py
-----------------
Pydantic request/response models for the CodeAtlas API.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, field_validator


# --------------------------------------------------------------------------- #
# Shared sub-models
# --------------------------------------------------------------------------- #


class StackInfo(BaseModel):
    languages: list[str] = []
    frameworks: list[str] = []
    databases: list[str] = []
    infra: list[str] = []
    test_frameworks: list[str] = []
    package_manager: str | None = None


class ModuleInfo(BaseModel):
    name: str
    path: str
    description: str


class Suggestion(BaseModel):
    category: str          # security | performance | scalability | quality
    severity: str          # high | medium | low
    title: str
    detail: str
    file_hint: str | None = None


class DiagramNode(BaseModel):
    id: str
    label: str


class DiagramEdge(BaseModel):
    from_: str = ""        # 'from' is a Python keyword; serialised as 'from'
    to: str = ""
    label: str = ""

    model_config = {"populate_by_name": True}

    @classmethod
    def from_dict(cls, d: dict) -> "DiagramEdge":
        return cls(from_=d.get("from", ""), to=d.get("to", ""), label=d.get("label", ""))


# --------------------------------------------------------------------------- #
# Request schemas
# --------------------------------------------------------------------------- #


class AnalyzeRequest(BaseModel):
    repo_url: str
    branch: str = "HEAD"
    question: str | None = None


def _coerce_modules(modules: list) -> list[str]:
    """Coerce a mixed list of strings / ModuleInfo dicts to plain strings."""
    result = []
    for m in modules:
        if isinstance(m, str):
            result.append(m)
        elif isinstance(m, dict):
            result.append(m.get("path") or m.get("name") or str(m))
        else:
            result.append(str(m))
    return result


class DiagramRequest(BaseModel):
    repo_url: str
    stack: dict[str, Any] = {}
    modules: list[Any] = []   # accepts str OR ModuleInfo dicts from /analyze

    @field_validator("modules", mode="before")
    @classmethod
    def coerce_modules(cls, v: list) -> list[str]:
        return _coerce_modules(v)


class SuggestionsRequest(BaseModel):
    repo_url: str
    stack: dict[str, Any] = {}
    modules: list[Any] = []   # accepts str OR ModuleInfo dicts from /analyze

    @field_validator("modules", mode="before")
    @classmethod
    def coerce_modules(cls, v: list) -> list[str]:
        return _coerce_modules(v)


# --------------------------------------------------------------------------- #
# Response schemas
# --------------------------------------------------------------------------- #


class HealthResponse(BaseModel):
    status: str


class NotImplementedResponse(BaseModel):
    status: str = "not implemented"


class FileTreeResponse(BaseModel):
    tree: dict = {}


class AnalyzeResponse(BaseModel):
    status: str
    repo: str
    branch: str
    stack: StackInfo | None = None
    summary: str | None = None
    modules: list[ModuleInfo] = []
    entry_points: list[str] = []
    request_flow: str | None = None
    used_fallback: bool = False


class DiagramResponse(BaseModel):
    status: str
    repo: str
    mermaid_source: str = ""
    nodes: list[dict] = []
    edges: list[dict] = []
    used_fallback: bool = False


class SuggestionsResponse(BaseModel):
    status: str
    repo: str
    suggestions: list[Suggestion] = []
    used_fallback: bool = False