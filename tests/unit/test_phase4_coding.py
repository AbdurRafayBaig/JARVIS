"""JARVIS - Phase 4 Coding & File Tools Tests"""

import pytest
from pathlib import Path

from jarvis.tools.coding import (
    FileEditTool,
    FileTreeTool,
    GrepSearchTool,
    AnalyzeCodeErrorTool,
)


@pytest.mark.asyncio
async def test_file_edit_tool(tmp_path):
    test_file = tmp_path / "test.txt"
    test_file.write_text("Hello World\nLine 2", encoding="utf-8")

    tool = FileEditTool()
    result = await tool.execute(path=str(test_file), target="World", replacement="JARVIS")

    assert result.success is True
    assert test_file.read_text(encoding="utf-8") == "Hello JARVIS\nLine 2"


@pytest.mark.asyncio
async def test_file_tree_tool(tmp_path):
    (tmp_path / "sub1").mkdir()
    (tmp_path / "sub1" / "a.py").write_text("print(1)")
    (tmp_path / "b.txt").write_text("hello")

    tool = FileTreeTool()
    result = await tool.execute(path=str(tmp_path), max_depth=2)

    assert result.success is True
    assert "sub1" in result.data["tree"]
    assert "b.txt" in result.data["tree"]


@pytest.mark.asyncio
async def test_grep_search_tool(tmp_path):
    (tmp_path / "sample.py").write_text("def jarvis_func():\n    return 'awesome'")

    tool = GrepSearchTool()
    result = await tool.execute(query="jarvis_func", path=str(tmp_path))

    assert result.success is True
    assert len(result.data["matches"]) == 1
    assert result.data["matches"][0]["file"] == "sample.py"


@pytest.mark.asyncio
async def test_analyze_code_error_tool():
    error_log = "Traceback (most recent call last):\n  File 'app.py', line 10\nValueError: Invalid number"

    tool = AnalyzeCodeErrorTool()
    result = await tool.execute(error_text=error_log)

    assert result.success is True
    assert "ValueError: Invalid number" in result.data["error_summary"]
