"""JARVIS - Agent recovery, step data flow, and persistence tests.

These cover the seams between the agent runtime and the storage layer, which
unit tests of each part in isolation did not reach.
"""

import pytest
import pytest_asyncio

from jarvis.agent.agent import Agent
from jarvis.agent.planner import BasePlanner, Plan
from jarvis.agent.step_context import StepContext
from jarvis.agent.task import Task, TaskStatus, StepStatus, TaskStep
from jarvis.agent.tools import ToolRegistry, BaseTool, ToolResult, ToolRiskLevel


# -- fixtures ---------------------------------------------------------------


@pytest_asyncio.fixture
async def temp_db(tmp_path):
    """Point the global database at a throwaway file and initialize it."""
    import jarvis.core.database as db_module

    original = db_module._database
    db_module._database = db_module.Database(db_path=tmp_path / "test.db")
    await db_module._database.initialize()

    yield db_module._database

    await db_module._database.close()
    db_module._database = original


class EchoTool(BaseTool):
    @property
    def name(self) -> str:
        return "echo"

    @property
    def description(self) -> str:
        return "Echoes its input"

    async def execute(self, text: str = "") -> ToolResult:
        return ToolResult(success=True, data=text)


class FlakyTool(BaseTool):
    """Fails the first time it is called, succeeds afterwards."""

    def __init__(self):
        super().__init__()
        self.calls = 0

    @property
    def name(self) -> str:
        return "flaky"

    @property
    def description(self) -> str:
        return "Fails once, then succeeds"

    async def execute(self, value: str = "") -> ToolResult:
        self.calls += 1
        if self.calls == 1:
            return ToolResult(success=False, error="transient failure")
        return ToolResult(success=True, data=f"ok:{value}")


class ScriptedPlanner(BasePlanner):
    """Returns preset plans so tests do not need an LLM."""

    def __init__(self, plan: Plan, recovery: Plan = None):
        self._plan = plan
        self._recovery = recovery
        self.replan_calls = 0

    async def plan(self, goal, context):
        return self._plan

    async def replan(self, task, failed_step, error):
        self.replan_calls += 1
        return self._recovery or Plan(steps=[], reasoning="no recovery")


# -- step context -----------------------------------------------------------


def test_step_context_resolves_positional_reference():
    ctx = StepContext()
    ctx.record(TaskStep(result="C:/projects/api"))

    assert ctx.resolve("{{step_1.result}}") == "C:/projects/api"
    assert ctx.resolve("{{step_1}}") == "C:/projects/api"
    assert ctx.resolve("{{previous.result}}") == "C:/projects/api"


def test_step_context_preserves_non_string_types():
    ctx = StepContext()
    payload = {"url": "https://example.com/repo", "id": 7}
    ctx.record(TaskStep(result=payload))

    # A placeholder filling the whole string yields the raw value...
    assert ctx.resolve("{{step_1.result}}") == payload
    # ...and a dotted path indexes into it.
    assert ctx.resolve("{{step_1.result.url}}") == "https://example.com/repo"
    # Embedded in text, it is stringified.
    assert ctx.resolve("repo at {{step_1.result.url}}") == "repo at https://example.com/repo"


def test_step_context_resolves_nested_args():
    ctx = StepContext()
    ctx.record(TaskStep(result="README.md"))

    resolved = ctx.resolve_args({"files": ["{{step_1}}", "setup.py"], "opts": {"path": "{{step_1}}"}})
    assert resolved == {"files": ["README.md", "setup.py"], "opts": {"path": "README.md"}}


def test_step_context_leaves_unknown_placeholder_intact():
    ctx = StepContext()
    assert ctx.resolve("{{step_9.result}}") == "{{step_9.result}}"


# -- agent execution --------------------------------------------------------


@pytest.mark.asyncio
async def test_step_receives_previous_step_result():
    registry = ToolRegistry()
    registry.register(EchoTool())

    plan = Plan(steps=[
        TaskStep(description="first", tool_name="echo", tool_args={"text": "hello"}),
        TaskStep(description="second", tool_name="echo", tool_args={"text": "{{step_1.result}} world"}),
    ])
    agent = Agent(planner=ScriptedPlanner(plan), tool_registry=registry)

    task = await agent.execute_task("chain the steps")

    assert task.status == TaskStatus.COMPLETED
    assert task.steps[1].result == "hello world"


@pytest.mark.asyncio
async def test_replanned_steps_actually_execute():
    """Regression: recovery replaced task.steps while the loop iterated a
    snapshot of the old list, so recovery steps were silently skipped."""
    registry = ToolRegistry()
    registry.register(EchoTool())
    flaky = FlakyTool()
    registry.register(flaky)

    plan = Plan(steps=[
        TaskStep(description="flaky step", tool_name="flaky", tool_args={"value": "a"}),
    ])
    recovery = Plan(
        steps=[
            TaskStep(description="retry flaky", tool_name="flaky", tool_args={"value": "b"}),
            TaskStep(description="follow up", tool_name="echo", tool_args={"text": "recovered"}),
        ],
        reasoning="retry after transient failure",
    )
    planner = ScriptedPlanner(plan, recovery)
    agent = Agent(planner=planner, tool_registry=registry)

    task = await agent.execute_task("run the flaky tool")

    assert planner.replan_calls == 1
    assert task.status == TaskStatus.COMPLETED
    assert flaky.calls == 2, "the replanned step never ran"
    assert task.steps[-1].result == "recovered"


@pytest.mark.asyncio
async def test_task_fails_when_recovery_yields_no_steps():
    registry = ToolRegistry()
    flaky = FlakyTool()
    registry.register(flaky)

    plan = Plan(steps=[TaskStep(description="flaky", tool_name="flaky", tool_args={"value": "a"})])
    agent = Agent(planner=ScriptedPlanner(plan, Plan(steps=[])), tool_registry=registry)

    task = await agent.execute_task("run the flaky tool")

    assert task.status == TaskStatus.FAILED
    assert "transient failure" in (task.error or "")


@pytest.mark.asyncio
async def test_step_limit_stops_runaway_recovery():
    """A recovery plan that keeps failing must not loop forever."""
    registry = ToolRegistry()

    class AlwaysFails(BaseTool):
        @property
        def name(self) -> str:
            return "always_fails"

        @property
        def description(self) -> str:
            return "Always fails"

        async def execute(self) -> ToolResult:
            return ToolResult(success=False, error="nope")

    registry.register(AlwaysFails())

    step = lambda: TaskStep(description="fail", tool_name="always_fails", tool_args={})
    planner = ScriptedPlanner(Plan(steps=[step()]), Plan(steps=[step()]))
    agent = Agent(planner=planner, tool_registry=registry, max_steps=5, max_retries=100)

    task = await agent.execute_task("keep failing")

    assert task.status == TaskStatus.FAILED
    assert "Step limit" in (task.error or "")


# -- persistence ------------------------------------------------------------


@pytest.mark.asyncio
async def test_task_is_persisted_with_steps(temp_db):
    from jarvis.memory.task_store import get_task_store

    registry = ToolRegistry()
    registry.register(EchoTool())

    plan = Plan(steps=[
        TaskStep(description="say hi", tool_name="echo", tool_args={"text": "hi"}),
    ])
    agent = Agent(planner=ScriptedPlanner(plan), tool_registry=registry)

    task = await agent.execute_task("say hi")

    store = get_task_store()
    stored = await store.get_task(task.id)
    assert stored is not None
    assert stored.goal == "say hi"

    steps = await store.get_steps(task.id)
    assert len(steps) == 1
    assert steps[0].tool_name == "echo"
    assert steps[0].step_number == 1

    stats = await store.get_stats()
    assert stats["total"] == 1
    assert stats["completed"] == 1


@pytest.mark.asyncio
async def test_conversation_is_recorded(temp_db):
    from jarvis.memory.conversation_memory import ConversationMemory

    registry = ToolRegistry()
    registry.register(EchoTool())

    plan = Plan(steps=[TaskStep(description="echo", tool_name="echo", tool_args={"text": "hi"})])
    agent = Agent(planner=ScriptedPlanner(plan), tool_registry=registry)

    await agent.execute_task("remember this")

    history = await ConversationMemory().get_recent(count=10)
    roles = [m.role for m in history]
    assert "user" in roles
    assert any(m.content == "remember this" for m in history)


@pytest.mark.asyncio
async def test_tool_calls_are_audited(temp_db):
    from jarvis.security.audit import get_audit_logger

    registry = ToolRegistry()
    registry.register(EchoTool())

    plan = Plan(steps=[TaskStep(description="echo", tool_name="echo", tool_args={"text": "hi"})])
    agent = Agent(planner=ScriptedPlanner(plan), tool_registry=registry)

    task = await agent.execute_task("audit me")

    logs = await get_audit_logger().get_recent_logs(task_id=task.id)
    assert len(logs) == 1
    assert logs[0].tool_name == "echo"
    assert logs[0].error is None
    assert logs[0].duration_ms is not None


@pytest.mark.asyncio
async def test_conversation_memory_round_trip(temp_db):
    """Regression: store() omitted the NOT NULL session_id and passed a
    reserved `metadata` kwarg, so every write raised."""
    from jarvis.memory.conversation_memory import ConversationMemory

    memory = ConversationMemory()
    stored = await memory.store("user", "hello", metadata={"source": "test"})

    assert stored is not None
    assert stored.session_id
    assert stored.task_metadata == {"source": "test"}

    found = await memory.search("hello")
    assert len(found) == 1


@pytest.mark.asyncio
async def test_audit_logger_writes_rows(temp_db):
    """Regression: AuditLogger wrote columns (action/details/status) that do
    not exist on the model, so every write failed silently."""
    from jarvis.security.audit import get_audit_logger

    audit = get_audit_logger()
    await audit.log_tool_execution(
        tool_name="run_command",
        tool_args={"command": "dir"},
        result="ok",
        success=True,
        duration=0.25,
        risk_level="sensitive",
    )

    logs = await audit.get_recent_logs()
    assert len(logs) == 1
    assert logs[0].tool_name == "run_command"
    assert logs[0].duration_ms == pytest.approx(250.0)

    stats = await audit.get_stats()
    assert stats["total"] == 1
    assert stats["failed"] == 0


@pytest.mark.asyncio
async def test_project_metadata_is_stored(temp_db):
    """Regression: create_project passed `metadata=`, which SQLAlchemy
    shadowed instead of persisting."""
    from jarvis.memory.project_memory import ProjectMemory

    memory = ProjectMemory()
    await memory.create_project("demo", "C:/demo", metadata={"language": "python"})

    project = await memory.get_project_by_path("C:/demo")
    assert project is not None
    assert project.task_metadata == {"language": "python"}
