"""JARVIS - LLM & Agent Execution Tests"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock

from jarvis.agent.agent import Agent, create_agent, AgentContext
from jarvis.agent.planner import LLMPlanner, Plan
from jarvis.agent.task import Task, TaskStatus, StepStatus, TaskStep
from jarvis.agent.tools import ToolRegistry, BaseTool, ToolResult, ToolRiskLevel
from jarvis.agent.response_generator import ResponseGenerator
from jarvis.llm.providers import Message, ChatCompletionResponse


class DummyTool(BaseTool):
    @property
    def name(self) -> str:
        return "dummy_tool"

    @property
    def description(self) -> str:
        return "Dummy tool for testing"

    @property
    def risk_level(self) -> ToolRiskLevel:
        return ToolRiskLevel.SAFE

    async def execute(self, text: str = "hello") -> ToolResult:
        return ToolResult(success=True, data=f"executed {text}")


@pytest.fixture
def mock_llm():
    llm = MagicMock()
    llm.chat_completion = AsyncMock(
        return_value=ChatCompletionResponse(
            content='''```json
{
  "reasoning": "Test plan",
  "estimated_duration": 5.0,
  "steps": [
    {
      "description": "Run dummy tool",
      "tool_name": "dummy_tool",
      "tool_args": {"text": "world"},
      "requires_approval": false
    }
  ]
}
```''',
            model="gpt-4o",
            provider="openai",
        )
    )
    return llm


@pytest.mark.asyncio
async def test_llm_planner(mock_llm):
    registry = ToolRegistry()
    registry.register(DummyTool())

    planner = LLMPlanner(mock_llm, tool_registry=registry)
    plan = await planner.plan("Test goal", context={})

    assert len(plan.steps) == 1
    assert plan.steps[0].tool_name == "dummy_tool"
    assert plan.steps[0].tool_args == {"text": "world"}
    assert plan.reasoning == "Test plan"


@pytest.mark.asyncio
async def test_agent_execution_with_llm(mock_llm):
    registry = ToolRegistry()
    registry.register(DummyTool())

    planner = LLMPlanner(mock_llm, tool_registry=registry)
    agent = Agent(planner=planner, tool_registry=registry)

    task = await agent.execute_task("Run dummy tool with world")

    assert task.status == TaskStatus.COMPLETED
    assert len(task.steps) == 1
    assert task.steps[0].status == StepStatus.COMPLETED
    assert task.steps[0].result == "executed world"


@pytest.mark.asyncio
async def test_response_generator(mock_llm):
    mock_llm.chat_completion.return_value = ChatCompletionResponse(
        content="Done. Executed dummy tool successfully.",
        model="gpt-4o",
        provider="openai",
    )
    gen = ResponseGenerator(mock_llm)

    task = Task(goal="Test goal", status=TaskStatus.COMPLETED)
    task.steps = [
        TaskStep(
            description="Run dummy tool",
            tool_name="dummy_tool",
            status=StepStatus.COMPLETED,
            result="executed world",
        )
    ]

    res = await gen.generate_response(task)
    assert "Executed dummy tool successfully" in res
