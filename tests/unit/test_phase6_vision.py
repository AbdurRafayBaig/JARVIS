"""JARVIS - Phase 6 Vision Tools Tests"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from jarvis.tools.vision import (
    AnalyzeScreenTool,
    FindElementTool,
    ClickElementTool,
    SuggestActionsTool,
    CaptureScreenTool,
)


@pytest.mark.asyncio
async def test_analyze_screen_tool():
    tool = AnalyzeScreenTool()
    with patch("jarvis.desktop.screen_analyzer.ScreenAnalyzer.analyze_screen", new_callable=AsyncMock) as mock_analyze:
        mock_analyze.return_value = "Detected open VS Code window with error at line 42"
        result = await tool.execute(question="What is open?")
        assert result.success is True
        assert "VS Code" in result.data["analysis"]


@pytest.mark.asyncio
async def test_find_ui_element_tool():
    tool = FindElementTool()
    with patch("jarvis.desktop.element_detector.ElementDetector.find_element", new_callable=AsyncMock) as mock_find:
        mock_elem = MagicMock()
        mock_elem.name = "Submit Button"
        mock_elem.x = 120
        mock_elem.y = 340
        mock_elem.description = "Blue primary button"
        mock_find.return_value = mock_elem

        result = await tool.execute(description="Submit Button")
        assert result.success is True
        assert result.data["x"] == 120
        assert result.data["y"] == 340


@pytest.mark.asyncio
async def test_click_ui_element_tool():
    tool = ClickElementTool()
    with patch("jarvis.desktop.element_detector.ElementDetector.click_element", new_callable=AsyncMock) as mock_click:
        mock_click.return_value = True
        result = await tool.execute(description="Settings Icon")
        assert result.success is True


@pytest.mark.asyncio
async def test_capture_screen_tool(tmp_path):
    tool = CaptureScreenTool()
    with patch("jarvis.desktop.vision.VisionCapture.capture_and_save", new_callable=AsyncMock) as mock_cap:
        mock_cap.return_value = tmp_path / "screen.png"
        result = await tool.execute()
        assert result.success is True
        assert "screen.png" in result.data["path"]
