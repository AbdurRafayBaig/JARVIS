"""JARVIS Agent - Core Runtime"""

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Optional

from jarvis.agent.task import Task, TaskStep, TaskStatus, StepStatus
from jarvis.agent.tools import ToolRegistry, get_registry, ToolResult, BaseTool
from jarvis.agent.planner import BasePlanner, SimplePlanner, LLMPlanner
from jarvis.agent.response_generator import ResponseGenerator
from jarvis.agent.step_context import StepContext, rebuild_context
from jarvis.llm.manager import get_llm_manager
from jarvis.core.database import is_database_ready
from jarvis.security.approval import get_approval_manager
from jarvis.security.audit import get_audit_logger
from jarvis.memory.conversation_memory import ConversationMemory
from jarvis.memory.short_term import get_short_term_memory
from jarvis.memory.task_store import get_task_store
from jarvis.core.logging import get_logger, log_task_start, log_task_step, log_task_complete, log_tool_call
from jarvis.core.exceptions import ToolError, ToolNotFoundError, AgentError, VerificationError

logger = get_logger(__name__)


@dataclass
class AgentContext:
    """Context for agent execution."""
    user_id: str = "default"
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    current_project: Optional[str] = None
    working_directory: str = ""
    environment: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


class ApprovalCallback:
    """Callback for handling approval requests."""

    def __init__(self, callback: Callable[[str, dict[str, Any]], Any]):
        self.callback = callback

    async def request_approval(self, action: str, details: dict[str, Any]) -> bool:
        """Request user approval."""
        res = self.callback(action, details)
        if asyncio.iscoroutine(res):
            return await res
        return bool(res)


class VerificationCallback:
    """Callback for verifying tool results."""

    def __init__(self, callback: Callable[[str, dict[str, Any], ToolResult], bool]):
        self.callback = callback

    async def verify(self, tool_name: str, args: dict[str, Any], result: ToolResult) -> bool:
        """Verify tool result."""
        res = self.callback(tool_name, args, result)
        if asyncio.iscoroutine(res):
            return await res
        return bool(res)


class Agent:
    """Main JARVIS agent runtime."""

    def __init__(
        self,
        planner: Optional[BasePlanner] = None,
        tool_registry: Optional[ToolRegistry] = None,
        approval_callback: Optional[ApprovalCallback] = None,
        verification_callback: Optional[VerificationCallback] = None,
        max_steps: int = 30,
        max_retries: int = 3,
        enable_verification: bool = True,
        enable_recovery: bool = True,
    ):
        self.tools = tool_registry or get_registry()

        # Setup planner
        if planner is not None:
            self.planner = planner
        else:
            try:
                llm = get_llm_manager().get_provider()
                self.planner = LLMPlanner(llm, self.tools, max_steps=max_steps)
            except Exception as e:
                logger.warning(f"Could not initialize LLMPlanner ({e}), using SimplePlanner fallback.")
                self.planner = SimplePlanner(self.tools)

        self.approval_callback = approval_callback
        self.verification_callback = verification_callback
        self.max_steps = max_steps
        self.max_retries = max_retries
        self.enable_verification = enable_verification
        self.enable_recovery = enable_recovery
        self.response_generator = ResponseGenerator()

        # Long-term memory, audit and history. These stay inert until a
        # database has been initialized, so tests and headless runs are
        # unaffected while a real session records everything.
        self.conversation_memory = ConversationMemory()
        self.short_term_memory = get_short_term_memory()
        self.audit_logger = get_audit_logger()
        self.task_store = get_task_store()

        self._current_task: Optional[Task] = None
        self._context = AgentContext()
        self._running = False
        self._cancel_requested = False
        self._callbacks: dict[str, list[Callable]] = {
            "task_start": [],
            "task_step": [],
            "task_complete": [],
            "tool_call": [],
            "error": [],
        }

    @property
    def current_task(self) -> Optional[Task]:
        return self._current_task

    @property
    def context(self) -> AgentContext:
        return self._context

    @property
    def is_running(self) -> bool:
        return self._running

    def on(self, event: str, callback: Callable) -> None:
        """Register event callback."""
        if event in self._callbacks:
            self._callbacks[event].append(callback)

    def _emit(self, event: str, *args, **kwargs) -> None:
        """Emit event to callbacks."""
        for callback in self._callbacks.get(event, []):
            try:
                if asyncio.iscoroutinefunction(callback):
                    asyncio.create_task(callback(*args, **kwargs))
                else:
                    callback(*args, **kwargs)
            except Exception as e:
                logger.error(f"Callback error for {event}: {e}")

    # -- persistence helpers -------------------------------------------------
    # Each is a no-op without a database, so the agent runs identically with
    # or without one.

    async def _persist(self, task: Task) -> None:
        if is_database_ready():
            await self.task_store.save_task(task)

    async def _remember(self, role: str, content: str, task_id: Optional[str] = None) -> None:
        self.short_term_memory.add(role, content)
        if is_database_ready():
            await self.conversation_memory.store(role, content, task_id=task_id)

    async def _audit(self, **kwargs: Any) -> None:
        if is_database_ready():
            await self.audit_logger.log_tool_execution(**kwargs)

    # -- execution -----------------------------------------------------------

    async def execute_task(self, goal: str, priority: str = "normal") -> Task:
        """Execute a task from a natural language goal."""
        task = Task(
            goal=goal,
            priority=priority,
        )

        self._current_task = task
        self._running = True
        self._cancel_requested = False

        log_task_start(task.id, goal)
        self._emit("task_start", task)

        await self._remember("user", goal, task_id=task.id)

        try:
            # Planning phase
            task.status = TaskStatus.PLANNING
            context = await self._build_context(goal)
            plan = await self.planner.plan(goal, context)
            task.steps = plan.steps
            task.metadata["reasoning"] = plan.reasoning

            logger.info(f"Plan created with {len(plan.steps)} steps: {plan.reasoning}")

            # Execution phase
            task.status = TaskStatus.RUNNING
            task.started_at = datetime.utcnow()
            await self._persist(task)

            await self._run_plan(task)

            if task.status == TaskStatus.RUNNING:
                task.status = TaskStatus.COMPLETED

            # Generate natural language summary response
            task.result = await self.response_generator.generate_response(task)

        except Exception as e:
            logger.error(f"Task execution failed: {e}")
            task.status = TaskStatus.FAILED
            task.error = str(e)
            task.result = f"Task failed: {e}"
            self._emit("error", task, e)

        finally:
            task.completed_at = datetime.utcnow()
            self._running = False
            log_task_complete(task.id, task.status == TaskStatus.COMPLETED, task.error or "")
            if task.result:
                await self._remember("assistant", str(task.result), task_id=task.id)
            await self._persist(task)
            self._emit("task_complete", task)

        return task

    async def _run_plan(self, task: Task) -> None:
        """Run a task's steps, re-reading the list on each iteration.

        Recovery replaces the remaining steps, so this loop indexes into
        ``task.steps`` rather than iterating a snapshot of it -- otherwise a
        replanned step would never execute.
        """
        step_context = StepContext()
        index = 0
        executed = 0

        while index < len(task.steps):
            if self._cancel_requested:
                task.status = TaskStatus.CANCELLED
                task.error = "Cancelled by user"
                return

            if executed >= self.max_steps:
                task.status = TaskStatus.FAILED
                task.error = f"Step limit reached ({self.max_steps})"
                logger.warning(task.error)
                return

            task.current_step_index = index
            step = task.steps[index]
            executed += 1

            success = await self._execute_step(task, step, step_context)

            if success:
                step_context.record(step)
                index += 1
                await self._persist(task)
                continue

            recovered = await self._handle_failure(task, step)
            await self._persist(task)

            if not recovered:
                task.status = TaskStatus.FAILED
                task.error = step.error or "Step failed"
                return

            # Recovery rewrote the plan from this index onward; rebuild the
            # result context from the steps that actually completed.
            step_context = rebuild_context(task.steps[:index])

    async def _build_context(self, goal: str = "") -> dict[str, Any]:
        """Build context for planning, including recalled memory."""
        context: dict[str, Any] = {
            "current_project": self._context.current_project,
            "working_directory": self._context.working_directory,
            "environment": self._context.environment,
            "available_tools": self.tools.list_tools(),
            "recent_conversation": self.short_term_memory.get_recent(count=6),
        }

        if is_database_ready() and goal:
            try:
                from jarvis.memory.retrieval import MemoryRetriever

                recalled = await MemoryRetriever().get_context(goal)
                context["conversation_history"] = recalled.get("conversation_history", [])
                context["preferences"] = recalled.get("preferences", {})
                context["related_knowledge"] = recalled.get("similar_documents", [])
            except Exception as e:
                logger.warning(f"Memory recall failed: {e}")

        return context

    async def _execute_step(
        self,
        task: Task,
        step: TaskStep,
        step_context: Optional[StepContext] = None,
    ) -> bool:
        """Execute a single step."""
        step.status = StepStatus.RUNNING
        step.started_at = datetime.utcnow()
        step.error = None

        log_task_step(task.id, step.description, "STARTED")
        self._emit("task_step", task, step, "started")

        tool = self.tools.get(step.tool_name)
        if not tool:
            step.error = f"Tool not found: {step.tool_name}"
            step.status = StepStatus.FAILED
            return False

        # Resolve {{step_N.result}} references against earlier results.
        if step_context is not None:
            step.tool_args = step_context.resolve_args(step.tool_args)

        # Check approval requirements (from step flag, tool risk level, or approval manager)
        risk_level = tool.risk_level.value
        approval_mgr = get_approval_manager()

        if step.requires_approval or tool.requires_approval:
            task.status = TaskStatus.WAITING_APPROVAL
            step.status = StepStatus.WAITING_APPROVAL

            approved = False
            if self.approval_callback:
                approved = await self.approval_callback.request_approval(
                    step.tool_name,
                    {"description": step.description, "args": step.tool_args},
                )
            else:
                approved = await approval_mgr.request_approval(
                    step.tool_name, step.tool_args, risk_level
                )

            step.approved = approved
            if is_database_ready():
                await self.audit_logger.log_approval(
                    step.tool_name, step.tool_args, risk_level, approved, task_id=task.id
                )

            if not approved:
                step.error = "User denied approval"
                step.status = StepStatus.FAILED
                return False

            task.status = TaskStatus.RUNNING

        started = time.perf_counter()
        try:
            validated_args = tool.validate_args(step.tool_args)
            self._emit("tool_call", tool.name, validated_args)

            result = await tool.execute(**validated_args)
            duration = time.perf_counter() - started

            step.result = result.data
            step.metadata = result.metadata

            log_tool_call(step.tool_name, validated_args, result.data, result.error if not result.success else None)
            await self._audit(
                tool_name=step.tool_name,
                tool_args=validated_args,
                result=result.data,
                success=result.success,
                duration=duration,
                error=result.error,
                risk_level=risk_level,
                approved=step.approved if step.approved is not None else True,
                task_id=task.id,
            )

            if not result.success:
                step.error = result.error
                step.status = StepStatus.FAILED
                self._emit("task_step", task, step, "failed")
                return False

            # Verification
            if self.enable_verification and self.verification_callback:
                verified = await self.verification_callback.verify(
                    step.tool_name, validated_args, result
                )
                if not verified:
                    step.error = "Verification failed"
                    step.status = StepStatus.FAILED
                    self._emit("task_step", task, step, "failed")
                    return False

            step.status = StepStatus.COMPLETED
            step.completed_at = datetime.utcnow()
            log_task_step(task.id, step.description, "COMPLETED")
            self._emit("task_step", task, step, "completed")
            return True

        except Exception as e:
            duration = time.perf_counter() - started
            step.error = str(e)
            step.status = StepStatus.FAILED
            log_tool_call(step.tool_name, step.tool_args, None, e)
            await self._audit(
                tool_name=step.tool_name,
                tool_args=step.tool_args,
                success=False,
                duration=duration,
                error=str(e),
                risk_level=risk_level,
                task_id=task.id,
            )
            self._emit("task_step", task, step, "failed")
            return False

    async def _handle_failure(self, task: Task, step: TaskStep) -> bool:
        """Handle step failure by replanning the remainder of the task."""
        if not self.enable_recovery or step.retry_count >= self.max_retries:
            return False

        step.retry_count += 1
        logger.info(f"Recovering step {step.retry_count}/{self.max_retries}: {step.description}")

        try:
            new_plan = await self.planner.replan(task, step, step.error or "Unknown error")
        except Exception as e:
            logger.error(f"Replanning failed: {e}")
            return False

        if not new_plan.steps:
            return False

        # Carry the retry count forward so a step that keeps failing the same
        # way eventually stops being retried.
        for replacement in new_plan.steps:
            if replacement.tool_name == step.tool_name:
                replacement.retry_count = step.retry_count
                break

        # Replace the failed step and everything after it with the new plan.
        task.steps = task.steps[: task.current_step_index] + new_plan.steps
        logger.info(f"Recovery plan has {len(new_plan.steps)} step(s): {new_plan.reasoning}")
        return True

    async def cancel_current_task(self) -> bool:
        """Cancel the currently running task."""
        if self._current_task and self._running:
            self._cancel_requested = True
            self._current_task.status = TaskStatus.CANCELLED
            self._current_task.completed_at = datetime.utcnow()
            self._running = False
            logger.info("Task cancelled")
            return True
        return False

    def get_status(self) -> dict[str, Any]:
        """Get agent status."""
        return {
            "running": self._running,
            "current_task": self._current_task.to_dict() if self._current_task else None,
            "tools_count": len(self.tools.get_all()),
        }


def create_agent(
    planner: Optional[BasePlanner] = None,
    tool_registry: Optional[ToolRegistry] = None,
    **kwargs,
) -> Agent:
    """Factory function to create an agent."""
    return Agent(planner=planner, tool_registry=tool_registry, **kwargs)
