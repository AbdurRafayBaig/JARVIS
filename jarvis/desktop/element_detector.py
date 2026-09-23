"""Element Detector

Locates UI elements for precise mouse/keyboard actions.
"""

from typing import Optional
from dataclasses import dataclass
from loguru import logger

from jarvis.desktop.vision import VisionCapture
from jarvis.desktop.screen_analyzer import ScreenAnalyzer


@dataclass
class UIElement:
    """Represents a detected UI element."""
    name: str
    description: str
    x: int
    y: int
    width: int
    height: int
    confidence: float = 0.0


class ElementDetector:
    """Detects UI elements on screen using vision."""

    def __init__(self):
        self._capture = VisionCapture()
        self._analyzer = ScreenAnalyzer()

    async def find_element(
        self,
        description: str,
        monitor: int = 0,
    ) -> Optional[UIElement]:
        """Find a UI element by description."""
        image = await self._capture.capture_full_screen(monitor)
        if not image:
            return None

        question = (
            f"Find the '{description}' UI element on the screen. "
            "Return its position as x,y coordinates and approximate width,height. "
            "If multiple matches, return the most prominent one."
        )

        response = await self._analyzer.analyze_image(image, question)
        if not response:
            return None

        try:
            import re
            coords = re.findall(r'(\d+)', response)
            if len(coords) >= 4:
                return UIElement(
                    name=description,
                    description=response,
                    x=int(coords[0]),
                    y=int(coords[1]),
                    width=int(coords[2]),
                    height=int(coords[3]),
                    confidence=0.8,
                )
        except Exception:
            pass

        return UIElement(
            name=description,
            description=response,
            x=0,
            y=0,
            width=0,
            height=0,
            confidence=0.0,
        )

    async def find_all_elements(
        self,
        monitor: int = 0,
    ) -> list[UIElement]:
        """Find all visible UI elements."""
        image = await self._capture.capture_full_screen(monitor)
        if not image:
            return []

        question = (
            "List all visible UI elements on the screen. "
            "For each element, provide: name, description, x, y, width, height. "
            "Format as a list."
        )

        response = await self._analyzer.analyze_image(image, question)
        if not response:
            return []

        elements = []
        lines = response.split("\n")

        for line in lines:
            if ":" in line:
                parts = line.split(":", 1)
                if len(parts) == 2:
                    elements.append(UIElement(
                        name=parts[0].strip(),
                        description=parts[1].strip(),
                        x=0,
                        y=0,
                        width=0,
                        height=0,
                    ))

        return elements

    async def click_element(
        self,
        description: str,
        monitor: int = 0,
    ) -> bool:
        """Click on a UI element by description."""
        element = await self.find_element(description, monitor)
        if not element:
            return False

        try:
            import pyautogui
            pyautogui.click(element.x + element.width // 2, element.y + element.height // 2)
            logger.info(f"Clicked element: {description} at ({element.x}, {element.y})")
            return True
        except Exception as e:
            logger.error(f"Click failed: {e}")
            return False

    async def type_at_element(
        self,
        description: str,
        text: str,
        monitor: int = 0,
    ) -> bool:
        """Click element and type text."""
        clicked = await self.click_element(description, monitor)
        if not clicked:
            return False

        try:
            import pyautogui
            pyautogui.typewrite(text, interval=0.05)
            logger.info(f"Typed at element: {description}")
            return True
        except Exception as e:
            logger.error(f"Type failed: {e}")
            return False
