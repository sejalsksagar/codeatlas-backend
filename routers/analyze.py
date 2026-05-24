from __future__ import annotations

from fastapi import APIRouter

from models.schemas import AnalyzeRequest, AnalyzeResponse, NotImplementedResponse

router = APIRouter(prefix="/analyze", tags=["analyze"])


@router.post("/", response_model=AnalyzeResponse)
async def analyze_repo(body: AnalyzeRequest) -> dict:
    return {
        "status": "ok",
        "repo": body.repo_url,
        "branch": body.branch,
        "stack": {
            "languages": ["Python"],
            "frameworks": ["FastAPI"],
            "databases": ["PostgreSQL"],
            "infra": ["Docker"],
            "test_frameworks": ["pytest"],
            "package_manager": "pip"
        }
    }


@router.get("/stack", response_model=NotImplementedResponse)
async def get_stack(repo_url: str, branch: str = "HEAD") -> dict:
    """
    Return the detected technology stack for a repository.
    Not yet implemented.
    """
    return {"status": "not implemented"}


@router.get("/tree", response_model=NotImplementedResponse)
async def get_tree(repo_url: str, branch: str = "HEAD") -> dict:
    """
    Return the structured file tree for a repository.
    Not yet implemented.
    """
    return {"status": "not implemented"}


@router.post("/ask", response_model=NotImplementedResponse)
async def ask_question(body: AnalyzeRequest) -> dict:
    """
    Answer a natural-language question about a repository.
    Requires body.question to be set.
    Not yet implemented.
    """
    return {"status": "not implemented"}
