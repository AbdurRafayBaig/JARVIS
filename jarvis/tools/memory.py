"""Memory Tools

Registers project memory and user preference tools with the tool registry.
"""

from typing import Optional, Dict, Any
from loguru import logger

from jarvis.agent.tools import BaseTool, ToolResult, ToolRiskLevel, get_registry
from jarvis.memory.project_memory import ProjectMemory


class RememberProjectTool(BaseTool):
    """Remember or create a project context."""

    @property
    def name(self) -> str:
        return "remember_project"

    @property
    def description(self) -> str:
        return "Remember a project name, path, description, and status/context."

    @property
    def risk_level(self) -> ToolRiskLevel:
        return ToolRiskLevel.SAFE

    async def execute(
        self,
        name: str,
        path: str,
        description: Optional[str] = None,
        context: Optional[str] = None,
        **kwargs,
    ) -> ToolResult:
        try:
            mem = ProjectMemory()
            existing = await mem.get_project_by_path(path)
            meta = {"context": context} if context else {}
            if existing:
                updated = await mem.update_project(existing.id, name=name, description=description, metadata=meta)
                return ToolResult(
                    success=True,
                    data={"id": updated.id, "name": updated.name, "path": updated.path, "status": "updated"},
                )
            else:
                project = await mem.create_project(name=name, path=path, description=description, metadata=meta)
                return ToolResult(
                    success=True,
                    data={"id": project.id, "name": project.name, "path": project.path, "status": "created"},
                )
        except Exception as e:
            logger.error(f"Remember project error: {e}")
            return ToolResult(success=False, error=str(e))


class GetProjectMemoryTool(BaseTool):
    """Get project context by name or path."""

    @property
    def name(self) -> str:
        return "get_project_memory"

    @property
    def description(self) -> str:
        return "Retrieve remembered details, path, and context of a project."

    @property
    def risk_level(self) -> ToolRiskLevel:
        return ToolRiskLevel.SAFE

    async def execute(self, query: str, **kwargs) -> ToolResult:
        try:
            mem = ProjectMemory()
            projects = await mem.list_projects()
            q = query.lower()
            matched = [p for p in projects if q in p.name.lower() or q in p.path.lower()]
            if matched:
                p = matched[0]
                return ToolResult(
                    success=True,
                    data={
                        "id": p.id,
                        "name": p.name,
                        "path": p.path,
                        "description": p.description,
                        "metadata": p.metadata,
                    },
                )
            return ToolResult(success=False, error=f"No project found matching '{query}'")
        except Exception as e:
            logger.error(f"Get project memory error: {e}")
            return ToolResult(success=False, error=str(e))


class ListProjectsTool(BaseTool):
    """List all remembered projects."""

    @property
    def name(self) -> str:
        return "list_projects"

    @property
    def description(self) -> str:
        return "List all projects saved in JARVIS memory."

    @property
    def risk_level(self) -> ToolRiskLevel:
        return ToolRiskLevel.SAFE

    async def execute(self, **kwargs) -> ToolResult:
        try:
            mem = ProjectMemory()
            projects = await mem.list_projects()
            items = [{"id": p.id, "name": p.name, "path": p.path, "description": p.description} for p in projects]
            return ToolResult(success=True, data={"projects": items, "count": len(items)})
        except Exception as e:
            logger.error(f"List projects error: {e}")
            return ToolResult(success=False, error=str(e))


class SetPreferenceTool(BaseTool):
    """Set a user preference."""

    @property
    def name(self) -> str:
        return "set_preference"

    @property
    def description(self) -> str:
        return "Set a user preference key-value pair."

    @property
    def risk_level(self) -> ToolRiskLevel:
        return ToolRiskLevel.SAFE

    async def execute(self, key: str, value: str, **kwargs) -> ToolResult:
        try:
            mem = ProjectMemory()
            pref = await mem.set_preference(key, value)
            return ToolResult(success=True, data={"key": pref.key, "value": pref.value})
        except Exception as e:
            logger.error(f"Set preference error: {e}")
            return ToolResult(success=False, error=str(e))


class GetPreferenceTool(BaseTool):
    """Get a user preference."""

    @property
    def name(self) -> str:
        return "get_preference"

    @property
    def description(self) -> str:
        return "Get a user preference value by key."

    @property
    def risk_level(self) -> ToolRiskLevel:
        return ToolRiskLevel.SAFE

    async def execute(self, key: str, **kwargs) -> ToolResult:
        try:
            mem = ProjectMemory()
            val = await mem.get_preference(key)
            if val is not None:
                return ToolResult(success=True, data={"key": key, "value": val})
            return ToolResult(success=False, error=f"Preference '{key}' not found")
        except Exception as e:
            logger.error(f"Get preference error: {e}")
            return ToolResult(success=False, error=str(e))


def register_memory_tools() -> None:
    """Register all memory tools."""
    registry = get_registry()

    tools = [
        RememberProjectTool(),
        GetProjectMemoryTool(),
        ListProjectsTool(),
        SetPreferenceTool(),
        GetPreferenceTool(),
    ]

    for tool in tools:
        registry.register(tool, category="general")

    logger.info(f"Registered {len(tools)} memory tools")
