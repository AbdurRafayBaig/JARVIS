import json
import re
import time
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
    # Who produced the plan: "llm", "router" (direct command, no model used)
    # or "fallback" (the model was needed but unavailable).
    source: str = "llm"


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
        fallback_to_simple: bool = True,
    ):
        self.llm = llm_client
        self.tools = tool_registry or get_registry()
        self.max_steps = max_steps
        self.fallback_to_simple = fallback_to_simple

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
            if not self.fallback_to_simple:
                raise
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
    """Planner that needs no language model.

    Direct computer commands are recognised by the intent router. Anything
    else gets a plain answer that the language model is required, rather
    than a pretend acknowledgement.
    """

    def __init__(self, tool_registry: Optional[ToolRegistry] = None):
        self.tools = tool_registry or get_registry()

    def _mark_approvals(self, steps: list[TaskStep]) -> list[TaskStep]:
        """Carry each tool's approval requirement onto its step."""
        for step in steps:
            tool = self.tools.get(step.tool_name)
            step.requires_approval = tool.requires_approval if tool else False
        return steps

    def route(self, goal: str) -> Optional[Plan]:
        """Plan for a direct command, or None when the goal is not one."""
        from jarvis.agent.intent_router import get_intent_router

        steps = get_intent_router().route(goal)
        if not steps:
            return None
        return Plan(
            steps=self._mark_approvals(steps),
            reasoning="Direct command",
            estimated_duration=5.0 * len(steps),
            source="router",
        )

    async def plan(self, goal: str, context: dict[str, Any]) -> Plan:
        """Plan a direct command, or explain that the model is needed."""
        routed = self.route(goal)
        if routed is not None:
            return routed

        message = (
            f'I can\'t work out how to do "{goal}" without my language model, which '
            f"is unavailable right now. Check LLM_API_KEY and your provider\'s billing, "
            f"or set LLM_PROVIDER=ollama to run locally. Direct commands still work - "
            f'say "help" to see them.'
        )
        return Plan(
            steps=[TaskStep(
                description="Explain that the request needs the language model",
                tool_name="respond",
                tool_args={"message": message},
            )],
            reasoning="Not a direct command and no LLM is available",
            estimated_duration=1.0,
            source="fallback",
        )

    async def replan(self, task: Task, failed_step: TaskStep, error: str) -> Plan:
        """Retry the failed step once; there is no smarter recovery here."""
        if failed_step.retry_count <= 1 and failed_step.tool_name != "respond":
            remaining = task.steps[task.current_step_index + 1:]
            retry = TaskStep(
                description=failed_step.description,
                tool_name=failed_step.tool_name,
                tool_args=failed_step.tool_args,
                requires_approval=False if failed_step.approved else failed_step.requires_approval,
            )
            return Plan(
                steps=[retry] + remaining,
                reasoning="Retrying failed step",
                estimated_duration=10.0,
                source="router",
            )
        return Plan(steps=[], reasoning="Max retries exceeded", source="router")


class HybridPlanner(BasePlanner):
    """Direct commands first, the language model for everything else.

    "Open chrome" should not cost an API call or wait on one. The intent
    router answers such commands instantly; goals it does not fully
    understand go to the LLM. When the LLM fails (no credits, no network),
    it is left alone for a while so later requests fail fast instead of
    each waiting through the same retries.
    """

    LLM_COOLDOWN_SECONDS = 300

    def __init__(self, llm_planner: Optional[LLMPlanner], tool_registry: Optional[ToolRegistry] = None):
        self.llm_planner = llm_planner
        if llm_planner is not None:
            llm_planner.fallback_to_simple = False
        self.simple = SimplePlanner(tool_registry)
        self._llm_down_until = 0.0

    @property
    def llm_available(self) -> bool:
        return self.llm_planner is not None and time.monotonic() >= self._llm_down_until

    def _mark_llm_down(self) -> None:
        self._llm_down_until = time.monotonic() + self.LLM_COOLDOWN_SECONDS

    async def plan(self, goal: str, context: dict[str, Any]) -> Plan:
        routed = self.simple.route(goal)
        if routed is not None:
            return routed

        if self.llm_available:
            try:
                return await self.llm_planner.plan(goal, context)
            except Exception as e:
                logger.error(f"LLM planning failed: {e}")
                self._mark_llm_down()

        return await self.simple.plan(goal, context)

    async def replan(self, task: Task, failed_step: TaskStep, error: str) -> Plan:
        if task.metadata.get("plan_source") == "llm" and self.llm_available:
            try:
                return await self.llm_planner.replan(task, failed_step, error)
            except Exception as e:
                logger.error(f"LLM replanning failed: {e}")
                self._mark_llm_down()
                return Plan(steps=[], reasoning="LLM unavailable for recovery")

        return await self.simple.replan(task, failed_step, error)
