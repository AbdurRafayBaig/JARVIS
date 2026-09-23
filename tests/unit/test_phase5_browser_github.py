"""JARVIS - Phase 5 Browser & GitHub Integration Tests"""

import pytest
from unittest.mock import AsyncMock, patch

from jarvis.tools.browser import (
    NavigateTool,
    ClickElementTool,
    TypeTextTool,
    GetPageContentTool,
    GetLinksTool,
    ScreenshotTool,
    ScrollTool,
)

from jarvis.tools.github import (
    CreateRepoTool,
    ListReposTool,
    ListIssuesTool,
    CreateIssueTool,
    CreatePRTool,
)


@pytest.mark.asyncio
async def test_browser_navigate_tool():
    tool = NavigateTool()
    with patch("jarvis.browser.navigator.Navigator.goto", new_callable=AsyncMock) as mock_goto:
        mock_goto.return_value = True
        result = await tool.execute(url="https://example.com")
        assert result.success is True
        assert "Navigated to" in result.data


@pytest.mark.asyncio
async def test_browser_click_tool():
    tool = ClickElementTool()
    with patch("jarvis.browser.interactor.Interactor.click", new_callable=AsyncMock) as mock_click:
        mock_click.return_value = True
        result = await tool.execute(selector="#btn")
        assert result.success is True


@pytest.mark.asyncio
async def test_github_list_repos_tool():
    tool = ListReposTool()
    with patch("jarvis.integrations.github_client.GitHubClient.list_repos", new_callable=AsyncMock) as mock_list:
        mock_list.return_value = [{"name": "repo1"}, {"name": "repo2"}]
        result = await tool.execute(username="octocat")
        assert result.success is True
        assert result.data["count"] == 2
        assert "repo1" in result.data["repositories"]


@pytest.mark.asyncio
async def test_github_create_issue_tool():
    tool = CreateIssueTool()
    with patch("jarvis.integrations.github_client.GitHubClient.create_issue", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = {"number": 42, "html_url": "https://github.com/owner/repo/issues/42"}
        result = await tool.execute(owner="owner", repo="repo", title="Test Issue")
        assert result.success is True
        assert result.data["issue_number"] == 42
