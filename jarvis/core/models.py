"""JARVIS Database Models"""

import enum
import uuid
from datetime import datetime
from typing import Optional, List
from sqlalchemy import (
    String,
    Text,
    Integer,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    JSON,
    Boolean,
    Float,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.sqlite import JSON as SQLiteJSON

from jarvis.core.database import Base


class TaskStatus(str, enum.Enum):
    """Task execution status."""
    PENDING = "pending"
    PLANNING = "planning"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskPriority(str, enum.Enum):
    """Task priority."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class ToolRiskLevel(str, enum.Enum):
    """Tool risk level."""
    SAFE = "safe"
    SENSITIVE = "sensitive"
    DANGEROUS = "dangerous"


class Task(Base):
    """Task model for tracking agent tasks."""

    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    goal: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[TaskStatus] = mapped_column(Enum(TaskStatus), default=TaskStatus.PENDING, nullable=False)
    priority: Mapped[TaskPriority] = mapped_column(Enum(TaskPriority), default=TaskPriority.NORMAL, nullable=False)
    parent_task_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("tasks.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    result: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    task_metadata: Mapped[dict] = mapped_column(SQLiteJSON, default=dict, nullable=False)

    # Relationships
    steps: Mapped[List["TaskStep"]] = relationship("TaskStep", back_populates="task", cascade="all, delete-orphan")
    sub_tasks: Mapped[List["Task"]] = relationship("Task", backref="parent_task", remote_side=[id])

    __table_args__ = (
        Index("ix_tasks_status", "status"),
        Index("ix_tasks_created_at", "created_at"),
        Index("ix_tasks_parent_task_id", "parent_task_id"),
    )


class TaskStep(Base):
    """Individual step within a task."""

    __tablename__ = "task_steps"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id: Mapped[str] = mapped_column(String(36), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    step_number: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    tool_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    tool_args: Mapped[dict] = mapped_column(SQLiteJSON, default=dict, nullable=False)
    status: Mapped[TaskStatus] = mapped_column(Enum(TaskStatus), default=TaskStatus.PENDING, nullable=False)
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    approved: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    result: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    task_metadata: Mapped[dict] = mapped_column(SQLiteJSON, default=dict, nullable=False)

    task: Mapped["Task"] = relationship("Task", back_populates="steps")

    __table_args__ = (
        Index("ix_task_steps_task_id", "task_id"),
        Index("ix_task_steps_step_number", "task_id", "step_number"),
    )


class Project(Base):
    """Project memory model."""

    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    path: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    language: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    framework: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    git_repo: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    github_repo: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    last_accessed: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    task_metadata: Mapped[dict] = mapped_column(SQLiteJSON, default=dict, nullable=False)

    __table_args__ = (
        Index("ix_projects_name", "name"),
        Index("ix_projects_path", "path"),
        Index("ix_projects_last_accessed", "last_accessed"),
    )


class Conversation(Base):
    """Conversation history model."""

    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id: Mapped[str] = mapped_column(String(36), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # user, assistant, system
    content: Mapped[str] = mapped_column(Text, nullable=False)
    task_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("tasks.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    task_metadata: Mapped[dict] = mapped_column(SQLiteJSON, default=dict, nullable=False)

    __table_args__ = (
        Index("ix_conversations_session_id", "session_id"),
        Index("ix_conversations_task_id", "task_id"),
        Index("ix_conversations_created_at", "created_at"),
    )


class Preference(Base):
    """User preferences model."""

    __tablename__ = "preferences"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(50), default="general", nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class AuditLog(Base):
    """Security audit log model."""

    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    task_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("tasks.id"), nullable=True)
    tool_name: Mapped[str] = mapped_column(String(100), nullable=False)
    tool_args: Mapped[dict] = mapped_column(SQLiteJSON, default=dict, nullable=False)
    risk_level: Mapped[ToolRiskLevel] = mapped_column(Enum(ToolRiskLevel), nullable=False)
    approved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    approved_by: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # user, auto
    result: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    __table_args__ = (
        Index("ix_audit_logs_timestamp", "timestamp"),
        Index("ix_audit_logs_task_id", "task_id"),
        Index("ix_audit_logs_tool_name", "tool_name"),
        Index("ix_audit_logs_risk_level", "risk_level"),
    )


class SystemMetric(Base):
    """System performance metrics."""

    __tablename__ = "system_metrics"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    cpu_percent: Mapped[float] = mapped_column(Float, nullable=False)
    memory_percent: Mapped[float] = mapped_column(Float, nullable=False)
    disk_percent: Mapped[float] = mapped_column(Float, nullable=False)
    network_sent_mb: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    network_recv_mb: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    __table_args__ = (
        Index("ix_system_metrics_timestamp", "timestamp"),
    )