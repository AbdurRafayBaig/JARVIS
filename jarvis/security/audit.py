"""Audit Logger

Logs tool executions and system events to the database.
"""

from datetime import datetime, timedelta
from typing import Any, Optional

from sqlalchemy import select, desc, delete
from loguru import logger

from jarvis.core.config import get_settings
from jarvis.core.database import get_session
from jarvis.core.models import AuditLog, ToolRiskLevel


def _coerce_risk(risk_level: Any) -> ToolRiskLevel:
    """Coerce an arbitrary risk value into a ToolRiskLevel."""
    if isinstance(risk_level, ToolRiskLevel):
        return risk_level
    try:
        return ToolRiskLevel(str(risk_level).lower())
    except ValueError:
        return ToolRiskLevel.SAFE


def _truncate(value: Any, limit: int = 2000) -> Optional[str]:
    """Render a value as a bounded string for storage."""
    if value is None:
        return None
    text = value if isinstance(value, str) else str(value)
    return text[:limit]


def _jsonable(args: Optional[dict]) -> dict:
    """Make tool args safe for the JSON column."""
    if not args:
        return {}
    safe = {}
    for key, value in args.items():
        if isinstance(value, (str, int, float, bool, type(None))):
            safe[str(key)] = value
        elif isinstance(value, (list, tuple)):
            safe[str(key)] = [_truncate(v, 200) for v in value[:20]]
        elif isinstance(value, dict):
            safe[str(key)] = {str(k): _truncate(v, 200) for k, v in list(value.items())[:20]}
        else:
            safe[str(key)] = _truncate(value, 200)
    return safe


class AuditLogger:
    """Logs audit events to the database."""

    def __init__(self):
        self._enabled = get_settings().security.audit_log_enabled

    @property
    def enabled(self) -> bool:
        return self._enabled

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled

    async def _write(self, **columns: Any) -> None:
        """Insert one audit row, never raising into the caller."""
        if not self._enabled:
            return
        try:
            async with get_session() as session:
                session.add(AuditLog(**columns))
                await session.commit()
        except Exception as e:
            logger.error(f"Failed to log audit event: {e}")

    async def log_tool_execution(
        self,
        tool_name: str,
        tool_args: dict,
        result: Any = None,
        success: bool = True,
        duration: float = 0.0,
        error: Optional[str] = None,
        risk_level: Any = ToolRiskLevel.SAFE,
        approved: bool = True,
        approved_by: str = "auto",
        task_id: Optional[str] = None,
    ) -> None:
        """Log a tool execution event."""
        await self._write(
            task_id=task_id,
            tool_name=tool_name,
            tool_args=_jsonable(tool_args),
            risk_level=_coerce_risk(risk_level),
            approved=approved,
            approved_by=approved_by,
            result=_truncate(result),
            error=_truncate(error) if not success or error else None,
            duration_ms=duration * 1000.0,
        )

    async def log_approval(
        self,
        tool_name: str,
        tool_args: dict,
        risk_level: Any,
        approved: bool,
        approved_by: str = "user",
        task_id: Optional[str] = None,
    ) -> None:
        """Log an approval decision, made before the tool runs."""
        await self._write(
            task_id=task_id,
            tool_name=tool_name,
            tool_args=_jsonable(tool_args),
            risk_level=_coerce_risk(risk_level),
            approved=approved,
            approved_by=approved_by,
            result="approved" if approved else "denied",
        )

    async def log_command_execution(
        self,
        command: str,
        result: Any,
        success: bool,
        duration: float,
        task_id: Optional[str] = None,
    ) -> None:
        """Log a shell/PowerShell command execution."""
        await self.log_tool_execution(
            tool_name="run_command",
            tool_args={"command": _truncate(command, 500)},
            result=result,
            success=success,
            duration=duration,
            error=None if success else _truncate(result),
            risk_level=ToolRiskLevel.SENSITIVE,
            task_id=task_id,
        )

    async def log_user_action(
        self,
        action: str,
        details: Optional[dict] = None,
        task_id: Optional[str] = None,
    ) -> None:
        """Log a user-initiated action."""
        await self._write(
            task_id=task_id,
            tool_name=f"user:{action}",
            tool_args=_jsonable(details),
            risk_level=ToolRiskLevel.SAFE,
            approved=True,
            approved_by="user",
            result="ok",
        )

    async def log_error(
        self,
        error_type: str,
        error_message: str,
        context: Optional[dict] = None,
        task_id: Optional[str] = None,
    ) -> None:
        """Log an error event."""
        await self._write(
            task_id=task_id,
            tool_name=f"error:{error_type}",
            tool_args=_jsonable(context),
            risk_level=ToolRiskLevel.SAFE,
            approved=False,
            approved_by="auto",
            error=_truncate(error_message),
        )

    async def get_recent_logs(
        self,
        tool_name: Optional[str] = None,
        task_id: Optional[str] = None,
        limit: int = 100,
    ) -> list[AuditLog]:
        """Get recent audit logs, newest first."""
        async with get_session() as session:
            query = select(AuditLog).order_by(desc(AuditLog.timestamp))
            if tool_name:
                query = query.where(AuditLog.tool_name == tool_name)
            if task_id:
                query = query.where(AuditLog.task_id == task_id)
            result = await session.execute(query.limit(limit))
            return list(result.scalars().all())

    async def get_stats(self, hours: int = 24) -> dict[str, Any]:
        """Summarize audit activity over a recent window."""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        async with get_session() as session:
            result = await session.execute(
                select(AuditLog).where(AuditLog.timestamp >= cutoff)
            )
            rows = list(result.scalars().all())

        durations = [r.duration_ms for r in rows if r.duration_ms is not None]
        return {
            "total": len(rows),
            "failed": sum(1 for r in rows if r.error),
            "denied": sum(1 for r in rows if not r.approved),
            "avg_duration_ms": sum(durations) / len(durations) if durations else 0.0,
            "by_tool": {
                name: sum(1 for r in rows if r.tool_name == name)
                for name in {r.tool_name for r in rows}
            },
        }

    async def clear_old_logs(self, days: int = 30) -> int:
        """Clear audit logs older than the given number of days."""
        cutoff = datetime.utcnow() - timedelta(days=days)
        async with get_session() as session:
            result = await session.execute(
                delete(AuditLog).where(AuditLog.timestamp < cutoff)
            )
            await session.commit()
            return result.rowcount or 0


_audit_logger: Optional[AuditLogger] = None


def get_audit_logger() -> AuditLogger:
    """Get the global audit logger instance."""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger
