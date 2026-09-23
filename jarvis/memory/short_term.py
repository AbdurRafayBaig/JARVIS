"""Short-Term Memory

Manages working memory and context window for the agent.
"""

from collections import deque
from typing import Any, Optional
from loguru import logger


class ShortTermMemory:
    """Manages short-term working memory for the agent."""

    def __init__(self, max_items: int = 50, max_tokens: int = 8000):
        self._items: deque[dict[str, Any]] = deque(maxlen=max_items)
        self._max_tokens = max_tokens
        self._current_tokens = 0

    def add(self, role: str, content: str, metadata: Optional[dict] = None) -> None:
        """Add an item to working memory."""
        estimated_tokens = len(content.split()) * 1.3

        while self._current_tokens + estimated_tokens > self._max_tokens and self._items:
            removed = self._items.popleft()
            self._current_tokens -= len(removed.get("content", "").split()) * 1.3

        item = {
            "role": role,
            "content": content,
            "metadata": metadata or {},
        }
        self._items.append(item)
        self._current_tokens += estimated_tokens

    def get_context(self) -> list[dict[str, str]]:
        """Get context as list of messages for LLM."""
        return [
            {"role": item["role"], "content": item["content"]}
            for item in self._items
        ]

    def get_recent(self, count: int = 5) -> list[dict[str, Any]]:
        """Get recent items."""
        items = list(self._items)
        return items[-count:] if count < len(items) else items

    def clear(self) -> None:
        """Clear working memory."""
        self._items.clear()
        self._current_tokens = 0

    def get_stats(self) -> dict[str, Any]:
        """Get memory statistics."""
        return {
            "items": len(self._items),
            "estimated_tokens": int(self._current_tokens),
            "max_tokens": self._max_tokens,
            "utilization": self._current_tokens / self._max_tokens if self._max_tokens > 0 else 0,
        }

    def search(self, query: str) -> list[dict[str, Any]]:
        """Search working memory by content."""
        query_lower = query.lower()
        return [
            item for item in self._items
            if query_lower in item.get("content", "").lower()
        ]


_short_term_memory: Optional[ShortTermMemory] = None


def get_short_term_memory() -> ShortTermMemory:
    """Get the global short-term memory instance."""
    global _short_term_memory
    if _short_term_memory is None:
        _short_term_memory = ShortTermMemory()
    return _short_term_memory
