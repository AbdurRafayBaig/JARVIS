"""JARVIS Tools - Windows Control

Everyday control of the computer: launching apps, opening Settings pages,
files and websites, volume, brightness, media keys, theme, and power.
"""

import asyncio
import ctypes
import os
import shutil
import subprocess
import webbrowser
from pathlib import Path
from typing import Optional
from urllib.parse import quote_plus

from jarvis.agent.tools import BaseTool, ToolResult, ToolRiskLevel, register_tool
from jarvis.core.logging import get_logger
from jarvis.tools.paths import resolve_path, known_folder

logger = get_logger(__name__)

# -- key presses --------------------------------------------------------------

KEYEVENTF_KEYUP = 0x0002
VK_VOLUME_MUTE = 0xAD
VK_VOLUME_DOWN = 0xAE
VK_VOLUME_UP = 0xAF
VK_MEDIA_NEXT = 0xB0
VK_MEDIA_PREV = 0xB1
VK_MEDIA_STOP = 0xB2
VK_MEDIA_PLAY_PAUSE = 0xB3
VK_LWIN = 0x5B
VK_D = 0x44

# One volume key press moves the Windows master volume by 2%.
VOLUME_STEP_PERCENT = 2


def _tap(vk: int, times: int = 1) -> None:
    """Press and release a virtual key."""
    user32 = ctypes.windll.user32
    for _ in range(times):
        user32.keybd_event(vk, 0, 0, 0)
        user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)


def _chord(*vks: int) -> None:
    """Hold several keys together, then release them in reverse."""
    user32 = ctypes.windll.user32
    for vk in vks:
        user32.keybd_event(vk, 0, 0, 0)
    for vk in reversed(vks):
        user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)


# -- application launching ----------------------------------------------------

# Friendly name -> something ShellExecute can start: an executable that is on
# PATH or registered under App Paths, or a protocol URI for a Store app.
APP_ALIASES = {
    "vscode": "code",
    "vs code": "code",
    "visual studio code": "code",
    "code": "code",
    "chrome": "chrome",
    "google chrome": "chrome",
    "firefox": "firefox",
    "edge": "msedge",
    "microsoft edge": "msedge",
    "browser": "msedge",
    "notepad": "notepad",
    "terminal": "wt",
    "windows terminal": "wt",
    "powershell": "powershell",
    "cmd": "cmd",
    "command prompt": "cmd",
    "explorer": "explorer",
    "file explorer": "explorer",
    "files": "explorer",
    "task manager": "taskmgr",
    "control panel": "control",
    "calculator": "calc",
    "calc": "calc",
    "paint": "mspaint",
    "word": "winword",
    "excel": "excel",
    "powerpoint": "powerpnt",
    "outlook": "outlook",
    "snipping tool": "snippingtool",
    "settings": "ms-settings:",
    "camera": "microsoft.windows.camera:",
    "photos": "ms-photos:",
    "store": "ms-windows-store:",
    "microsoft store": "ms-windows-store:",
    "clock": "ms-clock:",
    "alarms": "ms-clock:",
    "calendar": "outlookcal:",
    "mail": "outlookmail:",
    "maps": "bingmaps:",
    "spotify": "spotify:",
    "whatsapp": "whatsapp:",
}

# Process image names for closing an app by its friendly name.
PROCESS_NAMES = {
    "vscode": "Code",
    "vs code": "Code",
    "visual studio code": "Code",
    "chrome": "chrome",
    "google chrome": "chrome",
    "edge": "msedge",
    "microsoft edge": "msedge",
    "firefox": "firefox",
    "notepad": "notepad",
    "calculator": "CalculatorApp",
    "paint": "mspaint",
    "word": "WINWORD",
    "excel": "EXCEL",
    "powerpoint": "POWERPNT",
    "terminal": "WindowsTerminal",
    "task manager": "Taskmgr",
    "spotify": "Spotify",
    "explorer": "explorer",
    "settings": "SystemSettings",
    "calc": "CalculatorApp",
}


def _start_menu_shortcut(name: str) -> Optional[Path]:
    """Find a Start Menu shortcut whose name matches."""
    roots = [
        Path(os.environ.get("ProgramData", r"C:\ProgramData")) / "Microsoft/Windows/Start Menu/Programs",
        Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs",
    ]
    wanted = name.lower()
    partial = None
    for root in roots:
        if not root.is_dir():
            continue
        for shortcut in root.rglob("*.lnk"):
            stem = shortcut.stem.lower()
            if stem == wanted:
                return shortcut
            if partial is None and wanted in stem and "uninstall" not in stem:
                partial = shortcut
    return partial


def _store_app_id(name: str) -> Optional[str]:
    """Look up a Store/packaged app's AppID by its display name."""
    try:
        script = (
            "Get-StartApps | Where-Object { $_.Name -like '*" + name.replace("'", "") + "*' } "
            "| Select-Object -First 1 -ExpandProperty AppID"
        )
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            capture_output=True, text=True, timeout=15,
        )
        app_id = result.stdout.strip()
        return app_id or None
    except Exception:
        return None


def launch_application(name: str) -> str:
    """Start an application by friendly name, executable, or path.

    Tries, in order: a known alias, the shell (which resolves PATH and
    registered App Paths), a Start Menu shortcut, then the installed Store
    apps. Raises FileNotFoundError when nothing matches.
    """
    key = name.strip().lower()
    target = APP_ALIASES.get(key, name.strip())

    # A protocol URI (ms-settings:, spotify:) or an existing path.
    if target.endswith(":") or Path(target).exists():
        os.startfile(target)
        return target

    resolved = shutil.which(target)
    if resolved:
        subprocess.Popen([resolved], close_fds=True)
        return resolved

    try:
        # ShellExecute resolves executables registered under App Paths,
        # which is how chrome, winword and excel are found.
        os.startfile(target)
        return target
    except OSError:
        pass

    shortcut = _start_menu_shortcut(key)
    if shortcut:
        os.startfile(str(shortcut))
        return str(shortcut)

    app_id = _store_app_id(key)
    if app_id:
        subprocess.Popen(["explorer.exe", f"shell:AppsFolder\\{app_id}"])
        return app_id

    raise FileNotFoundError(f"Could not find an application called '{name}'")


# -- settings pages -----------------------------------------------------------

SETTINGS_PAGES = {
    "home": "ms-settings:",
    "display": "ms-settings:display",
    "screen": "ms-settings:display",
    "brightness": "ms-settings:display",
    "night light": "ms-settings:nightlight",
    "sound": "ms-settings:sound",
    "audio": "ms-settings:sound",
    "volume": "ms-settings:sound",
    "notifications": "ms-settings:notifications",
    "focus": "ms-settings:quiethours",
    "power": "ms-settings:powersleep",
    "battery": "ms-settings:batterysaver",
    "storage": "ms-settings:storagesense",
    "bluetooth": "ms-settings:bluetooth",
    "devices": "ms-settings:bluetooth",
    "printers": "ms-settings:printers",
    "mouse": "ms-settings:mousetouchpad",
    "touchpad": "ms-settings:devices-touchpad",
    "keyboard": "ms-settings:keyboard",
    "wifi": "ms-settings:network-wifi",
    "wi-fi": "ms-settings:network-wifi",
    "network": "ms-settings:network",
    "internet": "ms-settings:network",
    "vpn": "ms-settings:network-vpn",
    "hotspot": "ms-settings:network-mobilehotspot",
    "airplane mode": "ms-settings:network-airplanemode",
    "personalization": "ms-settings:personalization",
    "background": "ms-settings:personalization-background",
    "wallpaper": "ms-settings:personalization-background",
    "colors": "ms-settings:colors",
    "theme": "ms-settings:themes",
    "themes": "ms-settings:themes",
    "lock screen": "ms-settings:lockscreen",
    "taskbar": "ms-settings:taskbar",
    "start": "ms-settings:personalization-start",
    "apps": "ms-settings:appsfeatures",
    "installed apps": "ms-settings:appsfeatures",
    "default apps": "ms-settings:defaultapps",
    "startup apps": "ms-settings:startupapps",
    "accounts": "ms-settings:yourinfo",
    "sign-in": "ms-settings:signinoptions",
    "date": "ms-settings:dateandtime",
    "time": "ms-settings:dateandtime",
    "language": "ms-settings:regionlanguage",
    "region": "ms-settings:regionlanguage",
    "privacy": "ms-settings:privacy",
    "camera": "ms-settings:privacy-webcam",
    "microphone": "ms-settings:privacy-microphone",
    "update": "ms-settings:windowsupdate",
    "windows update": "ms-settings:windowsupdate",
    "about": "ms-settings:about",
    "system": "ms-settings:about",
    "accessibility": "ms-settings:easeofaccess",
}


def settings_uri(page: str) -> Optional[str]:
    """ms-settings URI for a named page, matching loosely."""
    key = page.strip().lower().replace(" settings", "").strip()
    if not key:
        return SETTINGS_PAGES["home"]
    if key in SETTINGS_PAGES:
        return SETTINGS_PAGES[key]
    for name, uri in SETTINGS_PAGES.items():
        if name in key or key in name:
            return uri
    return None


# -- tools --------------------------------------------------------------------


class OpenSettingsTool(BaseTool):
    """Open a Windows Settings page."""

    @property
    def name(self) -> str:
        return "open_settings"

    @property
    def description(self) -> str:
        return (
            "Open Windows Settings, optionally on a specific page such as display, "
            "sound, wifi, bluetooth, apps, update, personalization or privacy"
        )

    async def execute(self, page: str = "") -> ToolResult:
        """Open Settings.

        Args:
            page: Page to open, e.g. 'display', 'sound', 'wifi', 'bluetooth', 'apps',
                'windows update'. Leave empty for the Settings home page.
        """
        uri = settings_uri(page)
        if uri is None:
            return ToolResult(
                success=False,
                error=f"No Settings page called '{page}'. Known pages: "
                      f"{', '.join(sorted(SETTINGS_PAGES))}",
            )
        try:
            os.startfile(uri)
            label = page.strip() or "home"
            return ToolResult(success=True, data=f"Opened Settings ({label})")
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class OpenPathTool(BaseTool):
    """Open a file or folder with its default application."""

    @property
    def name(self) -> str:
        return "open_path"

    @property
    def description(self) -> str:
        return (
            "Open a file with its default app, or a folder in File Explorer. Accepts "
            "names like 'desktop', 'downloads', 'documents' as well as full paths"
        )

    async def execute(self, path: str) -> ToolResult:
        """Open a file or folder.

        Args:
            path: File or folder to open: a full path, or a user folder name such as
                'desktop', 'downloads', 'documents/report.docx'.
        """
        try:
            target = resolve_path(path)
            if not target.exists():
                return ToolResult(success=False, error=f"Path not found: {target}")
            os.startfile(str(target))
            return ToolResult(success=True, data=f"Opened {target}")
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class OpenUrlTool(BaseTool):
    """Open a website in the default browser."""

    @property
    def name(self) -> str:
        return "open_url"

    @property
    def description(self) -> str:
        return "Open a website in the default browser"

    async def execute(self, url: str) -> ToolResult:
        """Open a URL.

        Args:
            url: Address to open. 'https://' is added when no scheme is given.
        """
        try:
            address = url.strip()
            if "://" not in address:
                address = f"https://{address}"
            webbrowser.open(address)
            return ToolResult(success=True, data=f"Opened {address}")
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class WebSearchTool(BaseTool):
    """Search the web in the default browser."""

    @property
    def name(self) -> str:
        return "web_search"

    @property
    def description(self) -> str:
        return "Search the web (Google or YouTube) for a query in the default browser"

    async def execute(self, query: str, site: str = "google") -> ToolResult:
        """Search the web.

        Args:
            query: What to search for.
            site: Where to search: 'google' or 'youtube'.
        """
        try:
            if site.lower() == "youtube":
                address = f"https://www.youtube.com/results?search_query={quote_plus(query)}"
            else:
                address = f"https://www.google.com/search?q={quote_plus(query)}"
            webbrowser.open(address)
            return ToolResult(success=True, data=f"Searched {site} for '{query}'")
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class VolumeTool(BaseTool):
    """Control the system volume."""

    @property
    def name(self) -> str:
        return "volume"

    @property
    def description(self) -> str:
        return "Change the system volume: turn it up or down, set a level, or mute/unmute"

    async def execute(self, action: str, amount: int = 10) -> ToolResult:
        """Change the volume.

        Args:
            action: One of 'up', 'down', 'set', 'mute' (mute toggles).
            amount: Percent to move by for up/down, or the level (0-100) for set.
        """
        try:
            action = action.lower().strip()
            amount = max(0, min(100, int(amount)))
            steps = max(1, round(amount / VOLUME_STEP_PERCENT))

            if action == "up":
                _tap(VK_VOLUME_UP, steps)
                return ToolResult(success=True, data=f"Volume up {amount}%")
            if action == "down":
                _tap(VK_VOLUME_DOWN, steps)
                return ToolResult(success=True, data=f"Volume down {amount}%")
            if action in ("mute", "unmute", "toggle"):
                _tap(VK_VOLUME_MUTE)
                return ToolResult(success=True, data="Toggled mute")
            if action == "set":
                # Drop to zero, then climb to the requested level.
                _tap(VK_VOLUME_DOWN, 50)
                _tap(VK_VOLUME_UP, round(amount / VOLUME_STEP_PERCENT))
                return ToolResult(success=True, data=f"Volume set to {amount}%")

            return ToolResult(success=False, error=f"Unknown volume action: {action}")
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class MediaControlTool(BaseTool):
    """Control media playback."""

    @property
    def name(self) -> str:
        return "media_control"

    @property
    def description(self) -> str:
        return "Control whatever is playing: play/pause, next track, previous track, stop"

    async def execute(self, action: str) -> ToolResult:
        """Send a media key.

        Args:
            action: One of 'play_pause', 'next', 'previous', 'stop'.
        """
        keys = {
            "play_pause": VK_MEDIA_PLAY_PAUSE,
            "play": VK_MEDIA_PLAY_PAUSE,
            "pause": VK_MEDIA_PLAY_PAUSE,
            "next": VK_MEDIA_NEXT,
            "previous": VK_MEDIA_PREV,
            "prev": VK_MEDIA_PREV,
            "stop": VK_MEDIA_STOP,
        }
        vk = keys.get(action.lower().strip())
        if vk is None:
            return ToolResult(success=False, error=f"Unknown media action: {action}")
        _tap(vk)
        return ToolResult(success=True, data=f"Media: {action}")


class BrightnessTool(BaseTool):
    """Control the display brightness."""

    @property
    def name(self) -> str:
        return "brightness"

    @property
    def description(self) -> str:
        return "Set the laptop display brightness, or raise/lower it"

    @staticmethod
    async def _powershell(script: str) -> tuple[int, str, str]:
        process = await asyncio.create_subprocess_exec(
            "powershell", "-NoProfile", "-Command", script,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        out, err = await asyncio.wait_for(process.communicate(), timeout=20)
        return process.returncode, out.decode(errors="replace").strip(), err.decode(errors="replace").strip()

    async def execute(self, action: str, amount: int = 10) -> ToolResult:
        """Change the brightness.

        Args:
            action: One of 'up', 'down', 'set'.
            amount: Percent to move by for up/down, or the level (0-100) for set.
        """
        try:
            action = action.lower().strip()
            amount = max(0, min(100, int(amount)))

            if action in ("up", "down"):
                code, out, err = await self._powershell(
                    "(Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightness)"
                    ".CurrentBrightness"
                )
                if code != 0 or not out.isdigit():
                    return ToolResult(
                        success=False,
                        error="This display does not support software brightness control.",
                    )
                current = int(out)
                level = current + amount if action == "up" else current - amount
            elif action == "set":
                level = amount
            else:
                return ToolResult(success=False, error=f"Unknown brightness action: {action}")

            level = max(0, min(100, level))
            code, _, err = await self._powershell(
                "$m = Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightnessMethods; "
                f"Invoke-CimMethod -InputObject $m -MethodName WmiSetBrightness "
                f"-Arguments @{{Timeout=1; Brightness={level}}} | Out-Null"
            )
            if code != 0:
                return ToolResult(
                    success=False,
                    error="This display does not support software brightness control "
                          "(external monitors usually do not).",
                )
            return ToolResult(success=True, data=f"Brightness set to {level}%")
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class ShowDesktopTool(BaseTool):
    """Minimize everything to show the desktop."""

    @property
    def name(self) -> str:
        return "show_desktop"

    @property
    def description(self) -> str:
        return "Minimize all windows to show the desktop (again to restore them)"

    async def execute(self) -> ToolResult:
        """Toggle show-desktop."""
        _chord(VK_LWIN, VK_D)
        return ToolResult(success=True, data="Toggled show desktop")


class LockScreenTool(BaseTool):
    """Lock the computer."""

    @property
    def name(self) -> str:
        return "lock_screen"

    @property
    def description(self) -> str:
        return "Lock the computer"

    async def execute(self) -> ToolResult:
        """Lock the workstation."""
        if ctypes.windll.user32.LockWorkStation():
            return ToolResult(success=True, data="Locked the computer")
        return ToolResult(success=False, error="Windows refused to lock the workstation")


class PowerActionTool(BaseTool):
    """Shut down, restart, sleep or sign out."""

    @property
    def name(self) -> str:
        return "power_action"

    @property
    def description(self) -> str:
        return (
            "Shut down, restart, sleep or sign out of the computer. Shutdown and "
            "restart wait 30 seconds and can be cancelled with action 'cancel'"
        )

    @property
    def risk_level(self) -> ToolRiskLevel:
        return ToolRiskLevel.DANGEROUS

    async def execute(self, action: str) -> ToolResult:
        """Perform a power action.

        Args:
            action: One of 'shutdown', 'restart', 'sleep', 'sign_out', 'cancel'.
        """
        commands = {
            "shutdown": ["shutdown", "/s", "/t", "30"],
            "restart": ["shutdown", "/r", "/t", "30"],
            "sign_out": ["shutdown", "/l"],
            "cancel": ["shutdown", "/a"],
            "sleep": ["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"],
        }
        command = commands.get(action.lower().strip())
        if command is None:
            return ToolResult(success=False, error=f"Unknown power action: {action}")
        try:
            process = await asyncio.create_subprocess_exec(
                *command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            _, err = await process.communicate()
            if process.returncode != 0:
                return ToolResult(success=False, error=err.decode(errors="replace").strip() or "failed")
            notes = {
                "shutdown": "Shutting down in 30 seconds. Say 'cancel shutdown' to stop it.",
                "restart": "Restarting in 30 seconds. Say 'cancel shutdown' to stop it.",
                "cancel": "Cancelled the pending shutdown.",
                "sleep": "Going to sleep.",
                "sign_out": "Signing out.",
            }
            return ToolResult(success=True, data=notes[action.lower().strip()])
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class SetThemeTool(BaseTool):
    """Switch Windows between dark and light mode."""

    @property
    def name(self) -> str:
        return "set_theme"

    @property
    def description(self) -> str:
        return "Switch Windows and apps between dark mode and light mode"

    @property
    def risk_level(self) -> ToolRiskLevel:
        return ToolRiskLevel.SAFE

    async def execute(self, mode: str) -> ToolResult:
        """Set the colour mode.

        Args:
            mode: 'dark' or 'light'.
        """
        mode = mode.lower().strip()
        if mode not in ("dark", "light"):
            return ToolResult(success=False, error="mode must be 'dark' or 'light'")
        try:
            import winreg

            value = 0 if mode == "dark" else 1
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
                winreg.SetValueEx(key, "AppsUseLightTheme", 0, winreg.REG_DWORD, value)
                winreg.SetValueEx(key, "SystemUsesLightTheme", 0, winreg.REG_DWORD, value)

            # Tell running programs the setting changed so they repaint.
            HWND_BROADCAST, WM_SETTINGCHANGE, SMTO_ABORTIFHUNG = 0xFFFF, 0x001A, 0x0002
            ctypes.windll.user32.SendMessageTimeoutW(
                HWND_BROADCAST, WM_SETTINGCHANGE, 0, "ImmersiveColorSet",
                SMTO_ABORTIFHUNG, 2000, None,
            )
            return ToolResult(success=True, data=f"Switched to {mode} mode")
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class BatteryStatusTool(BaseTool):
    """Report battery level."""

    @property
    def name(self) -> str:
        return "battery_status"

    @property
    def description(self) -> str:
        return "Report the battery percentage and whether the computer is plugged in"

    async def execute(self) -> ToolResult:
        """Read the battery."""
        try:
            import psutil

            battery = psutil.sensors_battery()
            if battery is None:
                return ToolResult(success=True, data="This computer has no battery.")
            state = "plugged in" if battery.power_plugged else "on battery"
            return ToolResult(success=True, data=f"Battery is at {round(battery.percent)}%, {state}.")
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class MovePathTool(BaseTool):
    """Move or rename a file or folder."""

    @property
    def name(self) -> str:
        return "move_path"

    @property
    def description(self) -> str:
        return "Move a file or folder to another location, or rename it"

    @property
    def risk_level(self) -> ToolRiskLevel:
        return ToolRiskLevel.SENSITIVE

    async def execute(self, source: str, destination: str) -> ToolResult:
        """Move or rename.

        Args:
            source: File or folder to move. User folder names like 'desktop/a.txt' work.
            destination: New path. If it is an existing folder the item is moved into it.
        """
        try:
            src = resolve_path(source)
            dst = resolve_path(destination)
            if not src.exists():
                return ToolResult(success=False, error=f"Path not found: {src}")
            if dst.is_dir():
                dst = dst / src.name
            if dst.exists():
                return ToolResult(success=False, error=f"Destination already exists: {dst}")
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
            return ToolResult(success=True, data=f"Moved {src.name} to {dst}")
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class CopyPathTool(BaseTool):
    """Copy a file or folder."""

    @property
    def name(self) -> str:
        return "copy_path"

    @property
    def description(self) -> str:
        return "Copy a file or folder to another location"

    @property
    def risk_level(self) -> ToolRiskLevel:
        return ToolRiskLevel.SENSITIVE

    async def execute(self, source: str, destination: str) -> ToolResult:
        """Copy.

        Args:
            source: File or folder to copy. User folder names like 'desktop/a.txt' work.
            destination: Where to copy to. If it is an existing folder the copy goes inside it.
        """
        try:
            src = resolve_path(source)
            dst = resolve_path(destination)
            if not src.exists():
                return ToolResult(success=False, error=f"Path not found: {src}")
            if dst.is_dir():
                dst = dst / src.name
            if dst.exists():
                return ToolResult(success=False, error=f"Destination already exists: {dst}")
            dst.parent.mkdir(parents=True, exist_ok=True)
            if src.is_dir():
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)
            return ToolResult(success=True, data=f"Copied {src.name} to {dst}")
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class RecyclePathTool(BaseTool):
    """Send a file or folder to the Recycle Bin."""

    @property
    def name(self) -> str:
        return "recycle_path"

    @property
    def description(self) -> str:
        return (
            "Delete a file or folder by sending it to the Recycle Bin, where it can "
            "be restored. Prefer this over delete_file"
        )

    @property
    def risk_level(self) -> ToolRiskLevel:
        return ToolRiskLevel.SENSITIVE

    async def execute(self, path: str) -> ToolResult:
        """Recycle a file or folder.

        Args:
            path: File or folder to send to the Recycle Bin.
        """
        try:
            from win32com.shell import shell, shellcon

            target = resolve_path(path)
            if not target.exists():
                return ToolResult(success=False, error=f"Path not found: {target}")

            flags = shellcon.FOF_ALLOWUNDO | shellcon.FOF_NOCONFIRMATION | shellcon.FOF_SILENT
            code, aborted = shell.SHFileOperation(
                (0, shellcon.FO_DELETE, str(target), None, flags, None, None)
            )
            if code != 0 or aborted:
                return ToolResult(success=False, error=f"Windows could not recycle {target} (code {code})")
            return ToolResult(success=True, data=f"Moved {target.name} to the Recycle Bin")
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class WaitTool(BaseTool):
    """Pause between steps."""

    @property
    def name(self) -> str:
        return "wait"

    @property
    def description(self) -> str:
        return "Wait a moment, e.g. for an application window to finish opening"

    async def execute(self, seconds: float = 1.0) -> ToolResult:
        """Wait.

        Args:
            seconds: How long to wait, up to 30 seconds.
        """
        seconds = max(0.0, min(30.0, float(seconds)))
        await asyncio.sleep(seconds)
        return ToolResult(success=True, data=f"Waited {seconds:g}s")


def register_windows_tools() -> None:
    """Register the Windows control tools."""
    tools = [
        OpenSettingsTool(),
        OpenPathTool(),
        OpenUrlTool(),
        WebSearchTool(),
        VolumeTool(),
        MediaControlTool(),
        BrightnessTool(),
        ShowDesktopTool(),
        LockScreenTool(),
        PowerActionTool(),
        SetThemeTool(),
        BatteryStatusTool(),
        MovePathTool(),
        CopyPathTool(),
        RecyclePathTool(),
        WaitTool(),
    ]
    for tool in tools:
        register_tool(tool, "windows")
    logger.info(f"Registered {len(tools)} Windows control tools")
