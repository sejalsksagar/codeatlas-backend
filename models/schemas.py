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

# models/schemas.py — add this class
class StackInfo(BaseModel):
    languages: list[str] = []
    frameworks: list[str] = []
    databases: list[str] = []
    infra: list[str] = []
    test_frameworks: list[str] = []
    package_manager: str | None = None

class AnalyzeResponse(BaseModel):
    status: str
    repo: str
    branch: str
    stack: StackInfo | None = None