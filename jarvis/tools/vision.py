"""Vision Tools

Registers screen analysis tools with the tool registry.
"""

from typing import Optional
from loguru import logger

from jarvis.agent.tools import BaseTool, ToolResult, ToolRiskLevel, get_registry


class AnalyzeScreenTool(BaseTool):
    """Analyze current screen content."""

    @property
    def name(self) -> str:
        return "analyze_screen"

    @property
    def description(self) -> str:
        return "Analyze the current screen and describe what you see"

    @property
    def risk_level(self) -> ToolRiskLevel:
        return ToolRiskLevel.SAFE

    async def execute(self, question: str = "Describe what you see", **kwargs) -> ToolResult:
        """Analyze current screen content.

        Args:
            question: What to determine about what is currently on screen.
        """
        try:
            from jarvis.desktop.screen_analyzer import ScreenAnalyzer
            analyzer = ScreenAnalyzer()
            result = await analyzer.analyze_screen(question)
            if result:
                return ToolResult(success=True, data={"analysis": result})
            return ToolResult(success=False, error="Failed to analyze screen")
        except Exception as e:
            logger.error(f"Analyze screen error: {e}")
            return ToolResult(success=False, error=str(e))


class FindElementTool(BaseTool):
    """Find a UI element on screen."""

    @property
    def name(self) -> str:
        return "find_ui_element"

    @property
    def description(self) -> str:
        return "Find a specific UI element on the screen"

    @property
    def risk_level(self) -> ToolRiskLevel:
        return ToolRiskLevel.SAFE

    async def execute(self, description: str, **kwargs) -> ToolResult:
        """Find a UI element on screen.

        Args:
            description: Plain description of the element to locate, e.g. 'the blue
                Save button'.
        """
        try:
            from jarvis.desktop.element_detector import ElementDetector
            detector = ElementDetector()
            element = await detector.find_element(description)
            if element:
                return ToolResult(
                    success=True,
                    data={
                        "name": getattr(element, "name", description),
                        "x": getattr(element, "x", 0),
                        "y": getattr(element, "y", 0),
                        "description": getattr(element, "description", ""),
                    },
                )
            return ToolResult(success=False, error=f"Element '{description}' not found")
        except Exception as e:
            logger.error(f"Find element error: {e}")
            return ToolResult(success=False, error=str(e))


class ClickElementTool(BaseTool):
    """Click a UI element by description."""

    @property
    def name(self) -> str:
        return "click_ui_element"

    @property
    def description(self) -> str:
        return "Find and click a UI element by description"

    @property
    def risk_level(self) -> ToolRiskLevel:
        return ToolRiskLevel.SENSITIVE

    async def execute(self, description: str, **kwargs) -> ToolResult:
        """Click a UI element by description.

        Args:
            description: Plain description of the on-screen element to click, e.g. 'the
                Close button'.
        """
        try:
            from jarvis.desktop.element_detector import ElementDetector
            detector = ElementDetector()
            success = await detector.click_element(description)
            if success:
                return ToolResult(success=True, data=f"Clicked '{description}'")
            return ToolResult(success=False, error=f"Failed to click '{description}'")
        except Exception as e:
            logger.error(f"Click element error: {e}")
            return ToolResult(success=False, error=str(e))


class SuggestActionsTool(BaseTool):
    """Suggest actions based on screen state."""

    @property
    def name(self) -> str:
        return "suggest_actions"

    @property
    def description(self) -> str:
        return "Suggest actions to complete a task based on current screen"

    @property
    def risk_level(self) -> ToolRiskLevel:
        return ToolRiskLevel.SAFE

    async def execute(self, task: str, **kwargs) -> ToolResult:
        """Suggest actions based on screen state.

        Args:
            task: What the user is trying to accomplish on the current screen.
        """
        try:
            from jarvis.desktop.screen_analyzer import ScreenAnalyzer
            analyzer = ScreenAnalyzer()
            result = await analyzer.suggest_actions(task)
            if result:
                return ToolResult(success=True, data={"suggestions": result})
            return ToolResult(success=False, error="Failed to suggest actions")
        except Exception as e:
            logger.error(f"Suggest actions error: {e}")
            return ToolResult(success=False, error=str(e))


class CaptureScreenTool(BaseTool):
    """Capture and save a screenshot."""

    @property
    def name(self) -> str:
        return "capture_screen"

    @property
    def description(self) -> str:
        return "Capture a screenshot and save it"

    @property
    def risk_level(self) -> ToolRiskLevel:
        return ToolRiskLevel.SAFE

    async def execute(self, filename: Optional[str] = None, **kwargs) -> ToolResult:
        """Capture and save a screenshot.

        Args:
            filename: Where to save the capture. Omit to keep it in memory only.
        """
        try:
            from jarvis.desktop.vision import VisionCapture
            capture = VisionCapture()
            path = await capture.capture_and_save()
            if path:
                return ToolResult(success=True, data={"path": str(path)})
            return ToolResult(success=False, error="Failed to capture screenshot")
        except Exception as e:
            logger.error(f"Capture screen error: {e}")
            return ToolResult(success=False, error=str(e))


def register_vision_tools() -> None:
    """Register all vision tools."""
    registry = get_registry()

    tools = [
        AnalyzeScreenTool(),
        FindElementTool(),
        ClickElementTool(),
        SuggestActionsTool(),
        CaptureScreenTool(),
    ]

    for tool in tools:
        registry.register(tool, category="general")

    logger.info(f"Registered {len(tools)} vision tools")

