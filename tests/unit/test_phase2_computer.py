"""JARVIS - Phase 2 Computer Tools Tests"""

import pytest
import asyncio
from unittest.mock import patch, MagicMock

from jarvis.tools.computer import (
    ClickMouseTool,
    MoveMouseTool,
    ScrollMouseTool,
    TypeTextTool,
    PressKeyTool,
    HotkeyTool,
    WindowActionTool,
    GetClipboardTool,
    SetClipboardTool,
    ListProcessesTool,
)


@pytest.mark.asyncio
async def test_click_mouse_tool():
    tool = ClickMouseTool()
    with patch("pyautogui.click") as mock_click:
        result = await tool.execute(x=100, y=200, button="left")
        assert result.success is True
        mock_click.assert_called_once_with(x=100, y=200, button="left", clicks=1)


@pytest.mark.asyncio
async def test_move_mouse_tool():
    tool = MoveMouseTool()
    with patch("pyautogui.moveTo") as mock_move:
        result = await tool.execute(x=300, y=400)
        assert result.success is True
        mock_move.assert_called_once_with(x=300, y=400, duration=0.2)


@pytest.mark.asyncio
async def test_scroll_mouse_tool():
    tool = ScrollMouseTool()
    with patch("pyautogui.scroll") as mock_scroll:
        result = await tool.execute(amount=500)
        assert result.success is True
        mock_scroll.assert_called_once_with(500)


@pytest.mark.asyncio
async def test_type_text_tool():
    tool = TypeTextTool()
    with patch("pyautogui.write") as mock_write, patch("pyautogui.press") as mock_press:
        result = await tool.execute(text="Hello World", press_enter=True)
        assert result.success is True
        mock_write.assert_called_once_with("Hello World", interval=0.02)
        mock_press.assert_called_once_with("enter")


@pytest.mark.asyncio
async def test_press_key_tool():
    tool = PressKeyTool()
    with patch("pyautogui.press") as mock_press:
        result = await tool.execute(key="esc")
        assert result.success is True
        mock_press.assert_called_once_with("esc", presses=1)


@pytest.mark.asyncio
async def test_hotkey_tool():
    tool = HotkeyTool()
    with patch("pyautogui.hotkey") as mock_hotkey:
        result = await tool.execute(keys=["ctrl", "c"])
        assert result.success is True
        mock_hotkey.assert_called_once_with("ctrl", "c")


@pytest.mark.asyncio
async def test_list_processes_tool():
    tool = ListProcessesTool()
    result = await tool.execute(limit=5)
    assert result.success is True
    assert "processes" in result.data
    assert isinstance(result.data["processes"], list)
