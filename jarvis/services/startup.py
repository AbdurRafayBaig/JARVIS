"""Startup Service

Manages Windows startup registration.
"""

import sys
from pathlib import Path
from typing import Optional
from loguru import logger

from jarvis.core.config import get_settings


class StartupService:
    """Service for managing Windows startup."""

    def __init__(self):
        self._settings = get_settings()

    async def enable(self) -> bool:
        """Enable auto-start on Windows login."""
        try:
            import winreg
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            exe_path = sys.executable
            script_path = Path(__file__).parent.parent.parent / "run.py"

            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
                winreg.SetValueEx(key, "JARVIS", 0, winreg.REG_SZ, f'"{exe_path}" "{script_path}" --minimized')

            logger.info("Auto-start enabled")
            return True
        except Exception as e:
            logger.error(f"Failed to enable auto-start: {e}")
            return False

    async def disable(self) -> bool:
        """Disable auto-start."""
        try:
            import winreg
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"

            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
                try:
                    winreg.DeleteValue(key, "JARVIS")
                except FileNotFoundError:
                    pass

            logger.info("Auto-start disabled")
            return True
        except Exception as e:
            logger.error(f"Failed to disable auto-start: {e}")
            return False

    async def is_enabled(self) -> bool:
        """Check if auto-start is enabled."""
        try:
            import winreg
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"

            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ) as key:
                try:
                    winreg.QueryValueEx(key, "JARVIS")
                    return True
                except FileNotFoundError:
                    return False
        except Exception:
            return False


_startup_service: Optional[StartupService] = None


def get_startup_service() -> StartupService:
    """Get the global startup service instance."""
    global _startup_service
    if _startup_service is None:
        _startup_service = StartupService()
    return _startup_service
