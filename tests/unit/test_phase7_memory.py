"""JARVIS - Phase 7 Memory Tools Tests"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from jarvis.tools.memory import (
    RememberProjectTool,
    GetProjectMemoryTool,
    ListProjectsTool,
    SetPreferenceTool,
    GetPreferenceTool,
)


@pytest.mark.asyncio
async def test_remember_project_tool():
    tool = RememberProjectTool()
    with patch("jarvis.memory.project_memory.ProjectMemory.get_project_by_path", new_callable=AsyncMock) as mock_get:
        with patch("jarvis.memory.project_memory.ProjectMemory.create_project", new_callable=AsyncMock) as mock_create:
            mock_get.return_value = None
            mock_proj = MagicMock()
            mock_proj.id = "proj-123"
            mock_proj.name = "Atlas"
            mock_proj.path = "C:/Projects/Atlas"
            mock_create.return_value = mock_proj

            result = await tool.execute(name="Atlas", path="C:/Projects/Atlas", description="Main workspace")
            assert result.success is True
            assert result.data["name"] == "Atlas"


@pytest.mark.asyncio
async def test_set_get_preference_tool():
    set_tool = SetPreferenceTool()
    get_tool = GetPreferenceTool()

    with patch("jarvis.memory.project_memory.ProjectMemory.set_preference", new_callable=AsyncMock) as mock_set:
        with patch("jarvis.memory.project_memory.ProjectMemory.get_preference", new_callable=AsyncMock) as mock_get:
            mock_pref = MagicMock()
            mock_pref.key = "main_project"
            mock_pref.value = "Atlas"
            mock_set.return_value = mock_pref
            mock_get.return_value = "Atlas"

            set_res = await set_tool.execute(key="main_project", value="Atlas")
            assert set_res.success is True
            assert set_res.data["value"] == "Atlas"

            get_res = await get_tool.execute(key="main_project")
            assert get_res.success is True
            assert get_res.data["value"] == "Atlas"
