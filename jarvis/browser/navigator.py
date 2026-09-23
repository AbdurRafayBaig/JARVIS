"""Navigator

Handles URL navigation and page loading.
"""

from typing import Optional
from loguru import logger

from jarvis.browser.engine import get_browser_engine


class Navigator:
    """Navigates to URLs and manages page loading."""

    def __init__(self):
        self._engine = get_browser_engine()

    async def goto(self, url: str, wait_until: str = "load") -> bool:
        """Navigate to a URL."""
        try:
            page = self._engine.page
            if not page:
                await self._engine.start(headless=True)
                page = self._engine.page

            response = await page.goto(url, wait_until=wait_until)

            if response and response.ok:
                logger.info(f"Navigated to: {url}")
                return True
            else:
                logger.warning(f"Navigation failed: {url} (status: {response.status if response else 'None'})")
                return False

        except Exception as e:
            logger.error(f"Navigation error: {e}")
            return False

    async def wait_for_load(self, timeout: int = 30000) -> bool:
        """Wait for page to finish loading."""
        try:
            page = self._engine.page
            if page:
                await page.wait_for_load_state("networkidle", timeout=timeout)
                return True
            return False
        except Exception as e:
            logger.warning(f"Wait for load failed: {e}")
            return False

    async def reload(self) -> bool:
        """Reload current page."""
        try:
            page = self._engine.page
            if page:
                await page.reload()
                logger.info("Page reloaded")
                return True
            return False
        except Exception as e:
            logger.error(f"Reload failed: {e}")
            return False

    async def go_back(self) -> bool:
        """Navigate back."""
        try:
            page = self._engine.page
            if page:
                await page.go_back()
                logger.info("Navigated back")
                return True
            return False
        except Exception as e:
            logger.error(f"Go back failed: {e}")
            return False

    async def go_forward(self) -> bool:
        """Navigate forward."""
        try:
            page = self._engine.page
            if page:
                await page.go_forward()
                logger.info("Navigated forward")
                return True
            return False
        except Exception as e:
            logger.error(f"Go forward failed: {e}")
            return False

    async def get_url(self) -> Optional[str]:
        """Get current URL."""
        try:
            page = self._engine.page
            if page:
                return page.url
            return None
        except Exception:
            return None

    async def get_title(self) -> Optional[str]:
        """Get current page title."""
        try:
            page = self._engine.page
            if page:
                return await page.title()
            return None
        except Exception:
            return None
