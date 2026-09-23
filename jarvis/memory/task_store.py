"""Task Store

Persists agent tasks and steps to the database so the Command Center,
Activity Timeline and long-term memory have real history to show.

The agent works with the lightweight dataclasses in ``jarvis.agent.task``;
this module maps them onto the ORM models in ``jarvis.core.models``.
"""

from typing import Any, Optional

from sqlalchemy import select, desc
from loguru import logger

from jarvis.core.database import get_session
from jarvis.core.models import (
    Task as TaskRow,
    TaskStep as TaskStepRow,
    TaskStatus as DBTaskStatus,
    TaskPriority as DBTaskPriority,
)
from jarvis.agent.task import Task, TaskStep, StepStatus

# StepStatus has one value (SKIPPED) the DB task-status enum does not carry.
_STEP_STATUS_MAP = {
    StepStatus.PENDING: DBTaskStatus.PENDING,
    StepStatus.RUNNING: DBTaskStatus.RUNNING,
    StepStatus.COMPLETED: DBTaskStatus.COMPLETED,
    StepStatus.FAILED: DBTaskStatus.FAILED,
    StepStatus.SKIPPED: DBTaskStatus.CANCELLED,
    StepStatus.WAITING_APPROVAL: DBTaskStatus.WAITING_APPROVAL,
}


def _db_status(status: Any) -> DBTaskStatus:
    if isinstance(status, StepStatus):
        return _STEP_STATUS_MAP.get(status, DBTaskStatus.PENDING)
    try:
        return DBTaskStatus(getattr(status, "value", status))
    except ValueError:
        return DBTaskStatus.PENDING


def _db_priority(priority: Any) -> DBTaskPriority:
    try:
        return DBTaskPriority(getattr(priority, "value", priority))
    except ValueError:
        return DBTaskPriority.NORMAL


def _render(value: Any, limit: int = 4000) -> Optional[str]:
    if value is None:
        return None
    text = value if isinstance(value, str) else str(value)
    return text[:limit]


def _jsonable_args(args: Optional[dict]) -> dict:
    """Bound tool args so a huge payload cannot bloat the row."""
    if not args:
        return {}
    out = {}
    for key, value in args.items():
        if isinstance(value, (str, int, float, bool, type(None))):
            out[str(key)] = value[:1000] if isinstance(value, str) else value
        else:
            out[str(key)] = _render(value, 1000)
    return out


class TaskStore:
    """Persists agent tasks and their steps."""

    def __init__(self, enabled: bool = True):
        self._enabled = enabled

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled

    async def save_task(self, task: Task) -> None:
        """Insert or update the task row and replace its steps."""
        if not self._enabled:
            return
        try:
            async with get_session() as session:
                row = await session.get(TaskRow, task.id)
                if row is None:
                    row = TaskRow(id=task.id, goal=task.goal)
                    session.add(row)

                row.goal = task.goal
                row.status = _db_status(task.status)
                row.priority = _db_priority(task.priority)
                row.parent_task_id = task.parent_task_id
                row.created_at = task.created_at
                row.started_at = task.started_at
                row.completed_at = task.completed_at
                row.error = _render(task.error)
                row.result = _render(task.result)
                row.task_metadata = task.metadata or {}

                await session.flush()

                # Steps are replanned during recovery, so rewrite them wholesale.
                existing = await session.execute(
                    select(TaskStepRow).where(TaskStepRow.task_id == task.id)
                )
                for old in existing.scalars().all():
                    await session.delete(old)
                await session.flush()

                for number, step in enumerate(task.steps, start=1):
                    session.add(self._step_row(task.id, number, step))

                await session.commit()
        except Exception as e:
            logger.error(f"Failed to persist task {task.id}: {e}")

    @staticmethod
    def _step_row(task_id: str, number: int, step: TaskStep) -> TaskStepRow:
        return TaskStepRow(
            id=step.id,
            task_id=task_id,
            step_number=number,
            description=step.description,
            tool_name=step.tool_name,
            tool_args=_jsonable_args(step.tool_args),
            status=_db_status(step.status),
            requires_approval=step.requires_approval,
            approved=step.approved,
            started_at=step.started_at,
            completed_at=step.completed_at,
            result=_render(step.result),
            error=_render(step.error),
            retry_count=step.retry_count,
            task_metadata=step.metadata or {},
        )

    async def get_task(self, task_id: str) -> Optional[TaskRow]:
        """Load one persisted task."""
        async with get_session() as session:
            return await session.get(TaskRow, task_id)

    async def get_steps(self, task_id: str) -> list[TaskStepRow]:
        """Load a task's steps in order."""
        async with get_session() as session:
            result = await session.execute(
                select(TaskStepRow)
                .where(TaskStepRow.task_id == task_id)
                .order_by(TaskStepRow.step_number)
            )
            return list(result.scalars().all())

    async def get_recent_tasks(self, limit: int = 50) -> list[TaskRow]:
        """Load recent tasks, newest first."""
        async with get_session() as session:
            result = await session.execute(
                select(TaskRow).order_by(desc(TaskRow.created_at)).limit(limit)
            )
            return list(result.scalars().all())

    async def get_stats(self) -> dict[str, Any]:
        """Summarize stored task outcomes."""
        async with get_session() as session:
            result = await session.execute(select(TaskRow))
            rows = list(result.scalars().all())

        completed = sum(1 for r in rows if r.status == DBTaskStatus.COMPLETED)
        failed = sum(1 for r in rows if r.status == DBTaskStatus.FAILED)
        durations = [
            (r.completed_at - r.started_at).total_seconds()
            for r in rows
            if r.started_at and r.completed_at
        ]
        return {
            "total": len(rows),
            "completed": completed,
            "failed": failed,
            "success_rate": completed / len(rows) if rows else 0.0,
            "avg_duration_seconds": sum(durations) / len(durations) if durations else 0.0,
        }


_task_store: Optional[TaskStore] = None


def get_task_store() -> TaskStore:
    """Get the global task store instance."""
    global _task_store
    if _task_store is None:
        _task_store = TaskStore()
    return _task_store
