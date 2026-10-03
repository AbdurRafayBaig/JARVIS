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
    """Rule-based planner used when no LLM is available.

    This is the degraded path -- it runs when the LLM provider is
    unreachable, out of quota, or unconfigured. It cannot decompose a goal,
    but it can recognise common single-tool requests so that JARVIS still
    does something useful rather than only echoing the request back.
    """

    # Each rule is (required keywords, any-of keywords, tool, argument builder).
    # The first rule whose keywords all appear in the goal wins.
    _RULES: list[tuple[list[str], list[str], str]] = [
        (["time"], ["what", "current", "tell", "now"], "get_current_time"),
        (["date"], ["what", "current", "tell", "today"], "get_current_time"),
        (["system"], ["info", "spec", "status"], "get_system_info"),
        (["cpu"], [], "get_system_info"),
        (["memory"], ["usage", "ram", "much"], "get_system_info"),
        (["screenshot"], [], "take_screenshot"),
        (["screen"], ["capture", "shot", "grab"], "take_screenshot"),
        (["window"], ["list", "open", "which", "show"], "list_windows"),
        (["process"], ["list", "running", "show", "which"], "list_processes"),
        (["clipboard"], ["read", "get", "what"], "get_clipboard"),
        (["test"], ["run", "execute"], "run_tests"),
        (["pytest"], [], "run_tests"),
        (["git"], ["status"], "git_status"),
        (["project"], ["list", "show", "which"], "list_projects"),
    ]

    # Applications recognised by name in an "open X" request.
    _APPS = {
        "vs code": "Visual Studio Code",
        "vscode": "Visual Studio Code",
        "visual studio code": "Visual Studio Code",
        "notepad": "Notepad",
        "chrome": "Chrome",
        "edge": "Edge",
        "firefox": "Firefox",
        "explorer": "File Explorer",
        "calculator": "Calculator",
        "terminal": "Windows Terminal",
        "powershell": "PowerShell",
        "cmd": "Command Prompt",
        "spotify": "Spotify",
        "word": "Word",
        "excel": "Excel",
    }

    def __init__(self, tool_registry: Optional[ToolRegistry] = None):
        self.tools = tool_registry or get_registry()

    def _step(self, description: str, tool_name: str, **args) -> TaskStep:
        """Build a step. A tool missing from the registry is reported by the
        agent when the step runs, so planning does not depend on it."""
        tool = self.tools.get(tool_name)
        return TaskStep(
            description=description,
            tool_name=tool_name,
            tool_args=args,
            requires_approval=tool.requires_approval if tool else False,
        )

    def _match_application(self, goal: str) -> Optional[str]:
        """Find a known application named in an 'open ...' request."""
        for keyword, app in self._APPS.items():
            if keyword in goal:
                return app
        return None

    async def plan(self, goal: str, context: dict[str, Any]) -> Plan:
        """Create a plan by matching the goal against known request shapes."""
        goal_lower = goal.lower()
        step: Optional[TaskStep] = None
        reasoning = "Keyword-matched plan (no LLM available)"

        # "open <application>"
        if any(word in goal_lower for word in ("open", "launch", "start", "run")):
            app = self._match_application(goal_lower)
            if app:
                step = self._step(f"Open {app}", "open_application", app_name=app)

        # Single-tool keyword rules
        if step is None:
            for required, any_of, tool_name in self._RULES:
                if not all(word in goal_lower for word in required):
                    continue
                if any_of and not any(word in goal_lower for word in any_of):
                    continue
                step = self._step(f"Run {tool_name}", tool_name)
                if step is not None:
                    break

        if step is not None:
            return Plan(steps=[step], reasoning=reasoning, estimated_duration=10.0)

        # Nothing matched: say so plainly rather than implying work was done.
        fallback = self._step(
            "Explain that the request needs the language model",
            "respond",
            message=(
                f"I can't plan \"{goal}\" without my language model, which is "
                f"currently unavailable. Check LLM_API_KEY and the provider's "
                f"status, or set LLM_PROVIDER=ollama to run locally."
            ),
        )
        steps = [fallback] if fallback else []
        return Plan(
            steps=steps,
            reasoning="No keyword rule matched and no LLM is available",
            estimated_duration=1.0,
        )

    async def replan(self, task: Task, failed_step: TaskStep, error: str) -> Plan:
        """Retry the failed step once; there is no smarter recovery here."""
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
