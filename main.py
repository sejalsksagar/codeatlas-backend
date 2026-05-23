from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings
from core.github_client import github_client
from models.schemas import HealthResponse
from routers import analyze


# ------------------------------------------------------------------ #
# Lifespan: startup / shutdown hooks
# ------------------------------------------------------------------ #


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Startup
    yield
    # Shutdown — close persistent HTTP clients
    await github_client.close()


# ------------------------------------------------------------------ #
# App factory
# ------------------------------------------------------------------ #


app = FastAPI(
    title="CodeAtlas API",
    description="AI-powered GitHub repository analysis backend.",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(analyze.router)


# ------------------------------------------------------------------ #
# Core endpoints
# ------------------------------------------------------------------ #


@app.get("/health", response_model=HealthResponse, tags=["health"])
async def health() -> dict:
    """Liveness probe."""
    return {"status": "ok"}


# ------------------------------------------------------------------ #
# Dev entrypoint
# ------------------------------------------------------------------ #

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)