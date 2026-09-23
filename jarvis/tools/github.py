"""GitHub Tools

Registers GitHub integration tools with the tool registry.
"""

from typing import Optional
from loguru import logger

from jarvis.agent.tools import BaseTool, ToolResult, ToolRiskLevel, get_registry


class CreateRepoTool(BaseTool):
    """Create a GitHub repository."""

    @property
    def name(self) -> str:
        return "github_create_repo"

    @property
    def description(self) -> str:
        return "Create a new GitHub repository"

    @property
    def risk_level(self) -> ToolRiskLevel:
        return ToolRiskLevel.SENSITIVE

    async def execute(self, name: str, description: Optional[str] = None, private: bool = False, **kwargs) -> ToolResult:
        """Create a GitHub repository.

        Args:
            name: Name for the new repository.
            description: Short description shown on the repository page.
            private: Create it private rather than public.
        """
        try:
            from jarvis.integrations.github_client import get_github_client
            client = get_github_client()
            repo = await client.create_repo(name, description, private)
            return ToolResult(success=True, data={"url": repo.get("html_url", ""), "repo": repo})
        except Exception as e:
            logger.error(f"GitHub create repo error: {e}")
            return ToolResult(success=False, error=str(e))


class ListReposTool(BaseTool):
    """List GitHub repositories."""

    @property
    def name(self) -> str:
        return "github_list_repos"

    @property
    def description(self) -> str:
        return "List GitHub repositories for a user"

    @property
    def risk_level(self) -> ToolRiskLevel:
        return ToolRiskLevel.SAFE

    async def execute(self, username: Optional[str] = None, **kwargs) -> ToolResult:
        """List GitHub repositories.

        Args:
            username: Account whose repositories to list. Omit for the authenticated
                user.
        """
        try:
            from jarvis.integrations.github_client import get_github_client
            client = get_github_client()
            repos = await client.list_repos(username)
            names = [r.get("name", "") for r in repos] if isinstance(repos, list) else []
            return ToolResult(success=True, data={"repositories": names, "count": len(names)})
        except Exception as e:
            logger.error(f"GitHub list repos error: {e}")
            return ToolResult(success=False, error=str(e))


class ListIssuesTool(BaseTool):
    """List issues in a repository."""

    @property
    def name(self) -> str:
        return "github_list_issues"

    @property
    def description(self) -> str:
        return "List issues in a GitHub repository"

    @property
    def risk_level(self) -> ToolRiskLevel:
        return ToolRiskLevel.SAFE

    async def execute(self, owner: str, repo: str, state: str = "open", **kwargs) -> ToolResult:
        """List issues in a repository.

        Args:
            owner: Repository owner, a user or organisation.
            repo: Repository name.
            state: Which issues to return: open, closed, or all.
        """
        try:
            from jarvis.integrations.github_client import get_github_client
            client = get_github_client()
            issues = await client.list_issues(owner, repo, state)
            simplified = [{"number": i["number"], "title": i["title"]} for i in issues] if isinstance(issues, list) else []
            return ToolResult(success=True, data={"issues": simplified, "count": len(simplified)})
        except Exception as e:
            logger.error(f"GitHub list issues error: {e}")
            return ToolResult(success=False, error=str(e))


class CreateIssueTool(BaseTool):
    """Create a GitHub issue."""

    @property
    def name(self) -> str:
        return "github_create_issue"

    @property
    def description(self) -> str:
        return "Create a new issue in a GitHub repository"

    @property
    def risk_level(self) -> ToolRiskLevel:
        return ToolRiskLevel.SENSITIVE

    async def execute(self, owner: str, repo: str, title: str, body: Optional[str] = None, **kwargs) -> ToolResult:
        """Create a GitHub issue.

        Args:
            owner: Repository owner, a user or organisation.
            repo: Repository name.
            title: Issue title.
            body: Issue body in Markdown.
        """
        try:
            from jarvis.integrations.github_client import get_github_client
            client = get_github_client()
            issue = await client.create_issue(owner, repo, title, body)
            return ToolResult(success=True, data={"issue_number": issue.get("number"), "url": issue.get("html_url")})
        except Exception as e:
            logger.error(f"GitHub create issue error: {e}")
            return ToolResult(success=False, error=str(e))


class CreatePRTool(BaseTool):
    """Create a pull request."""

    @property
    def name(self) -> str:
        return "github_create_pr"

    @property
    def description(self) -> str:
        return "Create a pull request"

    @property
    def risk_level(self) -> ToolRiskLevel:
        return ToolRiskLevel.DANGEROUS

    async def execute(
        self,
        owner: str,
        repo: str,
        title: str,
        head: str,
        base: str,
        body: Optional[str] = None,
        **kwargs,
    ) -> ToolResult:
        """Create a pull request.

        Args:
            owner: Repository owner, a user or organisation.
            repo: Repository name.
            title: Pull request title.
            head: Branch containing the changes.
            base: Branch to merge into, such as main.
            body: Pull request description in Markdown.
        """
        try:
            from jarvis.integrations.github_client import get_github_client
            client = get_github_client()
            pr = await client.create_pull_request(owner, repo, title, head, base, body)
            return ToolResult(success=True, data={"pr_number": pr.get("number"), "url": pr.get("html_url")})
        except Exception as e:
            logger.error(f"GitHub create PR error: {e}")
            return ToolResult(success=False, error=str(e))


def register_github_tools() -> None:
    """Register all GitHub tools."""
    registry = get_registry()

    tools = [
        CreateRepoTool(),
        ListReposTool(),
        ListIssuesTool(),
        CreateIssueTool(),
        CreatePRTool(),
    ]

    for tool in tools:
        registry.register(tool, category="general")

    logger.info(f"Registered {len(tools)} GitHub tools")

