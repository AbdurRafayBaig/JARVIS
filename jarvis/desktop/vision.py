"""Vision Capture

Handles screen capture and region selection.
"""

import io
from pathlib import Path
from typing import Optional
from PIL import Image
from loguru import logger

from jarvis.core.config import get_settings


class VisionCapture:
    """Captures screen content for vision analysis."""

    def __init__(self):
        self._settings = get_settings()
        self._capture_dir = Path(self._settings.get_data_dir()) / "screenshots"
        self._capture_dir.mkdir(parents=True, exist_ok=True)

    async def capture_full_screen(self, monitor: int = 0) -> Optional[Image.Image]:
        """Capture the full screen."""
        try:
            import mss

            with mss.mss() as sct:
                if monitor >= len(sct.monitors):
                    monitor = 0

                screenshot = sct.grab(sct.monitors[monitor])
                img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")

                logger.debug(f"Captured full screen: {img.size}")
                return img

        except Exception as e:
            logger.error(f"Screen capture failed: {e}")
            return None

    async def capture_region(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
    ) -> Optional[Image.Image]:
        """Capture a specific screen region."""
        try:
            import mss

            region = {"top": y, "left": x, "width": width, "height": height}

            with mss.mss() as sct:
                screenshot = sct.grab(region)
                img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")

                logger.debug(f"Captured region: {region}")
                return img

        except Exception as e:
            logger.error(f"Region capture failed: {e}")
            return None

    async def capture_window(self, window_title: str) -> Optional[Image.Image]:
        """Capture a specific window."""
        try:
            import pygetwindow as gw

            windows = gw.getWindowsWithTitle(window_title)
            if not windows:
                logger.warning(f"Window not found: {window_title}")
                return None

            window = windows[0]

            if window.isMinimized:
                window.restore()
                window.activate()

            region = {
                "top": window.top,
                "left": window.left,
                "width": window.width,
                "height": window.height,
            }

            return await self.capture_region(**region)

        except Exception as e:
            logger.error(f"Window capture failed: {e}")
            return None

    async def save_screenshot(
        self,
        image: Image.Image,
        filename: Optional[str] = None,
    ) -> Optional[Path]:
        """Save screenshot to disk."""
        try:
            if filename is None:
                from datetime import datetime
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"screenshot_{timestamp}.png"

            filepath = self._capture_dir / filename
            image.save(filepath)

            logger.debug(f"Saved screenshot: {filepath}")
            return filepath

        except Exception as e:
            logger.error(f"Save screenshot failed: {e}")
            return None

    async def capture_and_save(self, monitor: int = 0) -> Optional[Path]:
        """Capture screen and save to disk."""
        image = await self.capture_full_screen(monitor)
        if image:
            return await self.save_screenshot(image)
        return None

    def image_to_bytes(self, image: Image.Image, format: str = "PNG") -> bytes:
        """Convert PIL Image to bytes."""
        buffer = io.BytesIO()
        image.save(buffer, format=format)
        return buffer.getvalue()

    def bytes_to_image(self, data: bytes) -> Optional[Image.Image]:
        """Convert bytes to PIL Image."""
        try:
            return Image.open(io.BytesIO(data))
        except Exception as e:
            logger.error(f"Failed to convert bytes to image: {e}")
            return None
