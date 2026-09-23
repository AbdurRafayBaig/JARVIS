import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional

from jarvis.agent.task import Task, TaskStep, TaskStatus, StepStatus
from jarvis.agent.tools import ToolRegistry, get_registry, ToolSchema
from jarvis.llm.providers import Message
from jarvis.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class Plan:
    """Execution plan for a task."""
    steps: list[TaskStep]
    reasoning: str = ""
    estimated_duration: float = 0.0


class BasePlanner(ABC):
    """Base planner interface."""

    @abstractmethod
    async def plan(self, goal: str, context: dict[str, Any]) -> Plan:
        """Create a plan for the given goal."""
        pass

    @abstractmethod
    async def replan(self, task: Task, failed_step: TaskStep, error: str) -> Plan:
        """Create a new plan after a step failure."""
        pass


class LLMPlanner(BasePlanner):
    """LLM-based planner."""

    def __init__(
        self,
        llm_client: Any,
        tool_registry: Optional[ToolRegistry] = None,
        max_steps: int = 30,
    ):
        self.llm = llm_client
        self.tools = tool_registry or get_registry()
        self.max_steps = max_steps

    def _build_system_prompt(self) -> str:
        """Build system prompt with available tools."""
        tool_schemas = self.tools.get_openai_schemas()
        tools_json = json.dumps(tool_schemas, indent=2)

        return f"""You are JARVIS, a personal AI computer agent. Your job is to create execution plans for user goals.

Available Tools:
{tools_json}

Planning Rules:
1. Break down the goal into discrete, executable steps
2. Each step must use exactly ONE tool, named exactly as listed above
3. Steps should be ordered logically with dependencies respected
4. Mark steps that modify system state as requiring approval (risk_level: sensitive/dangerous)
5. Maximum {self.max_steps} steps per plan
6. Include reasoning for the plan
7. Output ONLY valid JSON matching the Plan schema, wrapped in standard JSON or markdown json fence
8. If the goal is conversational (a question, a greeting, a request for information
   you already have), plan a single "respond" step rather than inventing tool calls

Referring to earlier results:
You are writing the whole plan before anything runs, so you cannot know a value
that only exists after an earlier step executes. Reference it with a placeholder
instead, and it will be substituted at execution time:
  {{{{step_1.result}}}}      the result of step 1 (steps are numbered from 1)
  {{{{step_2}}}}             shorthand for {{{{step_2.result}}}}
  {{{{previous.result}}}}    the result of the immediately preceding step
  {{{{step_1.result.url}}}}  the "url" key, when that result is an object
Use these instead of guessing a path, URL or file content you have not seen yet.

Output Format:
{{
  "reasoning": "High-level explanation of the approach",
  "estimated_duration": 120.0,
  "steps": [
    {{
      "description": "What this step does",
      "tool_name": "exact_tool_name",
      "tool_args": {{"arg1": "value1"}},
      "requires_approval": false
    }}
  ]
}}"""

    def _extract_json(self, text: str) -> str:
        """Extract JSON from response text."""
        text = text.strip()
        # Check for ```json ... ``` code fence
        json_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
        if json_match:
            return json_match.group(1).strip()
        return text

    async def plan(self, goal: str, context: dict[str, Any]) -> Plan:
        """Create a plan using the LLM."""
        system_prompt = self._build_system_prompt()

        # The tool schemas are already in the system prompt; repeating the
        # registry here would double the prompt size for no gain.
        trimmed = {k: v for k, v in context.items() if k != "available_tools" and v}
        context_str = json.dumps(trimmed, indent=2, default=str)

        user_prompt = f"""Goal: {goal}

Current Context:
{context_str}

Create a plan to achieve this goal."""

        try:
            messages = [
                Message(role="system", content=system_prompt),
                Message(role="user", content=user_prompt),
            ]
            response = await self.llm.chat_completion(messages)

            raw_content = response.content or ""
            json_str = self._extract_json(raw_content)
            plan_data = json.loads(json_str)

            steps = []
            for i, step_data in enumerate(plan_data.get("steps", [])):
                tool_name = step_data.get("tool_name")
                tool = self.tools.get(tool_name)
                if not tool:
                    logger.warning(f"Unknown tool in plan: {tool_name}")
                    continue

                step = TaskStep(
                    description=step_data.get("description", ""),
                    tool_name=tool_name,
                    tool_args=step_data.get("tool_args", {}),
                    requires_approval=step_data.get("requires_approval", tool.requires_approval),
                )
                steps.append(step)

            return Plan(
                steps=steps,
                reasoning=plan_data.get("reasoning", ""),
                estimated_duration=plan_data.get("estimated_duration", 0.0),
            )

        except Exception as e:
            logger.error(f"LLM planning failed: {e}. Falling back to SimplePlanner.")
            try:
                fallback_planner = SimplePlanner(self.tools)
                return await fallback_planner.plan(goal, context)
            except Exception as fallback_err:
                logger.error(f"Fallback planning failed: {fallback_err}")
                raise e

    async def replan(self, task: Task, failed_step: TaskStep, error: str) -> Plan:
        """Replan after a failure."""
        completed_steps = [
            {
                "description": s.description,
                "tool_name": s.tool_name,
                "result": s.result,
            }
            for s in task.steps
            if s.status == StepStatus.COMPLETED
        ]

        context = {
            "original_goal": task.goal,
            "completed_steps": completed_steps,
            "failed_step": {
                "description": failed_step.description,
                "tool_name": failed_step.tool_name,
                "error": error,
            },
            "retry_count": failed_step.retry_count,
        }

        return await self.plan(task.goal, context)


class SimplePlanner(BasePlanner):
    """Simple rule-based planner for basic tasks."""

    def __init__(self, tool_registry: Optional[ToolRegistry] = None):
        self.tools = tool_registry or get_registry()

    async def plan(self, goal: str, context: dict[str, Any]) -> Plan:
        """Create a simple plan based on keywords."""
        goal_lower = goal.lower()
        steps = []

        # Simple keyword-based planning
        if "open" in goal_lower and ("vscode" in goal_lower or "visual studio" in goal_lower):
            steps.append(TaskStep(
                description="Open Visual Studio Code",
                tool_name="open_application",
                tool_args={"app_name": "Visual Studio Code"},
            ))

        elif "create" in goal_lower and ("folder" in goal_lower or "directory" in goal_lower):
            # Extract folder name - simplified
            steps.append(TaskStep(
                description="Create directory",
                tool_name="create_directory",
                tool_args={"path": "NewFolder"},
            ))

        elif "run" in goal_lower and ("test" in goal_lower or "pytest" in goal_lower):
            steps.append(TaskStep(
                description="Run tests",
                tool_name="run_tests",
                tool_args={},
            ))

        if not steps:
            # Default: just acknowledge
            steps.append(TaskStep(
                description="Acknowledge request",
                tool_name="respond",
                tool_args={"message": f"I'll help with: {goal}"},
            ))

        return Plan(
            steps=steps,
            reasoning="Simple keyword-based plan",
            estimated_duration=30.0,
        )

    async def replan(self, task: Task, failed_step: TaskStep, error: str) -> Plan:
        """Simple replan - just retry once."""
        if failed_step.retry_count < 1:
            return Plan(
                steps=[TaskStep(
                    description=f"Retry: {failed_step.description}",
                    tool_name=failed_step.tool_name,
                    tool_args=failed_step.tool_args,
                    requires_approval=failed_step.requires_approval,
                )],
                reasoning="Retrying failed step",
                estimated_duration=10.0,
            )
        return Plan(steps=[], reasoning="Max retries exceeded")