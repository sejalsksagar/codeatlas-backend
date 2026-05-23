from __future__ import annotations

from core.config import settings


class GitHubModelsClient:
    """
    Client for the GitHub Models inference API.
    Will use settings.GITHUB_MODELS_TOKEN for authentication.
    """

    async def summarise_repo(self, context: dict) -> dict:
        """
        Generate a natural-language summary of a repository.
        Not yet implemented.
        """
        return {"status": "not implemented"}

    async def explain_stack(self, stack: dict) -> dict:
        """
        Produce a human-readable explanation of the detected tech stack.
        Not yet implemented.
        """
        return {"status": "not implemented"}

    async def answer_question(self, context: dict, question: str) -> dict:
        """
        Answer an arbitrary question about the repository.
        Not yet implemented.
        """
        return {"status": "not implemented"}


github_models_client = GitHubModelsClient()
