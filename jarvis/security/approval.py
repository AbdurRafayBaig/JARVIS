"""Approval Manager

Manages tool execution approvals based on risk levels.
"""

import asyncio
from enum import Enum
from typing import Optional, Callable, Any
from loguru import logger

from jarvis.core.config import get_settings


class ApprovalLevel(Enum):
    """Approval levels for tool execution."""
    AUTO = "auto"
    PROMPT = "prompt"
    BLOCK = "block"


class ApprovalManager:
    """Manages tool execution approvals."""

    def __init__(self):
        self._settings = get_settings()
        self._approval_callback: Optional[Callable[[str, str], Any]] = None
        self._always_approve: set[str] = set()
        self._always_block: set[str] = set()

    def set_approval_callback(self, callback: Callable[[str, str], Any]) -> None:
        """Set callback for approval requests."""
        self._approval_callback = callback

    def add_always_approve(self, tool_name: str) -> None:
        """Add tool to always approve list."""
        self._always_approve.add(tool_name)

    def add_always_block(self, tool_name: str) -> None:
        """Add tool to always block list."""
        self._always_block.add(tool_name)

    def get_approval_level(self, risk_level: str) -> ApprovalLevel:
        """Get approval level for a risk level."""
        if risk_level == "SAFE" or risk_level == "safe":
            return ApprovalLevel.AUTO
        elif risk_level == "SENSITIVE" or risk_level == "sensitive":
            return ApprovalLevel.PROMPT if self._settings.security.require_confirmation_sensitive else ApprovalLevel.AUTO
        elif risk_level == "DANGEROUS" or risk_level == "dangerous":
            return ApprovalLevel.BLOCK if self._settings.security.sandbox_mode else ApprovalLevel.PROMPT
        return ApprovalLevel.PROMPT

    async def request_approval(
        self,
        tool_name: str,
        tool_args: dict,
        risk_level: str,
    ) -> bool:
        """Request approval for tool execution."""
        if tool_name in self._always_approve:
            return True

        if tool_name in self._always_block:
            return False

        level = self.get_approval_level(risk_level)

        if level == ApprovalLevel.AUTO:
            return True

        if level == ApprovalLevel.BLOCK:
            logger.warning(f"Tool blocked: {tool_name}")
            return False

        if self._approval_callback:
            try:
                result = await self._approval_callback(tool_name, str(tool_args))
                return result
            except Exception as e:
                logger.error(f"Approval callback failed: {e}")
                return False

        logger.warning(f"No approval callback set, defaulting to deny: {tool_name}")
        return False


_approval_manager: Optional[ApprovalManager] = None


def get_approval_manager() -> ApprovalManager:
    """Get the global approval manager instance."""
    global _approval_manager
    if _approval_manager is None:
        _approval_manager = ApprovalManager()
    return _approval_manager
