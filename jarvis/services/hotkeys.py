"""Global Hotkey Service

Handles system-wide hotkey registration and listening.

Windows delivers global hotkeys as WM_HOTKEY messages to the thread that
registered them, so registration and the message pump both live on one
dedicated worker thread. Callbacks are marshalled back onto the asyncio loop.
"""

import asyncio
import ctypes
import sys
import threading
from ctypes import wintypes
from dataclasses import dataclass, field
from typing import Callable, Optional, Dict, Any
from loguru import logger

# Windows hotkey modifier flags (winuser.h)
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000

WM_HOTKEY = 0x0312
WM_QUIT = 0x0012
PM_REMOVE = 0x0001

_MODIFIERS = {
    "ctrl": MOD_CONTROL,
    "control": MOD_CONTROL,
    "alt": MOD_ALT,
    "shift": MOD_SHIFT,
    "win": MOD_WIN,
    "super": MOD_WIN,
    "cmd": MOD_WIN,
}

# Virtual-key codes for keys whose code is not simply ord(upper(char)).
_NAMED_KEYS = {
    "space": 0x20,
    "enter": 0x0D,
    "return": 0x0D,
    "tab": 0x09,
    "esc": 0x1B,
    "escape": 0x1B,
    "backspace": 0x08,
    "delete": 0x2E,
    "insert": 0x2D,
    "home": 0x24,
    "end": 0x23,
    "pageup": 0x21,
    "pagedown": 0x22,
    "left": 0x25,
    "up": 0x26,
    "right": 0x27,
    "down": 0x28,
    "print": 0x2C,
    "printscreen": 0x2C,
}
_NAMED_KEYS.update({f"f{i}": 0x6F + i for i in range(1, 25)})  # F1..F24


class HotkeyParseError(ValueError):
    """Raised when a hotkey string cannot be understood."""


def parse_hotkey(spec: str) -> tuple[int, int]:
    """Parse a spec like 'ctrl+space' into (modifiers, virtual-key code)."""
    parts = [p.strip().lower() for p in spec.replace(" ", "").split("+") if p.strip()]
    if not parts:
        raise HotkeyParseError(f"Empty hotkey: {spec!r}")

    modifiers = 0
    key: Optional[int] = None

    for part in parts:
        if part in _MODIFIERS:
            modifiers |= _MODIFIERS[part]
        elif part in _NAMED_KEYS:
            key = _NAMED_KEYS[part]
        elif len(part) == 1:
            key = ord(part.upper())
        else:
            raise HotkeyParseError(f"Unknown key {part!r} in hotkey {spec!r}")

    if key is None:
        raise HotkeyParseError(f"Hotkey {spec!r} has modifiers but no key")

    # MOD_NOREPEAT stops a held-down combo from firing repeatedly.
    return modifiers | MOD_NOREPEAT, key


@dataclass
class HotkeyConfig:
    """Configuration for a hotkey."""
    key: str
    callback: Callable[[], Any]
    description: str = ""
    modifiers: list = field(default_factory=list)


class HotkeyService:
    """Service for managing global hotkeys."""

    def __init__(self):
        self._hotkeys: Dict[str, HotkeyConfig] = {}
        self._ids: Dict[str, int] = {}
        self._next_id = 1
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._ready = threading.Event()
        self._thread_id: Optional[int] = None
        self._supported = sys.platform == "win32"
        self._lock = threading.Lock()

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def is_supported(self) -> bool:
        """Global hotkeys are implemented for Windows only."""
        return self._supported

    async def start(self) -> None:
        """Start the hotkey listener."""
        if self._running:
            return

        if not self._supported:
            logger.warning(
                f"Global hotkeys are not supported on {sys.platform}; "
                f"registrations will be recorded but never fire."
            )
            self._running = True
            return

        self._loop = asyncio.get_running_loop()
        self._ready.clear()
        self._running = True

        self._thread = threading.Thread(
            target=self._message_loop, name="jarvis-hotkeys", daemon=True
        )
        self._thread.start()

        # Wait briefly for the pump to come up so registrations made right
        # after start() land on the listening thread.
        await asyncio.get_running_loop().run_in_executor(None, self._ready.wait, 2.0)
        logger.info("Hotkey service started")

    async def stop(self) -> None:
        """Stop the hotkey listener."""
        if not self._running:
            return

        self._running = False

        if self._thread is not None and self._thread_id is not None:
            # Wake the pump so it notices _running went False.
            ctypes.windll.user32.PostThreadMessageW(
                wintypes.DWORD(self._thread_id), WM_QUIT, 0, 0
            )
            await asyncio.get_running_loop().run_in_executor(None, self._thread.join, 3.0)

        self._thread = None
        self._thread_id = None
        logger.info("Hotkey service stopped")

    def _message_loop(self) -> None:
        """Register hotkeys and pump Windows messages on this thread."""
        user32 = ctypes.windll.user32
        self._thread_id = ctypes.windll.kernel32.GetCurrentThreadId()

        with self._lock:
            pending = list(self._hotkeys.values())
        for config in pending:
            self._register_on_thread(config)

        self._ready.set()

        msg = wintypes.MSG()
        try:
            while self._running:
                # PeekMessage keeps the loop responsive to _running going False.
                if user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, PM_REMOVE):
                    if msg.message == WM_QUIT:
                        break
                    if msg.message == WM_HOTKEY:
                        self._on_hotkey(int(msg.wParam))
                else:
                    # No message waiting; sleep briefly instead of spinning.
                    ctypes.windll.kernel32.Sleep(30)
        except Exception as e:
            logger.error(f"Hotkey message loop failed: {e}")
        finally:
            for hotkey_id in list(self._ids.values()):
                try:
                    user32.UnregisterHotKey(None, hotkey_id)
                except Exception:
                    pass

    def _register_on_thread(self, config: HotkeyConfig) -> bool:
        """Register one hotkey with Windows. Must run on the pump thread."""
        try:
            modifiers, vk = parse_hotkey(config.key)
        except HotkeyParseError as e:
            logger.error(str(e))
            return False

        with self._lock:
            hotkey_id = self._ids.get(config.key)
            if hotkey_id is None:
                hotkey_id = self._next_id
                self._next_id += 1
                self._ids[config.key] = hotkey_id

        if not ctypes.windll.user32.RegisterHotKey(None, hotkey_id, modifiers, vk):
            error = ctypes.get_last_error()
            logger.warning(
                f"Could not register hotkey {config.key!r} "
                f"(error {error}); another application may already own it."
            )
            return False

        logger.info(f"Registered global hotkey: {config.key} -> {config.description}")
        return True

    def _on_hotkey(self, hotkey_id: int) -> None:
        """Dispatch a WM_HOTKEY back onto the asyncio loop."""
        with self._lock:
            key = next((k for k, v in self._ids.items() if v == hotkey_id), None)
            config = self._hotkeys.get(key) if key else None

        if config is None:
            return

        logger.debug(f"Hotkey pressed: {config.key}")

        if self._loop is None or not self._loop.is_running():
            try:
                config.callback()
            except Exception as e:
                logger.error(f"Hotkey callback failed: {e}")
            return

        def invoke() -> None:
            try:
                result = config.callback()
                if asyncio.iscoroutine(result):
                    asyncio.ensure_future(result)
            except Exception as e:
                logger.error(f"Hotkey callback failed: {e}")

        self._loop.call_soon_threadsafe(invoke)

    def register(self, config: HotkeyConfig) -> None:
        """Register a hotkey.

        Registering while the service runs takes effect at the next restart of
        the pump, so callers normally register before calling :meth:`start`.
        """
        with self._lock:
            self._hotkeys[config.key] = config

        logger.debug(f"Registered hotkey: {config.key} -> {config.description}")

    def unregister(self, key: str) -> None:
        """Unregister a hotkey."""
        with self._lock:
            self._hotkeys.pop(key, None)
            hotkey_id = self._ids.pop(key, None)

        if hotkey_id is not None and self._supported:
            try:
                ctypes.windll.user32.UnregisterHotKey(None, hotkey_id)
            except Exception:
                pass

        logger.debug(f"Unregistered hotkey: {key}")

    def get_registered(self) -> Dict[str, HotkeyConfig]:
        """Get all registered hotkeys."""
        with self._lock:
            return self._hotkeys.copy()


_hotkey_service: Optional[HotkeyService] = None


def get_hotkey_service() -> HotkeyService:
    """Get the global hotkey service instance."""
    global _hotkey_service
    if _hotkey_service is None:
        _hotkey_service = HotkeyService()
    return _hotkey_service
