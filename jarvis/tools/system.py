"""JARVIS Tools - System & Response Tools

These are fundamental tools the agent uses for conversational responses
and system information gathering.
"""

import os
import platform
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import psutil

from jarvis.agent.tools import BaseTool, ToolResult, ToolRiskLevel, register_tool
from jarvis.core.logging import get_logger

logger = get_logger(__name__)


class RespondTool(BaseTool):
    """Respond to the user with a message.
    
    Use this tool when the user's request is conversational and doesn't
    require any system action (e.g., greetings, explanations, questions).
    """

    @property
    def name(self) -> str:
        return "respond"

    @property
    def description(self) -> str:
        return (
            "Send a conversational response to the user. Use this when no "
            "system action is needed — for greetings, explanations, questions, "
            "or general conversation."
        )

    @property
    def risk_level(self) -> ToolRiskLevel:
        return ToolRiskLevel.SAFE

    async def execute(self, message: str) -> ToolResult:
        """Send a response to the user.

        Args:
            message: The message to say to the user.
        """
        return ToolResult(success=True, data=message)


class GetSystemInfoTool(BaseTool):
    """Get system information for context."""

    @property
    def name(self) -> str:
        return "get_system_info"

    @property
    def description(self) -> str:
        return (
            "Get current system information including OS, time, working directory, "
            "CPU/RAM usage, and active processes. Useful for answering questions "
            "about the current system state."
        )

    @property
    def risk_level(self) -> ToolRiskLevel:
        return ToolRiskLevel.SAFE

    async def execute(self) -> ToolResult:
        """Get system information."""
        try:
            info = {
                "os": platform.system(),
                "os_version": platform.version(),
                "machine": platform.machine(),
                "hostname": platform.node(),
                "username": os.getenv("USERNAME", os.getenv("USER", "unknown")),
                "current_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "working_directory": os.getcwd(),
                "home_directory": str(Path.home()),
                "cpu_count": psutil.cpu_count(),
                "cpu_percent": psutil.cpu_percent(interval=0.1),
                "memory_total_gb": round(psutil.virtual_memory().total / (1024**3), 1),
                "memory_used_percent": psutil.virtual_memory().percent,
                "disk_usage_percent": psutil.disk_usage("/").percent if platform.system() != "Windows" else psutil.disk_usage("C:\\").percent,
            }
            return ToolResult(success=True, data=info)
        except Exception as e:
            logger.error(f"Failed to get system info: {e}")
            return ToolResult(success=False, error=str(e))


class GetCurrentTimeTool(BaseTool):
    """Get the current date and time."""

    @property
    def name(self) -> str:
        return "get_current_time"

    @property
    def description(self) -> str:
        return "Get the current date and time."

    @property
    def risk_level(self) -> ToolRiskLevel:
        return ToolRiskLevel.SAFE

    async def execute(self) -> ToolResult:
        """Get current time."""
        now = datetime.now()
        return ToolResult(
            success=True,
            data={
                "datetime": now.strftime("%Y-%m-%d %H:%M:%S"),
                "date": now.strftime("%Y-%m-%d"),
                "time": now.strftime("%H:%M:%S"),
                "day_of_week": now.strftime("%A"),
                "timezone": str(datetime.now().astimezone().tzinfo),
            },
        )


def register_system_tools() -> None:
    """Register system tools."""
    register_tool(RespondTool(), category="system")
    register_tool(GetSystemInfoTool(), category="system")
    register_tool(GetCurrentTimeTool(), category="system")
