"""Activity Timeline

Provides a clickable activity history backed by persisted task records.
"""

import asyncio

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QLabel,
    QPushButton,
    QTextEdit,
)
from PySide6.QtCore import Qt, Signal
from loguru import logger

from jarvis.core.database import is_database_ready
from jarvis.core.models import TaskStatus as DBTaskStatus
from jarvis.memory.task_store import get_task_store

_STATUS_ICONS = {
    DBTaskStatus.COMPLETED: "[OK]",
    DBTaskStatus.FAILED: "[FAIL]",
    DBTaskStatus.CANCELLED: "[CANCELLED]",
    DBTaskStatus.RUNNING: "[RUNNING]",
    DBTaskStatus.PLANNING: "[PLANNING]",
    DBTaskStatus.WAITING_APPROVAL: "[WAITING]",
    DBTaskStatus.PENDING: "[PENDING]",
}


def _status_label(status) -> str:
    return _STATUS_ICONS.get(status, f"[{getattr(status, 'value', status)}]")


class ActivityTimeline(QWidget):
    """Widget showing activity history."""

    task_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._store = get_task_store()
        self._init_ui()

    def _init_ui(self):
        """Initialize the UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        header_row = QHBoxLayout()
        header = QLabel("Activity Timeline")
        header.setStyleSheet("font-weight: bold; font-size: 14px; padding: 5px;")
        header_row.addWidget(header)
        header_row.addStretch()

        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.request_refresh)
        header_row.addWidget(self.refresh_button)
        layout.addLayout(header_row)

        self.list_widget = QListWidget()
        self.list_widget.currentItemChanged.connect(self._on_item_changed)
        layout.addWidget(self.list_widget)

        self.detail_text = QTextEdit()
        self.detail_text.setReadOnly(True)
        self.detail_text.setMaximumHeight(150)
        layout.addWidget(self.detail_text)

    def request_refresh(self) -> None:
        """Refresh from a synchronous context, such as a button click."""
        try:
            asyncio.get_running_loop().create_task(self.refresh())
        except RuntimeError:
            logger.debug("No running event loop; skipping timeline refresh")

    async def refresh(self):
        """Refresh the activity list."""
        if not is_database_ready():
            self.list_widget.clear()
            self.detail_text.setPlainText("No database connected - history is unavailable.")
            return

        try:
            tasks = await self._store.get_recent_tasks(limit=50)

            self.list_widget.clear()
            for task in tasks:
                item = QListWidgetItem()
                # The agent's task text lives in `goal`.
                item.setText(f"{_status_label(task.status)} {task.goal[:60]}")
                item.setData(Qt.ItemDataRole.UserRole, task.id)
                self.list_widget.addItem(item)

            if not tasks:
                self.detail_text.setPlainText("No tasks recorded yet.")

        except Exception as e:
            logger.error(f"Failed to refresh activity: {e}")

    def _on_item_changed(self, current, previous):
        """Handle item selection change."""
        if not current:
            return

        task_id = current.data(Qt.ItemDataRole.UserRole)
        if not task_id:
            return

        self.task_selected.emit(task_id)
        try:
            # _load_task_details is a coroutine; it needs scheduling, not calling.
            asyncio.get_running_loop().create_task(self._load_task_details(task_id))
        except RuntimeError:
            logger.debug("No running event loop; skipping task detail load")

    async def _load_task_details(self, task_id: str):
        """Load task details."""
        try:
            task = await self._store.get_task(task_id)
            if not task:
                self.detail_text.setPlainText("Task not found.")
                return

            steps = await self._store.get_steps(task_id)

            lines = [
                f"Goal: {task.goal}",
                f"Status: {getattr(task.status, 'value', task.status)}",
                f"Created: {task.created_at}",
            ]
            if task.started_at and task.completed_at:
                duration = (task.completed_at - task.started_at).total_seconds()
                lines.append(f"Duration: {duration:.1f}s")
            if task.error:
                lines.append(f"Error: {task.error}")
            if task.result:
                lines.append(f"Result: {task.result}")

            lines.append("")
            lines.append("Steps:")
            for step in steps:
                lines.append(
                    f"  {step.step_number}. {_status_label(step.status)} "
                    f"{step.description} ({step.tool_name})"
                )
                if step.error:
                    lines.append(f"       error: {step.error}")

            self.detail_text.setPlainText("\n".join(lines))

        except Exception as e:
            logger.error(f"Failed to load task details: {e}")
