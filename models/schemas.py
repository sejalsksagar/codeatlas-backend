from __future__ import annotations

from pydantic import BaseModel, HttpUrl


# ------------------------------------------------------------------ #
# Request schemas
# ------------------------------------------------------------------ #


class AnalyzeRequest(BaseModel):
    repo_url: str
    branch: str = "HEAD"
    question: str | None = None


# ------------------------------------------------------------------ #
# Response schemas
# ------------------------------------------------------------------ #


class HealthResponse(BaseModel):
    status: str


class NotImplementedResponse(BaseModel):
    status: str = "not implemented"


class StackInfo(BaseModel):
    languages: list[str] = []
    frameworks: list[str] = []
    tools: list[str] = []


class FileTreeResponse(BaseModel):
    tree: dict = {}


class AnalyzeResponse(BaseModel):
    repo: str
    branch: str
    stack: StackInfo | None = None
    file_tree: FileTreeResponse | None = None
    summary: str | None = None
    status: str = "not implemented"
