"""Interactor

Handles DOM interaction: click, type, scroll, select.
"""

from typing import Optional
from loguru import logger

from jarvis.browser.engine import get_browser_engine


class Interactor:
    """Interacts with web page elements."""

    def __init__(self):
        self._engine = get_browser_engine()

    async def click(self, selector: str, timeout: int = 5000) -> bool:
        """Click an element by selector."""
        try:
            page = self._engine.page
            if page:
                await page.click(selector, timeout=timeout)
                logger.debug(f"Clicked: {selector}")
                return True
            return False
        except Exception as e:
            logger.error(f"Click failed: {e}")
            return False

    async def type_text(
        self,
        selector: str,
        text: str,
        delay: int = 0,
    ) -> bool:
        """Type text into an element."""
        try:
            page = self._engine.page
            if page:
                await page.fill(selector, text, timeout=5000)
                logger.debug(f"Typed into: {selector}")
                return True
            return False
        except Exception as e:
            logger.error(f"Type failed: {e}")
            return False

    async def scroll(self, direction: str = "down", amount: int = 500) -> bool:
        """Scroll the page."""
        try:
            page = self._engine.page
            if page:
                if direction == "down":
                    await page.mouse.wheel(0, amount)
                elif direction == "up":
                    await page.mouse.wheel(0, -amount)
                elif direction == "right":
                    await page.mouse.wheel(amount, 0)
                elif direction == "left":
                    await page.mouse.wheel(-amount, 0)

                logger.debug(f"Scrolled {direction}: {amount}")
                return True
            return False
        except Exception as e:
            logger.error(f"Scroll failed: {e}")
            return False

    async def select_option(self, selector: str, value: str) -> bool:
        """Select an option from a dropdown."""
        try:
            page = self._engine.page
            if page:
                await page.select_option(selector, value)
                logger.debug(f"Selected: {value} in {selector}")
                return True
            return False
        except Exception as e:
            logger.error(f"Select failed: {e}")
            return False

    async def check(self, selector: str) -> bool:
        """Check a checkbox."""
        try:
            page = self._engine.page
            if page:
                await page.check(selector)
                logger.debug(f"Checked: {selector}")
                return True
            return False
        except Exception as e:
            logger.error(f"Check failed: {e}")
            return False

    async def uncheck(self, selector: str) -> bool:
        """Uncheck a checkbox."""
        try:
            page = self._engine.page
            if page:
                await page.uncheck(selector)
                logger.debug(f"Unchecked: {selector}")
                return True
            return False
        except Exception as e:
            logger.error(f"Uncheck failed: {e}")
            return False

    async def hover(self, selector: str) -> bool:
        """Hover over an element."""
        try:
            page = self._engine.page
            if page:
                await page.hover(selector)
                logger.debug(f"Hovered: {selector}")
                return True
            return False
        except Exception as e:
            logger.error(f"Hover failed: {e}")
            return False

    async def focus(self, selector: str) -> bool:
        """Focus on an element."""
        try:
            page = self._engine.page
            if page:
                await page.focus(selector)
                logger.debug(f"Focused: {selector}")
                return True
            return False
        except Exception as e:
            logger.error(f"Focus failed: {e}")
            return False

    async def press_key(self, key: str) -> bool:
        """Press a keyboard key."""
        try:
            page = self._engine.page
            if page:
                await page.keyboard.press(key)
                logger.debug(f"Pressed key: {key}")
                return True
            return False
        except Exception as e:
            logger.error(f"Key press failed: {e}")
            return False

    async def screenshot(self, path: Optional[str] = None) -> Optional[bytes]:
        """Take a screenshot of the page."""
        try:
            page = self._engine.page
            if page:
                if path:
                    await page.screenshot(path=path)
                    logger.debug(f"Screenshot saved: {path}")
                else:
                    return await page.screenshot()
            return None
        except Exception as e:
            logger.error(f"Screenshot failed: {e}")
            return None
