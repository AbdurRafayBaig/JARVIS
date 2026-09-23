"""Scraper

Extracts content from web pages using BeautifulSoup.
"""

from typing import Optional
from loguru import logger

from jarvis.browser.engine import get_browser_engine


class Scraper:
    """Scrapes content from web pages."""

    def __init__(self):
        self._engine = get_browser_engine()

    async def get_text(self, selector: Optional[str] = None) -> str:
        """Get text content from page."""
        try:
            page = self._engine.page
            if not page:
                return ""

            if selector:
                element = await page.query_selector(selector)
                if element:
                    return await element.text_content() or ""
                return ""

            return await page.text_content("body") or ""

        except Exception as e:
            logger.error(f"Get text failed: {e}")
            return ""

    async def get_html(self, selector: Optional[str] = None) -> str:
        """Get HTML content from page."""
        try:
            page = self._engine.page
            if not page:
                return ""

            if selector:
                return await page.inner_html(selector)
            else:
                return await page.content()

        except Exception as e:
            logger.error(f"Get HTML failed: {e}")
            return ""

    async def get_links(self) -> list[dict[str, str]]:
        """Get all links from page."""
        try:
            page = self._engine.page
            if not page:
                return []

            links = await page.evaluate("""
                () => {
                    return Array.from(document.querySelectorAll('a')).map(a => ({
                        text: a.textContent.trim(),
                        href: a.href,
                    })).filter(l => l.href);
                }
            """)

            return links

        except Exception as e:
            logger.error(f"Get links failed: {e}")
            return []

    async def get_images(self) -> list[dict[str, str]]:
        """Get all images from page."""
        try:
            page = self._engine.page
            if not page:
                return []

            images = await page.evaluate("""
                () => {
                    return Array.from(document.querySelectorAll('img')).map(img => ({
                        alt: img.alt,
                        src: img.src,
                        width: img.width,
                        height: img.height,
                    }));
                }
            """)

            return images

        except Exception as e:
            logger.error(f"Get images failed: {e}")
            return []

    async def get_table(self, selector: str) -> list[list[str]]:
        """Extract table data."""
        try:
            page = self._engine.page
            if not page:
                return []

            table_data = await page.evaluate("""
                (selector) => {
                    const table = document.querySelector(selector);
                    if (!table) return [];

                    const rows = Array.from(table.querySelectorAll('tr'));
                    return rows.map(row => {
                        const cells = Array.from(row.querySelectorAll('th, td'));
                        return cells.map(cell => cell.textContent.trim());
                    });
                }
            """, selector)

            return table_data

        except Exception as e:
            logger.error(f"Get table failed: {e}")
            return []

    async def search_text(self, query: str) -> list[dict]:
        """Search for text in page."""
        try:
            page = self._engine.page
            if not page:
                return []

            results = await page.evaluate("""
                (query) => {
                    const results = [];
                    const walker = document.createTreeWalker(
                        document.body,
                        NodeFilter.SHOW_TEXT,
                        null,
                        false
                    );

                    while (walker.nextNode()) {
                        const node = walker.currentNode;
                        if (node.textContent.toLowerCase().includes(query.toLowerCase())) {
                            results.push({
                                text: node.textContent.trim(),
                                parent: node.parentElement?.tagName || 'unknown',
                            });
                        }
                    }

                    return results;
                }
            """, query)

            return results

        except Exception as e:
            logger.error(f"Search text failed: {e}")
            return []
