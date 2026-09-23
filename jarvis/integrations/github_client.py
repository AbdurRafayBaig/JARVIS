"""GitHub Client

Provides GitHub API integration using httpx.
"""

import httpx
from typing import Optional
from loguru import logger

from jarvis.core.config import get_settings


class GitHubClient:
    """GitHub REST API client."""

    def __init__(self):
        self._settings = get_settings()
        self._token = self._settings.github.token
        self._username = self._settings.github.username
        self._base_url = "https://api.github.com"
        self._client = None

    def _get_client(self) -> httpx.AsyncClient:
        """Get HTTP client with auth."""
        if self._client is None or self._client.is_closed:
            headers = {
                "Accept": "application/vnd.github.v3+json",
            }
            if self._token:
                headers["Authorization"] = f"token {self._token}"

            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                headers=headers,
                timeout=30.0,
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def get_user(self, username: Optional[str] = None) -> dict:
        """Get user information."""
        client = self._get_client()
        user = username or self._username
        response = await client.get(f"/users/{user}")
        response.raise_for_status()
        return response.json()

    async def list_repos(
        self,
        username: Optional[str] = None,
        per_page: int = 30,
        page: int = 1,
    ) -> list[dict]:
        """List repositories for a user."""
        client = self._get_client()
        user = username or self._username
        response = await client.get(
            f"/users/{user}/repos",
            params={"per_page": per_page, "page": page},
        )
        response.raise_for_status()
        return response.json()

    async def get_repo(self, owner: str, repo: str) -> dict:
        """Get repository information."""
        client = self._get_client()
        response = await client.get(f"/repos/{owner}/{repo}")
        response.raise_for_status()
        return response.json()

    async def create_repo(
        self,
        name: str,
        description: Optional[str] = None,
        private: bool = False,
        auto_init: bool = True,
    ) -> dict:
        """Create a new repository."""
        client = self._get_client()
        data = {
            "name": name,
            "private": private,
            "auto_init": auto_init,
        }
        if description:
            data["description"] = description

        response = await client.post("/user/repos", json=data)
        response.raise_for_status()
        return response.json()

    async def list_issues(
        self,
        owner: str,
        repo: str,
        state: str = "open",
        per_page: int = 30,
    ) -> list[dict]:
        """List issues in a repository."""
        client = self._get_client()
        response = await client.get(
            f"/repos/{owner}/{repo}/issues",
            params={"state": state, "per_page": per_page},
        )
        response.raise_for_status()
        return response.json()

    async def create_issue(
        self,
        owner: str,
        repo: str,
        title: str,
        body: Optional[str] = None,
        labels: Optional[list[str]] = None,
    ) -> dict:
        """Create a new issue."""
        client = self._get_client()
        data = {"title": title}
        if body:
            data["body"] = body
        if labels:
            data["labels"] = labels

        response = await client.post(
            f"/repos/{owner}/{repo}/issues",
            json=data,
        )
        response.raise_for_status()
        return response.json()

    async def list_pull_requests(
        self,
        owner: str,
        repo: str,
        state: str = "open",
        per_page: int = 30,
    ) -> list[dict]:
        """List pull requests."""
        client = self._get_client()
        response = await client.get(
            f"/repos/{owner}/{repo}/pulls",
            params={"state": state, "per_page": per_page},
        )
        response.raise_for_status()
        return response.json()

    async def create_pull_request(
        self,
        owner: str,
        repo: str,
        title: str,
        head: str,
        base: str,
        body: Optional[str] = None,
    ) -> dict:
        """Create a pull request."""
        client = self._get_client()
        data = {
            "title": title,
            "head": head,
            "base": base,
        }
        if body:
            data["body"] = body

        response = await client.post(
            f"/repos/{owner}/{repo}/pulls",
            json=data,
        )
        response.raise_for_status()
        return response.json()

    async def get_file_content(
        self,
        owner: str,
        repo: str,
        path: str,
        ref: Optional[str] = None,
    ) -> dict:
        """Get file content from repository."""
        client = self._get_client()
        params = {}
        if ref:
            params["ref"] = ref

        response = await client.get(
            f"/repos/{owner}/{repo}/contents/{path}",
            params=params,
        )
        response.raise_for_status()
        return response.json()

    async def health_check(self) -> bool:
        """Check if GitHub API is accessible."""
        try:
            client = self._get_client()
            response = await client.get("/rate_limit")
            return response.status_code == 200
        except Exception as e:
            logger.error(f"GitHub health check failed: {e}")
            return False


_github_client: Optional[GitHubClient] = None


def get_github_client() -> GitHubClient:
    """Get the global GitHub client instance."""
    global _github_client
    if _github_client is None:
        _github_client = GitHubClient()
    return _github_client
