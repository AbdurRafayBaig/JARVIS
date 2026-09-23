"""Browser Engine

Manages Playwright browser lifecycle.
"""

from typing import Optional
from loguru import logger

from jarvis.core.config import get_settings


class BrowserEngine:
    """Manages Playwright browser instances."""

    def __init__(self):
        self._settings = get_settings()
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None

    async def start(self, headless: bool = True) -> None:
        """Start the browser engine."""
        if self._browser:
            return

        try:
            from playwright.async_api import async_playwright

            self._playwright = await async_playwright().start()

            browser_type = self._settings.browser.browser_type

            if browser_type == "chromium":
                self._browser = await self._playwright.chromium.launch(headless=headless)
            elif browser_type == "firefox":
                self._browser = await self._playwright.firefox.launch(headless=headless)
            elif browser_type == "webkit":
                self._browser = await self._playwright.webkit.launch(headless=headless)
            else:
                self._browser = await self._playwright.chromium.launch(headless=headless)

            self._context = await self._browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            )

            self._page = await self._context.new_page()

            logger.info(f"Browser engine started: {browser_type}")

        except Exception as e:
            logger.error(f"Failed to start browser: {e}")
            raise

    async def stop(self) -> None:
        """Stop the browser engine."""
        if self._page:
            await self._page.close()
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

        self._page = None
        self._context = None
        self._browser = None
        self._playwright = None

        logger.info("Browser engine stopped")

    async def new_page(self):
        """Create a new page."""
        if not self._context:
            raise RuntimeError("Browser not started")
        return await self._context.new_page()

    @property
    def page(self):
        """Get current page."""
        return self._page

    @property
    def context(self):
        """Get browser context."""
        return self._context

    @property
    def is_running(self) -> bool:
        """Check if browser is running."""
        return self._browser is not None


_browser_engine: Optional[BrowserEngine] = None


def get_browser_engine() -> BrowserEngine:
    """Get the global browser engine instance."""
    global _browser_engine
    if _browser_engine is None:
        _browser_engine = BrowserEngine()
    return _browser_engine
