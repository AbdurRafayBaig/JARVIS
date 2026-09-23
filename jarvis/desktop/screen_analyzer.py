"""Screen Analyzer

Analyzes screen content using vision-capable LLMs.
"""

import base64
from typing import Optional
from loguru import logger

from jarvis.core.config import get_settings
from jarvis.desktop.vision import VisionCapture


class ScreenAnalyzer:
    """Analyzes screen content using vision LLMs."""

    def __init__(self):
        self._settings = get_settings()
        self._capture = VisionCapture()

    async def analyze_screen(
        self,
        question: str = "Describe what you see on the screen",
        monitor: int = 0,
    ) -> Optional[str]:
        """Analyze current screen content."""
        image = await self._capture.capture_full_screen(monitor)
        if not image:
            return None

        return await self.analyze_image(image, question)

    async def analyze_image(
        self,
        image,
        question: str = "Describe this image",
    ) -> Optional[str]:
        """Analyze an image using vision LLM."""
        try:
            from jarvis.llm.manager import get_llm_manager

            manager = get_llm_manager()
            provider = manager.get_provider()

            image_bytes = self._capture.image_to_bytes(image)
            image_b64 = base64.b64encode(image_bytes).decode()

            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": question},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{image_b64}",
                            },
                        },
                    ],
                }
            ]

            response = await provider.chat(messages)
            return response.content

        except Exception as e:
            logger.error(f"Image analysis failed: {e}")
            return None

    async def find_text_on_screen(
        self,
        text: str,
        monitor: int = 0,
    ) -> Optional[dict]:
        """Find specific text on screen."""
        image = await self._capture.capture_full_screen(monitor)
        if not image:
            return None

        question = f"Find the text '{text}' on the screen. Return its approximate position as x,y coordinates and the bounding box. If not found, say 'not found'."

        response = await self.analyze_image(image, question)
        return {"text": text, "analysis": response}

    async def describe_ui_elements(self, monitor: int = 0) -> Optional[str]:
        """Describe UI elements on screen."""
        image = await self._capture.capture_full_screen(monitor)
        if not image:
            return None

        question = (
            "Describe all visible UI elements on this screen. "
            "Include buttons, text fields, menus, windows, and any interactive elements. "
            "For each element, describe its approximate location and what it appears to do."
        )

        return await self.analyze_image(image, question)

    async def suggest_actions(self, task: str, monitor: int = 0) -> Optional[str]:
        """Suggest actions to complete a task based on screen state."""
        image = await self._capture.capture_full_screen(monitor)
        if not image:
            return None

        question = (
            f"I want to {task}. Based on what you see on the screen, "
            "suggest the steps I should take. Include specific UI elements to interact with "
            "and their approximate positions."
        )

        return await self.analyze_image(image, question)

    async def compare_screens(
        self,
        before_image,
        after_image,
        question: str = "What changed between these two screenshots?",
    ) -> Optional[str]:
        """Compare two screenshots."""
        try:
            from jarvis.llm.manager import get_llm_manager

            manager = get_llm_manager()
            provider = manager.get_provider()

            before_bytes = self._capture.image_to_bytes(before_image)
            after_bytes = self._capture.image_to_bytes(after_image)

            before_b64 = base64.b64encode(before_bytes).decode()
            after_b64 = base64.b64encode(after_bytes).decode()

            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": f"Before image:\n"},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{before_b64}"},
                        },
                        {"type": "text", "text": f"\nAfter image:\n"},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{after_b64}"},
                        },
                        {"type": "text", "text": f"\n{question}"},
                    ],
                }
            ]

            response = await provider.chat(messages)
            return response.content

        except Exception as e:
            logger.error(f"Screen comparison failed: {e}")
            return None
