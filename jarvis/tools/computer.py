"""JARVIS Tools - Computer Tools"""

import asyncio
import subprocess
import os
import shutil
from pathlib import Path
from typing import Any, Optional

from jarvis.agent.tools import BaseTool, ToolResult, ToolRiskLevel, register_tool
from jarvis.core.logging import get_logger
from jarvis.core.config import get_settings

logger = get_logger(__name__)


class OpenApplicationTool(BaseTool):
    """Open a Windows application."""

    @property
    def name(self) -> str:
        return "open_application"

    @property
    def description(self) -> str:
        return "Open a Windows application by name"

    @property
    def risk_level(self) -> ToolRiskLevel:
        return ToolRiskLevel.SAFE

    async def execute(self, app_name: str) -> ToolResult:
        """Open an application.

        Args:
            app_name: Application to open: a friendly name ('vscode', 'chrome',
                'notepad'), an executable name, or a full path.
        """
        try:
            # Common application mappings
            app_map = {
                "vscode": "code",
                "visual studio code": "code",
                "chrome": "chrome",
                "google chrome": "chrome",
                "firefox": "firefox",
                "edge": "msedge",
                "notepad": "notepad",
                "terminal": "wt",
                "windows terminal": "wt",
                "powershell": "powershell",
                "cmd": "cmd",
                "explorer": "explorer",
                "file explorer": "explorer",
                "settings": "ms-settings:",
                "calculator": "calc",
                "paint": "mspaint",
                "word": "winword",
                "excel": "excel",
                "powerpoint": "powerpnt",
            }

            cmd = app_map.get(app_name.lower(), app_name)

            if cmd == "ms-settings:":
                await asyncio.create_subprocess_exec("start", cmd, shell=True)
            else:
                await asyncio.create_subprocess_exec(cmd)

            return ToolResult(success=True, data=f"Opened {app_name}")
        except Exception as e:
            logger.error(f"Failed to open {app_name}: {e}")
            return ToolResult(success=False, error=str(e))


class CloseApplicationTool(BaseTool):
    """Close a Windows application."""

    @property
    def name(self) -> str:
        return "close_application"

    @property
    def description(self) -> str:
        return "Close a Windows application by name"

    @property
    def risk_level(self) -> ToolRiskLevel:
        return ToolRiskLevel.SENSITIVE

    async def execute(self, app_name: str) -> ToolResult:
        """Close an application.

        Args:
            app_name: Name of the application process to close, without '.exe'.
        """
        try:
            # Use taskkill
            proc = await asyncio.create_subprocess_exec(
                "taskkill", "/IM", f"{app_name}.exe", "/F",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()

            if proc.returncode == 0:
                return ToolResult(success=True, data=f"Closed {app_name}")
            else:
                return ToolResult(success=False, error=stderr.decode())
        except Exception as e:
            logger.error(f"Failed to close {app_name}: {e}")
            return ToolResult(success=False, error=str(e))


class ListWindowsTool(BaseTool):
    """List open windows."""

    @property
    def name(self) -> str:
        return "list_windows"

    @property
    def description(self) -> str:
        return "List all open windows"

    @property
    def risk_level(self) -> ToolRiskLevel:
        return ToolRiskLevel.SAFE

    async def execute(self) -> ToolResult:
        """List windows using pywinauto."""
        try:
            from pywinauto import Desktop

            windows = []
            for w in Desktop(backend="uia").windows():
                try:
                    if w.is_visible() and w.window_text():
                        windows.append({
                            "title": w.window_text(),
                            "class_name": w.class_name(),
                            "process_id": w.process_id(),
                            "rect": {
                                "left": w.rectangle().left,
                                "top": w.rectangle().top,
                                "right": w.rectangle().right,
                                "bottom": w.rectangle().bottom,
                            },
                        })
                except Exception:
                    continue

            return ToolResult(success=True, data={"windows": windows, "count": len(windows)})
        except Exception as e:
            logger.error(f"Failed to list windows: {e}")
            return ToolResult(success=False, error=str(e))


class FocusWindowTool(BaseTool):
    """Focus a window by title."""

    @property
    def name(self) -> str:
        return "focus_window"

    @property
    def description(self) -> str:
        return "Focus a window by title (partial match)"

    @property
    def risk_level(self) -> ToolRiskLevel:
        return ToolRiskLevel.SAFE

    async def execute(self, title: str) -> ToolResult:
        """Focus window.

        Args:
            title: Full or partial title of the window to bring to the foreground.
        """
        try:
            from pywinauto import Desktop

            windows = Desktop(backend="uia").windows()
            for w in windows:
                if title.lower() in w.window_text().lower():
                    w.set_focus()
                    return ToolResult(success=True, data=f"Focused window: {w.window_text()}")

            return ToolResult(success=False, error=f"Window not found: {title}")
        except Exception as e:
            logger.error(f"Failed to focus window: {e}")
            return ToolResult(success=False, error=str(e))


class TakeScreenshotTool(BaseTool):
    """Take a screenshot."""

    @property
    def name(self) -> str:
        return "take_screenshot"

    @property
    def description(self) -> str:
        return "Take a screenshot of the screen or a region"

    @property
    def risk_level(self) -> ToolRiskLevel:
        return ToolRiskLevel.SAFE

    async def execute(
        self,
        region: Optional[dict[str, int]] = None,
        save_path: Optional[str] = None,
    ) -> ToolResult:
        """Take screenshot.

        Args:
            region: Region to capture as
                {'left':int,'top':int,'width':int,'height':int}. Omit to capture the
                whole screen.
            save_path: Where to write the PNG. Omit to keep it in memory only.
        """
        try:
            import mss
            from PIL import Image

            with mss.mss() as sct:
                if region:
                    monitor = {
                        "left": region.get("left", 0),
                        "top": region.get("top", 0),
                        "width": region.get("width", 1920),
                        "height": region.get("height", 1080),
                    }
                else:
                    monitor = sct.monitors[1]  # Primary monitor

                screenshot = sct.grab(monitor)
                img = Image.frombytes("RGB", screenshot.size, screenshot.rgb)

                if save_path:
                    path = Path(save_path)
                else:
                    path = get_settings().get_temp_dir() / f"screenshot_{asyncio.current_task().get_name()}.png"

                path.parent.mkdir(parents=True, exist_ok=True)
                img.save(path)

                return ToolResult(success=True, data={"path": str(path), "size": img.size})
        except Exception as e:
            logger.error(f"Screenshot failed: {e}")
            return ToolResult(success=False, error=str(e))


class RunCommandTool(BaseTool):
    """Run a shell command."""

    @property
    def name(self) -> str:
        return "run_command"

    @property
    def description(self) -> str:
        return "Run a shell command and return output"

    @property
    def risk_level(self) -> ToolRiskLevel:
        return ToolRiskLevel.SENSITIVE

    async def execute(
        self,
        command: str,
        cwd: Optional[str] = None,
        timeout: int = 60,
        shell: bool = True,
    ) -> ToolResult:
        """Run command.

        Args:
            command: The command line to run.
            cwd: Working directory for the command. Defaults to the current directory.
            timeout: Seconds to wait before killing the command.
            shell: Run through the system shell, enabling pipes and redirection.
        """
        try:
            if shell:
                proc = await asyncio.create_subprocess_shell(
                    command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=cwd,
                )
            else:
                proc = await asyncio.create_subprocess_exec(
                    *command.split(),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=cwd,
                )

            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.communicate()
                return ToolResult(success=False, error=f"Command timed out after {timeout}s")

            return ToolResult(
                success=proc.returncode == 0,
                data={
                    "stdout": stdout.decode() if stdout else "",
                    "stderr": stderr.decode() if stderr else "",
                    "returncode": proc.returncode,
                },
                error=stderr.decode() if stderr and proc.returncode != 0 else None,
            )
        except Exception as e:
            logger.error(f"Command failed: {e}")
            return ToolResult(success=False, error=str(e))


class RunPowerShellTool(BaseTool):
    """Run a PowerShell command."""

    @property
    def name(self) -> str:
        return "run_powershell"

    @property
    def description(self) -> str:
        return "Run a PowerShell command"

    @property
    def risk_level(self) -> ToolRiskLevel:
        return ToolRiskLevel.SENSITIVE

    async def execute(
        self,
        command: str,
        cwd: Optional[str] = None,
        timeout: int = 60,
    ) -> ToolResult:
        """Run PowerShell command.

        Args:
            command: PowerShell command or script to run.
            cwd: Working directory for the command. Defaults to the current directory.
            timeout: Seconds to wait before killing the command.
        """
        try:
            full_cmd = f'powershell -NoProfile -Command "{command}"'
            return await RunCommandTool().execute(full_cmd, cwd=cwd, timeout=timeout)
        except Exception as e:
            logger.error(f"PowerShell failed: {e}")
            return ToolResult(success=False, error=str(e))


# File system tools
class ListDirectoryTool(BaseTool):
    """List directory contents."""

    @property
    def name(self) -> str:
        return "list_directory"

    @property
    def description(self) -> str:
        return "List files and directories in a path"

    @property
    def risk_level(self) -> ToolRiskLevel:
        return ToolRiskLevel.SAFE

    async def execute(self, path: str = ".") -> ToolResult:
        """List directory.

        Args:
            path: Directory to list.
        """
        try:
            p = Path(path).resolve()
            if not p.exists():
                return ToolResult(success=False, error=f"Path not found: {path}")

            items = []
            for item in p.iterdir():
                stat = item.stat()
                items.append({
                    "name": item.name,
                    "path": str(item),
                    "type": "directory" if item.is_dir() else "file",
                    "size": stat.st_size,
                    "modified": stat.st_mtime,
                })

            return ToolResult(success=True, data={"path": str(p), "items": items, "count": len(items)})
        except Exception as e:
            logger.error(f"List directory failed: {e}")
            return ToolResult(success=False, error=str(e))


class CreateFileTool(BaseTool):
    """Create a file with content."""

    @property
    def name(self) -> str:
        return "create_file"

    @property
    def description(self) -> str:
        return "Create a file with given content"

    @property
    def risk_level(self) -> ToolRiskLevel:
        return ToolRiskLevel.SAFE

    async def execute(self, path: str, content: str = "") -> ToolResult:
        """Create file.

        Args:
            path: Path of the file to create, including the filename.
            content: Initial text content for the file.
        """
        try:
            p = Path(path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            return ToolResult(success=True, data={"path": str(p), "size": len(content)})
        except Exception as e:
            logger.error(f"Create file failed: {e}")
            return ToolResult(success=False, error=str(e))


class ReadFileTool(BaseTool):
    """Read file content."""

    @property
    def name(self) -> str:
        return "read_file"

    @property
    def description(self) -> str:
        return "Read content of a file"

    @property
    def risk_level(self) -> ToolRiskLevel:
        return ToolRiskLevel.SAFE

    async def execute(self, path: str, encoding: str = "utf-8") -> ToolResult:
        """Read file.

        Args:
            path: Path of the file to read.
            encoding: Text encoding to decode with, such as utf-8.
        """
        try:
            p = Path(path)
            if not p.exists():
                return ToolResult(success=False, error=f"File not found: {path}")

            content = p.read_text(encoding=encoding)
            return ToolResult(success=True, data={"path": str(p), "content": content, "size": len(content)})
        except Exception as e:
            logger.error(f"Read file failed: {e}")
            return ToolResult(success=False, error=str(e))


class WriteFileTool(BaseTool):
    """Write content to a file (overwrite)."""

    @property
    def name(self) -> str:
        return "write_file"

    @property
    def description(self) -> str:
        return "Write content to a file (overwrites existing)"

    @property
    def risk_level(self) -> ToolRiskLevel:
        return ToolRiskLevel.SENSITIVE

    async def execute(self, path: str, content: str, encoding: str = "utf-8") -> ToolResult:
        """Write file.

        Args:
            path: Path of the file to write. It is overwritten if it exists.
            content: Full text content to write.
            encoding: Text encoding to write with, such as utf-8.
        """
        try:
            p = Path(path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding=encoding)
            return ToolResult(success=True, data={"path": str(p), "size": len(content)})
        except Exception as e:
            logger.error(f"Write file failed: {e}")
            return ToolResult(success=False, error=str(e))


class CreateDirectoryTool(BaseTool):
    """Create a directory."""

    @property
    def name(self) -> str:
        return "create_directory"

    @property
    def description(self) -> str:
        return "Create a directory (and parents)"

    @property
    def risk_level(self) -> ToolRiskLevel:
        return ToolRiskLevel.SAFE

    async def execute(self, path: str) -> ToolResult:
        """Create directory.

        Args:
            path: Directory to create, including any missing parents.
        """
        try:
            p = Path(path)
            p.mkdir(parents=True, exist_ok=True)
            return ToolResult(success=True, data={"path": str(p)})
        except Exception as e:
            logger.error(f"Create directory failed: {e}")
            return ToolResult(success=False, error=str(e))


class DeleteFileTool(BaseTool):
    """Delete a file or directory."""

    @property
    def name(self) -> str:
        return "delete_file"

    @property
    def description(self) -> str:
        return "Delete a file or directory"

    @property
    def risk_level(self) -> ToolRiskLevel:
        return ToolRiskLevel.DANGEROUS

    async def execute(self, path: str, recursive: bool = False) -> ToolResult:
        """Delete file/directory.

        Args:
            path: File or directory to delete.
            recursive: Required to delete a directory and everything inside it.
        """
        try:
            p = Path(path)
            if not p.exists():
                return ToolResult(success=False, error=f"Path not found: {path}")

            if p.is_dir():
                if recursive:
                    shutil.rmtree(p)
                else:
                    p.rmdir()
            else:
                p.unlink()

            return ToolResult(success=True, data={"path": str(p), "deleted": True})
        except Exception as e:
            logger.error(f"Delete failed: {e}")
            return ToolResult(success=False, error=str(e))


class SearchFilesTool(BaseTool):
    """Search for files by pattern."""

    @property
    def name(self) -> str:
        return "search_files"

    @property
    def description(self) -> str:
        return "Search for files matching a pattern"

    @property
    def risk_level(self) -> ToolRiskLevel:
        return ToolRiskLevel.SAFE

    async def execute(
        self,
        pattern: str,
        root: str = ".",
        max_results: int = 100,
    ) -> ToolResult:
        """Search files.

        Args:
            pattern: Filename glob to match, such as '*.py' or 'test_*'.
            root: Directory to search from, recursively.
            max_results: Maximum number of matches to return.
        """
        try:
            root_path = Path(root).resolve()
            results = []

            for path in root_path.rglob(pattern):
                if len(results) >= max_results:
                    break
                stat = path.stat()
                results.append({
                    "name": path.name,
                    "path": str(path),
                    "type": "directory" if path.is_dir() else "file",
                    "size": stat.st_size,
                    "modified": stat.st_mtime,
                })

            return ToolResult(success=True, data={"pattern": pattern, "root": str(root_path), "results": results})
        except Exception as e:
            logger.error(f"Search files failed: {e}")
            return ToolResult(success=False, error=str(e))


# Phase 2: Mouse, Keyboard, Clipboard, Window Action & Process Management Tools

class ClickMouseTool(BaseTool):
    """Click mouse at coordinates or current position."""

    @property
    def name(self) -> str:
        return "click_mouse"

    @property
    def description(self) -> str:
        return "Click mouse at specified (x, y) coordinates or current position. button can be 'left', 'right', 'middle'."

    @property
    def risk_level(self) -> ToolRiskLevel:
        return ToolRiskLevel.SENSITIVE

    async def execute(
        self,
        x: Optional[int] = None,
        y: Optional[int] = None,
        button: str = "left",
        clicks: int = 1,
    ) -> ToolResult:
        """Click mouse.

        Args:
            x: Screen x coordinate. Omit to click wherever the cursor already is.
            y: Screen y coordinate. Omit to click wherever the cursor already is.
            button: Which button to click: left, right, or middle.
            clicks: Number of clicks; use 2 for a double-click.
        """
        try:
            import pyautogui
            pyautogui.FAILSAFE = True

            if x is not None and y is not None:
                pyautogui.click(x=x, y=y, button=button, clicks=clicks)
                location_str = f"at ({x}, {y})"
            else:
                pyautogui.click(button=button, clicks=clicks)
                location_str = "at current position"

            return ToolResult(success=True, data=f"Clicked {button} button {clicks} time(s) {location_str}")
        except Exception as e:
            logger.error(f"Mouse click failed: {e}")
            return ToolResult(success=False, error=str(e))


class MoveMouseTool(BaseTool):
    """Move mouse to coordinates."""

    @property
    def name(self) -> str:
        return "move_mouse"

    @property
    def description(self) -> str:
        return "Move mouse cursor to specified (x, y) screen coordinates."

    @property
    def risk_level(self) -> ToolRiskLevel:
        return ToolRiskLevel.SAFE

    async def execute(self, x: int, y: int, duration: float = 0.2) -> ToolResult:
        """Move mouse.

        Args:
            x: Target screen x coordinate.
            y: Target screen y coordinate.
            duration: Seconds to spend moving there; 0 jumps instantly.
        """
        try:
            import pyautogui
            pyautogui.moveTo(x=x, y=y, duration=duration)
            return ToolResult(success=True, data=f"Moved mouse cursor to ({x}, {y})")
        except Exception as e:
            logger.error(f"Move mouse failed: {e}")
            return ToolResult(success=False, error=str(e))


class ScrollMouseTool(BaseTool):
    """Scroll mouse wheel."""

    @property
    def name(self) -> str:
        return "scroll_mouse"

    @property
    def description(self) -> str:
        return "Scroll mouse wheel up (positive clicks) or down (negative clicks)."

    @property
    def risk_level(self) -> ToolRiskLevel:
        return ToolRiskLevel.SAFE

    async def execute(self, amount: int = 300) -> ToolResult:
        """Scroll mouse.

        Args:
            amount: Scroll distance in notches. Positive scrolls up, negative scrolls
                down.
        """
        try:
            import pyautogui
            pyautogui.scroll(amount)
            direction = "up" if amount > 0 else "down"
            return ToolResult(success=True, data=f"Scrolled mouse wheel {direction} by {abs(amount)} units")
        except Exception as e:
            logger.error(f"Scroll mouse failed: {e}")
            return ToolResult(success=False, error=str(e))


class TypeTextTool(BaseTool):
    """Type text using keyboard."""

    @property
    def name(self) -> str:
        return "type_text"

    @property
    def description(self) -> str:
        return "Type specified text using keyboard simulation. Can optionally press Enter afterwards."

    @property
    def risk_level(self) -> ToolRiskLevel:
        return ToolRiskLevel.SENSITIVE

    async def execute(self, text: str, press_enter: bool = False, interval: float = 0.02) -> ToolResult:
        """Type text.

        Args:
            text: The literal text to type at the current cursor position.
            press_enter: Press Enter after typing the text.
            interval: Seconds between keystrokes; raise it for apps that drop fast
                input.
        """
        try:
            import pyautogui
            pyautogui.write(text, interval=interval)
            if press_enter:
                pyautogui.press("enter")
            return ToolResult(success=True, data=f"Typed text: {text[:50]}...")
        except Exception as e:
            logger.error(f"Type text failed: {e}")
            return ToolResult(success=False, error=str(e))


class PressKeyTool(BaseTool):
    """Press a keyboard key."""

    @property
    def name(self) -> str:
        return "press_key"

    @property
    def description(self) -> str:
        return "Press a keyboard key (e.g. 'enter', 'esc', 'tab', 'backspace', 'space', 'up', 'down', 'f5')."

    @property
    def risk_level(self) -> ToolRiskLevel:
        return ToolRiskLevel.SAFE

    async def execute(self, key: str, presses: int = 1) -> ToolResult:
        """Press key.

        Args:
            key: Key name to press, such as enter, tab, esc, f5, up, or a single
                character.
            presses: How many times to press the key.
        """
        try:
            import pyautogui
            pyautogui.press(key, presses=presses)
            return ToolResult(success=True, data=f"Pressed key '{key}' {presses} time(s)")
        except Exception as e:
            logger.error(f"Press key failed: {e}")
            return ToolResult(success=False, error=str(e))


class HotkeyTool(BaseTool):
    """Execute keyboard shortcut / hotkey combination."""

    @property
    def name(self) -> str:
        return "hotkey"

    @property
    def description(self) -> str:
        return "Press key combination (e.g., ['ctrl', 'c'], ['ctrl', 'v'], ['alt', 'tab'], ['win', 'r'], ['ctrl', 'shift', 'esc'])."

    @property
    def risk_level(self) -> ToolRiskLevel:
        return ToolRiskLevel.SENSITIVE

    async def execute(self, keys: list[str]) -> ToolResult:
        """Execute hotkey.

        Args:
            keys: Keys to hold together, in order, e.g. ['ctrl', 'shift', 'esc'].
        """
        try:
            import pyautogui
            pyautogui.hotkey(*keys)
            return ToolResult(success=True, data=f"Executed hotkey: {'+'.join(keys)}")
        except Exception as e:
            logger.error(f"Hotkey failed: {e}")
            return ToolResult(success=False, error=str(e))


class WindowActionTool(BaseTool):
    """Perform action on a window (minimize, maximize, restore, close)."""

    @property
    def name(self) -> str:
        return "window_action"

    @property
    def description(self) -> str:
        return "Perform window operation by title. Actions: 'minimize', 'maximize', 'restore', 'close'."

    @property
    def risk_level(self) -> ToolRiskLevel:
        return ToolRiskLevel.SAFE

    async def execute(self, title: str, action: str = "minimize") -> ToolResult:
        """Window action.

        Args:
            title: Full or partial title of the target window.
            action: What to do with it: minimize, maximize, restore, or close.
        """
        try:
            from pywinauto import Desktop

            windows = Desktop(backend="uia").windows()
            action = action.lower()

            for w in windows:
                if title.lower() in w.window_text().lower():
                    if action == "minimize":
                        w.minimize()
                    elif action == "maximize":
                        w.maximize()
                    elif action == "restore":
                        w.restore()
                    elif action == "close":
                        w.close()
                    else:
                        return ToolResult(success=False, error=f"Unknown window action: {action}")
                    return ToolResult(success=True, data=f"Window action '{action}' performed on: {w.window_text()}")

            return ToolResult(success=False, error=f"Window matching '{title}' not found")
        except Exception as e:
            logger.error(f"Window action failed: {e}")
            return ToolResult(success=False, error=str(e))


class GetClipboardTool(BaseTool):
    """Get text content from system clipboard."""

    @property
    def name(self) -> str:
        return "get_clipboard"

    @property
    def description(self) -> str:
        return "Get text content currently stored in system clipboard."

    @property
    def risk_level(self) -> ToolRiskLevel:
        return ToolRiskLevel.SAFE

    async def execute(self) -> ToolResult:
        """Get clipboard."""
        try:
            import PySide6.QtWidgets
            from PySide6.QtWidgets import QApplication

            app = QApplication.instance()
            if not app:
                clipboard_text = ""
            else:
                clipboard_text = app.clipboard().text()

            return ToolResult(success=True, data={"text": clipboard_text})
        except Exception as e:
            logger.error(f"Get clipboard failed: {e}")
            return ToolResult(success=False, error=str(e))


class SetClipboardTool(BaseTool):
    """Set text content into system clipboard."""

    @property
    def name(self) -> str:
        return "set_clipboard"

    @property
    def description(self) -> str:
        return "Copy specified text to system clipboard."

    @property
    def risk_level(self) -> ToolRiskLevel:
        return ToolRiskLevel.SAFE

    async def execute(self, text: str) -> ToolResult:
        """Set clipboard.

        Args:
            text: Text to place on the Windows clipboard.
        """
        try:
            from PySide6.QtWidgets import QApplication

            app = QApplication.instance()
            if app:
                app.clipboard().setText(text)
                return ToolResult(success=True, data=f"Copied {len(text)} characters to clipboard")
            else:
                # Fallback to powershell Set-Clipboard
                proc = await asyncio.create_subprocess_shell(
                    f'powershell -NoProfile -Command "Set-Clipboard -Value \'{text}\'"',
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await proc.communicate()
                return ToolResult(success=True, data=f"Copied {len(text)} characters to clipboard via PowerShell")
        except Exception as e:
            logger.error(f"Set clipboard failed: {e}")
            return ToolResult(success=False, error=str(e))


class ListProcessesTool(BaseTool):
    """List active processes on system."""

    @property
    def name(self) -> str:
        return "list_processes"

    @property
    def description(self) -> str:
        return "List top active processes ordered by CPU or Memory usage."

    @property
    def risk_level(self) -> ToolRiskLevel:
        return ToolRiskLevel.SAFE

    async def execute(self, limit: int = 15, sort_by: str = "memory") -> ToolResult:
        """List processes.

        Args:
            limit: Maximum number of processes to return.
            sort_by: Sort key: cpu, memory, name, or pid.
        """
        try:
            import psutil

            processes = []
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
                try:
                    info = proc.info
                    processes.append({
                        "pid": info['pid'],
                        "name": info['name'],
                        "cpu_percent": round(info['cpu_percent'] or 0.0, 1),
                        "memory_percent": round(info['memory_percent'] or 0.0, 1),
                    })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            key = "memory_percent" if sort_by == "memory" else "cpu_percent"
            sorted_procs = sorted(processes, key=lambda x: x[key], reverse=True)[:limit]

            return ToolResult(success=True, data={"processes": sorted_procs, "count": len(sorted_procs)})
        except Exception as e:
            logger.error(f"List processes failed: {e}")
            return ToolResult(success=False, error=str(e))


# Register all tools
def register_computer_tools():
    """Register all computer tools."""
    tools = [
        OpenApplicationTool(),
        CloseApplicationTool(),
        ListWindowsTool(),
        FocusWindowTool(),
        TakeScreenshotTool(),
        RunCommandTool(),
        RunPowerShellTool(),
        ListDirectoryTool(),
        CreateFileTool(),
        ReadFileTool(),
        WriteFileTool(),
        CreateDirectoryTool(),
        DeleteFileTool(),
        SearchFilesTool(),
        ClickMouseTool(),
        MoveMouseTool(),
        ScrollMouseTool(),
        TypeTextTool(),
        PressKeyTool(),
        HotkeyTool(),
        WindowActionTool(),
        GetClipboardTool(),
        SetClipboardTool(),
        ListProcessesTool(),
    ]
    for tool in tools:
        register_tool(tool, category="computer")