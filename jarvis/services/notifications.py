"""Notification Service

Provides toast notification functionality.
"""

import sys
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Callable, Any
from datetime import datetime
from loguru import logger


class NotificationLevel(Enum):
    """Notification levels."""
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"


@dataclass
class Notification:
    """Notification data."""
    title: str
    message: str
    level: NotificationLevel = NotificationLevel.INFO
    duration: int = 5000
    callback: Optional[Callable[[], Any]] = None
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class NotificationService:
    """Service for sending notifications."""

    def __init__(self):
        self._notifications: list[Notification] = []
        self._max_notifications = 100

    async def send(
        self,
        title: str,
        message: str,
        level: NotificationLevel = NotificationLevel.INFO,
        duration: int = 5000,
        callback: Optional[Callable[[], Any]] = None,
    ) -> Notification:
        """Send a notification."""
        notification = Notification(
            title=title,
            message=message,
            level=level,
            duration=duration,
            callback=callback,
        )

        self._notifications.append(notification)

        if len(self._notifications) > self._max_notifications:
            self._notifications = self._notifications[-self._max_notifications:]

        logger.debug(f"Notification: [{level.value}] {title}: {message}")
        return notification

    async def info(self, title: str, message: str, **kwargs) -> Notification:
        """Send an info notification."""
        return await self.send(title, message, NotificationLevel.INFO, **kwargs)

    async def success(self, title: str, message: str, **kwargs) -> Notification:
        """Send a success notification."""
        return await self.send(title, message, NotificationLevel.SUCCESS, **kwargs)

    async def warning(self, title: str, message: str, **kwargs) -> Notification:
        """Send a warning notification."""
        return await self.send(title, message, NotificationLevel.WARNING, **kwargs)

    async def error(self, title: str, message: str, **kwargs) -> Notification:
        """Send an error notification."""
        return await self.send(title, message, NotificationLevel.ERROR, **kwargs)

    def get_recent(self, count: int = 10) -> list[Notification]:
        """Get recent notifications."""
        return self._notifications[-count:]

    def clear(self) -> None:
        """Clear all notifications."""
        self._notifications.clear()


_notification_service: Optional[NotificationService] = None


def get_notification_service() -> NotificationService:
    """Get the global notification service instance."""
    global _notification_service
    if _notification_service is None:
        _notification_service = NotificationService()
    return _notification_service
