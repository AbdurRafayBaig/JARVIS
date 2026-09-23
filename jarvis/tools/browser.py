"""Browser Tools

Registers browser automation tools with the tool registry.
"""

from typing import Any, Optional
from loguru import logger

from jarvis.agent.tools import BaseTool, ToolResult, ToolRiskLevel, get_registry


class NavigateTool(BaseTool):
    """Navigate to a URL."""

    @property
    def name(self) -> str:
        return "browser_navigate"

    @property
    def description(self) -> str:
        return "Navigate to a URL in the browser"

    @property
    def risk_level(self) -> ToolRiskLevel:
        return ToolRiskLevel.SENSITIVE

    async def execute(self, url: str, **kwargs) -> ToolResult:
        try:
            from jarvis.browser.navigator import Navigator
            navigator = Navigator()
            success = await navigator.goto(url)
            if success:
                return ToolResult(success=True, data=f"Navigated to {url}")
            return ToolResult(success=False, error=f"Failed to navigate to {url}")
        except Exception as e:
            logger.error(f"Browser navigate error: {e}")
            return ToolResult(success=False, error=str(e))


class ClickElementTool(BaseTool):
    """Click an element on the page."""

    @property
    def name(self) -> str:
        return "browser_click"

    @property
    def description(self) -> str:
        return "Click an element by CSS selector"

    @property
    def risk_level(self) -> ToolRiskLevel:
        return ToolRiskLevel.SAFE

    async def execute(self, selector: str, **kwargs) -> ToolResult:
        try:
            from jarvis.browser.interactor import Interactor
            interactor = Interactor()
            success = await interactor.click(selector)
            if success:
                return ToolResult(success=True, data=f"Clicked {selector}")
            return ToolResult(success=False, error=f"Failed to click {selector}")
        except Exception as e:
            logger.error(f"Browser click error: {e}")
            return ToolResult(success=False, error=str(e))


class TypeTextTool(BaseTool):
    """Type text into an element."""

    @property
    def name(self) -> str:
        return "browser_type"

    @property
    def description(self) -> str:
        return "Type text into an input field"

    @property
    def risk_level(self) -> ToolRiskLevel:
        return ToolRiskLevel.SAFE

    async def execute(self, selector: str, text: str, **kwargs) -> ToolResult:
        try:
            from jarvis.browser.interactor import Interactor
            interactor = Interactor()
            success = await interactor.type_text(selector, text)
            if success:
                return ToolResult(success=True, data=f"Typed text into {selector}")
            return ToolResult(success=False, error=f"Failed to type into {selector}")
        except Exception as e:
            logger.error(f"Browser type error: {e}")
            return ToolResult(success=False, error=str(e))


class GetPageContentTool(BaseTool):
    """Get text content from the page."""

    @property
    def name(self) -> str:
        return "browser_get_content"

    @property
    def description(self) -> str:
        return "Get text content from the current page"

    @property
    def risk_level(self) -> ToolRiskLevel:
        return ToolRiskLevel.SAFE

    async def execute(self, selector: Optional[str] = None, **kwargs) -> ToolResult:
        try:
            from jarvis.browser.scraping import Scraper
            scraper = Scraper()
            content = await scraper.get_text(selector)
            return ToolResult(success=True, data={"content": content})
        except Exception as e:
            logger.error(f"Browser get content error: {e}")
            return ToolResult(success=False, error=str(e))


class GetLinksTool(BaseTool):
    """Get all links from the page."""

    @property
    def name(self) -> str:
        return "browser_get_links"

    @property
    def description(self) -> str:
        return "Get all links from the current page"

    @property
    def risk_level(self) -> ToolRiskLevel:
        return ToolRiskLevel.SAFE

    async def execute(self, **kwargs) -> ToolResult:
        try:
            from jarvis.browser.scraping import Scraper
            scraper = Scraper()
            links = await scraper.get_links()
            return ToolResult(success=True, data={"links": links, "count": len(links)})
        except Exception as e:
            logger.error(f"Browser get links error: {e}")
            return ToolResult(success=False, error=str(e))


class ScreenshotTool(BaseTool):
    """Take a screenshot of the page."""

    @property
    def name(self) -> str:
        return "browser_screenshot"

    @property
    def description(self) -> str:
        return "Take a screenshot of the current page"

    @property
    def risk_level(self) -> ToolRiskLevel:
        return ToolRiskLevel.SAFE

    async def execute(self, path: Optional[str] = None, **kwargs) -> ToolResult:
        try:
            from jarvis.browser.interactor import Interactor
            interactor = Interactor()
            screenshot = await interactor.screenshot(path)
            return ToolResult(success=True, data={"path": str(screenshot)})
        except Exception as e:
            logger.error(f"Browser screenshot error: {e}")
            return ToolResult(success=False, error=str(e))


class ScrollTool(BaseTool):
    """Scroll the page."""

    @property
    def name(self) -> str:
        return "browser_scroll"

    @property
    def description(self) -> str:
        return "Scroll the page up or down"

    @property
    def risk_level(self) -> ToolRiskLevel:
        return ToolRiskLevel.SAFE

    async def execute(self, direction: str = "down", amount: int = 500, **kwargs) -> ToolResult:
        try:
            from jarvis.browser.interactor import Interactor
            interactor = Interactor()
            success = await interactor.scroll(direction, amount)
            if success:
                return ToolResult(success=True, data=f"Scrolled {direction} by {amount}px")
            return ToolResult(success=False, error=f"Failed to scroll {direction}")
        except Exception as e:
            logger.error(f"Browser scroll error: {e}")
            return ToolResult(success=False, error=str(e))


def register_browser_tools():
    """Register browser tools."""
    get_registry().register(NavigateTool(), category="browser")
    get_registry().register(ClickElementTool(), category="browser")
    get_registry().register(TypeTextTool(), category="browser")
def register_browser_tools() -> None:
    """Register all browser tools."""
    registry = get_registry()

    tools = [
        NavigateTool(),
        ClickElementTool(),
        TypeTextTool(),
        GetPageContentTool(),
        GetLinksTool(),
        ScreenshotTool(),
        ScrollTool(),
    ]

    for tool in tools:
        registry.register(tool)

    logger.info(f"Registered {len(tools)} browser tools")
