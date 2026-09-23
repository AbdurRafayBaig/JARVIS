"""JARVIS - Unit Tests"""

import pytest
import asyncio
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch

from jarvis.core.config import Settings, get_settings, LLMSettings
from jarvis.core.exceptions import (
    JarvisError,
    ConfigurationError,
    ToolError,
    ToolNotFoundError,
)
from jarvis.core.logging import setup_logging, get_logger
from jarvis.agent.task import Task, TaskStep, TaskStatus, StepStatus, TaskPriority
from jarvis.agent.tools import (
    BaseTool,
    ToolSchema,
    ToolParameter,
    ToolResult,
    ToolRiskLevel,
    ToolRegistry,
    get_registry,
    register_tool,
)
from jarvis.agent.planner import SimplePlanner, Plan
from jarvis.tools.computer import (
    OpenApplicationTool,
    ListDirectoryTool,
    CreateFileTool,
    ReadFileTool,
)
from jarvis.tools.coding import (
    RunPythonTool,
    GitStatusTool,
    GitInitTool,
)


class TestConfiguration:
    """Test configuration management."""

    def test_settings_creation(self):
        """Test settings can be created."""
        settings = Settings()
        assert settings is not None
        assert settings.llm.provider == "openai"
        assert settings.agent.max_steps == 30

    def test_llm_settings(self):
        """Test LLM settings."""
        llm = LLMSettings(provider="openai", model="gpt-4o", api_key="test")
        assert llm.provider == "openai"
        assert llm.model == "gpt-4o"

    def test_get_data_dir(self, tmp_path):
        """Test data directory creation."""
        settings = Settings()
        # Mock the path
        with patch.object(settings.paths, 'data_dir', str(tmp_path / "test_data")):
            data_dir = settings.get_data_dir()
            assert data_dir.exists()

    def test_get_projects_dir(self, tmp_path):
        """Test projects directory creation."""
        settings = Settings()
        with patch.object(settings.paths, 'projects_dir', str(tmp_path / "test_projects")):
            projects_dir = settings.get_projects_dir()
            assert projects_dir.exists()


class TestExceptions:
    """Test exception hierarchy."""

    def test_jarvis_error(self):
        """Test base JarvisError."""
        error = JarvisError("Test error", code="TEST_ERROR", details={"key": "value"})
        assert error.message == "Test error"
        assert error.code == "TEST_ERROR"
        assert error.details == {"key": "value"}
        assert error.recoverable is True

    def test_tool_error(self):
        """Test ToolError with tool context."""
        error = ToolError(
            "Tool failed",
            tool_name="test_tool",
            tool_args={"arg1": "value1"},
        )
        assert error.tool_name == "test_tool"
        assert error.tool_args == {"arg1": "value1"}
        d = error.to_dict()
        assert d["tool_name"] == "test_tool"

    def test_configuration_error(self):
        """Test ConfigurationError."""
        error = ConfigurationError("Missing config")
        assert error.code == "CONFIG_ERROR"

    def test_tool_not_found_error(self):
        """Test ToolNotFoundError."""
        error = ToolNotFoundError("missing_tool")
        assert error.code == "TOOL_NOT_FOUND"
        assert error.details["tool_name"] == "missing_tool"


class TestTaskModels:
    """Test task and step models."""

    def test_task_creation(self):
        """Test task creation."""
        task = Task(goal="Test goal", priority=TaskPriority.HIGH)
        assert task.goal == "Test goal"
        assert task.priority == TaskPriority.HIGH
        assert task.status == TaskStatus.PENDING
        assert task.progress == 0.0

    def test_task_steps(self):
        """Test adding steps to task."""
        task = Task(goal="Test")
        step1 = TaskStep(description="Step 1", tool_name="tool1")
        step2 = TaskStep(description="Step 2", tool_name="tool2")
        task.steps = [step1, step2]

        assert len(task.steps) == 2
        assert task.current_step == step1
        assert task.progress == 0.0

    def test_task_progress(self):
        """Test progress calculation."""
        task = Task(goal="Test")
        step1 = TaskStep(description="Step 1", status=StepStatus.COMPLETED)
        step2 = TaskStep(description="Step 2", status=StepStatus.PENDING)
        step3 = TaskStep(description="Step 3", status=StepStatus.RUNNING)
        task.steps = [step1, step2, step3]

        assert task.progress == pytest.approx(0.333, rel=0.01)

    def test_step_to_dict(self):
        """Test step serialization."""
        step = TaskStep(
            description="Test step",
            tool_name="test_tool",
            tool_args={"key": "value"},
            status=StepStatus.COMPLETED,
        )
        d = step.to_dict()
        assert d["description"] == "Test step"
        assert d["tool_name"] == "test_tool"
        assert d["status"] == "completed"


class TestToolSystem:
    """Test tool registry and base tool."""

    def test_tool_registry(self):
        """Test tool registration."""
        registry = ToolRegistry()

        class TestTool(BaseTool):
            @property
            def name(self):
                return "test_tool"

            @property
            def description(self):
                return "A test tool"

            async def execute(self, **kwargs):
                return ToolResult(success=True, data="done")

        tool = TestTool()
        registry.register(tool, "test")

        assert registry.get("test_tool") == tool
        assert len(registry.get_all()) == 1
        assert tool in registry.get_by_category("test")

    def test_tool_schema_generation(self):
        """Test OpenAI schema generation."""
        class TestTool(BaseTool):
            @property
            def name(self):
                return "test_tool"

            @property
            def description(self):
                return "A test tool"

            async def execute(self, param1: str, param2: int = 42) -> ToolResult:
                return ToolResult(success=True)

            @property
            def risk_level(self):
                return ToolRiskLevel.SAFE

        tool = TestTool()
        schema = tool.schema.to_openai_schema()

        assert schema["type"] == "function"
        assert schema["function"]["name"] == "test_tool"
        assert "param1" in schema["function"]["parameters"]["properties"]
        assert "param2" in schema["function"]["parameters"]["properties"]
        assert "param1" in schema["function"]["parameters"]["required"]

    def test_global_registry(self):
        """Test global registry functions."""
        registry = get_registry()
        initial_count = len(registry.get_all())

        class TempTool(BaseTool):
            @property
            def name(self):
                return "temp_tool"

            @property
            def description(self):
                return "Temp"

            async def execute(self):
                return ToolResult(success=True)

        register_tool(TempTool(), "temp")
        assert len(registry.get_all()) == initial_count + 1

        # Cleanup
        registry.unregister("temp_tool")

    def test_tool_result(self):
        """Test ToolResult model."""
        result = ToolResult(success=True, data={"key": "value"}, metadata={"time": 1.0})
        assert result.success is True
        assert result.data == {"key": "value"}
        assert result.metadata == {"time": 1.0}

        error_result = ToolResult(success=False, error="Something failed")
        assert error_result.success is False
        assert error_result.error == "Something failed"


class TestPlanner:
    """Test planner."""

    @pytest.mark.asyncio
    async def test_simple_planner(self):
        """Test simple planner creates basic plan."""
        planner = SimplePlanner()
        plan = await planner.plan("open vscode", {})

        assert isinstance(plan, Plan)
        assert len(plan.steps) > 0
        assert plan.steps[0].tool_name == "open_application"

    @pytest.mark.asyncio
    async def test_simple_planner_unknown(self):
        """Test simple planner with unknown goal."""
        planner = SimplePlanner()
        plan = await planner.plan("do something completely unknown", {})

        assert len(plan.steps) == 1
        assert plan.steps[0].tool_name == "respond"


class TestComputerTools:
    """Test computer tools."""

    @pytest.mark.asyncio
    async def test_list_directory(self, tmp_path):
        """Test list directory tool."""
        # Create test files
        (tmp_path / "file1.txt").write_text("content1")
        (tmp_path / "file2.txt").write_text("content2")
        (tmp_path / "subdir").mkdir()

        tool = ListDirectoryTool()
        result = await tool.execute(path=str(tmp_path))

        assert result.success is True
        assert result.data["count"] == 3
        names = {item["name"] for item in result.data["items"]}
        assert names == {"file1.txt", "file2.txt", "subdir"}

    @pytest.mark.asyncio
    async def test_create_read_file(self, tmp_path):
        """Test create and read file tools."""
        file_path = tmp_path / "test.txt"

        # Create
        create_tool = CreateFileTool()
        result = await create_tool.execute(path=str(file_path), content="Hello World")
        assert result.success is True

        # Read
        read_tool = ReadFileTool()
        result = await read_tool.execute(path=str(file_path))
        assert result.success is True
        assert result.data["content"] == "Hello World"

    @pytest.mark.asyncio
    async def test_open_application_tool(self):
        """Test open application tool (mocked)."""
        tool = OpenApplicationTool()

        with patch('asyncio.create_subprocess_exec') as mock_exec:
            mock_proc = AsyncMock()
            mock_proc.communicate = AsyncMock(return_value=(b"", b""))
            mock_exec.return_value = mock_proc

            result = await tool.execute(app_name="notepad")
            assert result.success is True
            mock_exec.assert_called_once()


class TestCodingTools:
    """Test coding tools."""

    @pytest.mark.asyncio
    async def test_git_status_tool(self, tmp_path):
        """Test git status tool."""
        import shutil
        import subprocess
        if not shutil.which("git"):
            pytest.skip("git binary not found in PATH")
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, capture_output=True)

        tool = GitStatusTool()
        result = await tool.execute(cwd=str(tmp_path))

        assert result.success is True
        # Should have empty status for new repo


class TestAgent:
    """Test agent runtime."""

    @pytest.mark.asyncio
    async def test_agent_creation(self):
        """Test agent can be created."""
        from jarvis.agent.agent import create_agent
        from jarvis.agent.planner import SimplePlanner

        planner = SimplePlanner()
        agent = create_agent(planner=planner)

        assert agent is not None
        assert agent.max_steps == 30

    @pytest.mark.asyncio
    async def test_agent_execute_simple(self):
        """Test agent executes simple task."""
        from jarvis.agent.agent import create_agent
        from jarvis.agent.planner import SimplePlanner

        planner = SimplePlanner()
        agent = create_agent(planner=planner, max_steps=5)

        # Mock a simple tool
        class EchoTool(BaseTool):
            @property
            def name(self):
                return "respond"

            @property
            def description(self):
                return "Echo response"

            async def execute(self, message: str):
                return ToolResult(success=True, data=message)

        register_tool(EchoTool(), "test")

        task = await agent.execute_task("test message")

        # Cleanup
        get_registry().unregister("respond")


class TestLogging:
    """Test logging setup."""

    def test_setup_logging(self, tmp_path):
        """Test logging configuration."""
        log_file = tmp_path / "test.log"
        setup_logging(log_file=log_file, level="DEBUG", console=False)

        logger = get_logger("test")
        logger.info("Test message")

        # Check log file exists
        assert log_file.exists()

    def test_get_logger(self):
        """Test logger creation."""
        logger = get_logger("test.module")
        assert logger is not None


# Integration tests
class TestIntegration:
    """Integration tests."""

    @pytest.mark.asyncio
    async def test_full_flow_mock(self):
        """Test full agent flow with mocked tools."""
        from jarvis.agent.agent import create_agent
        from jarvis.agent.planner import SimplePlanner
        from jarvis.agent.tools import register_tool, get_registry

        # Register mock tools
        class MockOpenApp(BaseTool):
            @property
            def name(self): return "open_application"
            @property
            def description(self): return "Open app"
            async def execute(self, app_name: str):
                return ToolResult(success=True, data=f"Opened {app_name}")

        register_tool(MockOpenApp(), "computer")

        planner = SimplePlanner()
        agent = create_agent(planner=planner, max_steps=5)

        task = await agent.execute_task("open vscode")

        assert task.status == TaskStatus.COMPLETED
        assert len(task.steps) == 1
        assert task.steps[0].tool_name == "open_application"

        # Cleanup
        get_registry().unregister("open_application")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])