"""JARVIS UI - Command Center Dashboard"""

from typing import Optional, List
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QGridLayout, QProgressBar, QListWidget,
    QListWidgetItem, QTabWidget, QTextEdit, QSplitter
)
from PySide6.QtGui import QFont, QColor, QPalette

import asyncio

from jarvis.core.config import get_settings
from jarvis.core.logging import get_logger
from jarvis.core.database import is_database_ready
from jarvis.agent.task import Task, TaskStatus
from jarvis.memory.task_store import get_task_store
from jarvis.memory.project_memory import ProjectMemory
from jarvis.ui.activity_timeline import ActivityTimeline

logger = get_logger(__name__)


class MetricCard(QFrame):
    """System metric card."""

    def __init__(self, title: str, value: str, unit: str = "", color: str = "#00aaff", parent=None):
        super().__init__(parent)
        self.title = title
        self.value = value
        self.unit = unit
        self.color = color
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(4)

        # Title
        title_label = QLabel(self.title)
        title_label.setFont(QFont("Segoe UI", 9))
        title_label.setStyleSheet("color: #888;")
        layout.addWidget(title_label)

        # Value
        self.value_label = QLabel(f"{self.value}{self.unit}")
        self.value_label.setFont(QFont("Segoe UI", 24, QFont.Weight.Bold))
        self.value_label.setStyleSheet(f"color: {self.color};")
        layout.addWidget(self.value_label)

        self.setStyleSheet(f"""
            MetricCard {{
                background-color: #16161e;
                border-radius: 8px;
                border: 1px solid #333;
            }}
        """)


class ActiveAppWidget(QFrame):
    """Active application widget."""

    def __init__(self, apps: List[str], parent=None):
        super().__init__(parent)
        self.apps = apps
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        # Title
        title = QLabel("ACTIVE APPLICATIONS")
        title.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        title.setStyleSheet("color: #888;")
        layout.addWidget(title)

        # Apps
        self.apps_layout = QVBoxLayout()
        self.apps_layout.setSpacing(6)
        layout.addLayout(self.apps_layout)

        self.setStyleSheet("""
            ActiveAppWidget {
                background-color: #16161e;
                border-radius: 8px;
                border: 1px solid #333;
            }
        """)

    def update_apps(self, apps: List[str]) -> None:
        """Update app list."""
        # Clear existing
        while self.apps_layout.count():
            item = self.apps_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for app in apps:
            label = QLabel(f"▸ {app}")
            label.setFont(QFont("Segoe UI", 10))
            label.setStyleSheet("color: #e0e0e0;")
            self.apps_layout.addWidget(label)


class RecentTaskWidget(QFrame):
    """Recent tasks widget."""

    def __init__(self, tasks: List[Task], parent=None):
        super().__init__(parent)
        self.tasks = tasks
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        # Title
        title = QLabel("RECENT TASKS")
        title.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        title.setStyleSheet("color: #888;")
        layout.addWidget(title)

        # Tasks
        self.tasks_layout = QVBoxLayout()
        self.tasks_layout.setSpacing(6)
        layout.addLayout(self.tasks_layout)

        self.setStyleSheet("""
            RecentTaskWidget {
                background-color: #16161e;
                border-radius: 8px;
                border: 1px solid #333;
            }
        """)

    def update_tasks(self, tasks: List[Task]) -> None:
        """Update task list."""
        while self.tasks_layout.count():
            item = self.tasks_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for task in tasks[:10]:
            task_item = QWidget()
            item_layout = QHBoxLayout(task_item)
            item_layout.setContentsMargins(0, 0, 0, 0)
            item_layout.setSpacing(8)

            # Status icon
            # Keyed by value so both the agent's TaskStatus and the
            # database's equivalent enum resolve to the same color.
            status_colors = {
                "completed": "#00ff66",
                "failed": "#ff4444",
                "cancelled": "#ff8844",
                "running": "#00aaff",
                "planning": "#ffaa00",
                "waiting_approval": "#ffaa00",
            }
            status_value = getattr(task.status, "value", str(task.status))
            color = status_colors.get(status_value, "#888")

            status_dot = QLabel("●")
            status_dot.setStyleSheet(f"color: {color}; font-size: 12px;")
            item_layout.addWidget(status_dot)

            # Task info
            info_layout = QVBoxLayout()
            info_layout.setSpacing(2)

            name = QLabel(task.goal[:40] + "..." if len(task.goal) > 40 else task.goal)
            name.setFont(QFont("Segoe UI", 9))
            name.setStyleSheet("color: #ffffff;")
            info_layout.addWidget(name)

            status = QLabel(status_value.upper())
            status.setFont(QFont("Segoe UI", 7))
            status.setStyleSheet(f"color: {color};")
            info_layout.addWidget(status)

            item_layout.addLayout(info_layout)
            item_layout.addStretch()

            self.tasks_layout.addWidget(task_item)


class MemoryWidget(QFrame):
    """Memory/Projects widget."""

    def __init__(self, projects: List[str], parent=None):
        super().__init__(parent)
        self.projects = projects
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        title = QLabel("MEMORY / PROJECTS")
        title.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        title.setStyleSheet("color: #888;")
        layout.addWidget(title)

        self.projects_layout = QVBoxLayout()
        self.projects_layout.setSpacing(6)
        layout.addLayout(self.projects_layout)

        self.setStyleSheet("""
            MemoryWidget {
                background-color: #16161e;
                border-radius: 8px;
                border: 1px solid #333;
            }
        """)

    def update_projects(self, projects: List[str]) -> None:
        while self.projects_layout.count():
            item = self.projects_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for project in projects:
            label = QLabel(f"📁 {project}")
            label.setFont(QFont("Segoe UI", 10))
            label.setStyleSheet("color: #e0e0e0;")
            self.projects_layout.addWidget(label)


class SystemWidget(QFrame):
    """System metrics widget."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        title = QLabel("SYSTEM")
        title.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        title.setStyleSheet("color: #888;")
        layout.addWidget(title)

        # Metrics grid
        grid = QGridLayout()
        grid.setSpacing(12)

        self.cpu_card = MetricCard("CPU", "0", "%", "#00aaff")
        self.ram_card = MetricCard("RAM", "0", "%", "#00ff66")
        self.net_card = MetricCard("NETWORK", "0", " MB/s", "#ffaa00")
        self.disk_card = MetricCard("DISK", "0", "%", "#aa66ff")

        grid.addWidget(self.cpu_card, 0, 0)
        grid.addWidget(self.ram_card, 0, 1)
        grid.addWidget(self.net_card, 1, 0)
        grid.addWidget(self.disk_card, 1, 1)

        layout.addLayout(grid)

        self.setStyleSheet("""
            SystemWidget {
                background-color: #16161e;
                border-radius: 8px;
                border: 1px solid #333;
            }
        """)

    def update_metrics(self, cpu: float, ram: float, net: float, disk: float) -> None:
        self.cpu_card.value_label.setText(f"{cpu:.0f}{self.cpu_card.unit}")
        self.ram_card.value_label.setText(f"{ram:.0f}{self.ram_card.unit}")
        self.net_card.value_label.setText(f"{net:.1f}{self.net_card.unit}")
        self.disk_card.value_label.setText(f"{disk:.0f}{self.disk_card.unit}")


class CurrentTaskWidget(QFrame):
    """Current task detail widget."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._task: Optional[Task] = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)

        # Title
        title = QLabel("CURRENT TASK")
        title.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        title.setStyleSheet("color: #888;")
        layout.addWidget(title)

        # Task name
        self.task_name = QLabel("No active task")
        self.task_name.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        self.task_name.setStyleSheet("color: #ffffff;")
        self.task_name.setWordWrap(True)
        layout.addWidget(self.task_name)

        # Progress
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #333;
                border-radius: 6px;
                background-color: #1a1a2e;
                text-align: center;
                color: #ffffff;
                height: 24px;
                font-size: 11px;
            }
            QProgressBar::chunk {
                background-color: #00aaff;
                border-radius: 5px;
            }
        """)
        layout.addWidget(self.progress_bar)

        # Current step
        self.step_label = QLabel("")
        self.step_label.setFont(QFont("Segoe UI", 9))
        self.step_label.setStyleSheet("color: #888;")
        self.step_label.setWordWrap(True)
        layout.addWidget(self.step_label)

        # Steps list
        self.steps_list = QListWidget()
        self.steps_list.setMaximumHeight(200)
        self.steps_list.setStyleSheet("""
            QListWidget {
                background-color: #1a1a2e;
                border: 1px solid #333;
                border-radius: 6px;
                color: #e0e0e0;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #333;
            }
            QListWidget::item:selected {
                background-color: #00aaff44;
            }
        """)
        layout.addWidget(self.steps_list)

        self.setStyleSheet("""
            CurrentTaskWidget {
                background-color: #16161e;
                border-radius: 8px;
                border: 1px solid #333;
            }
        """)

    def set_task(self, task: Optional[Task]) -> None:
        self._task = task
        if task:
            self.task_name.setText(task.goal)
            self.progress_bar.setValue(int(task.progress * 100))
            if task.current_step:
                self.step_label.setText(f"→ {task.current_step.description}")

            # Update steps list
            self.steps_list.clear()
            for i, step in enumerate(task.steps):
                status_icons = {
                    "pending": "○",
                    "running": "◐",
                    "completed": "●",
                    "failed": "✗",
                    "waiting_approval": "◍",
                }
                icon = status_icons.get(step.status.value, "?")
                item_text = f"{icon} {step.description}"
                if step.tool_name:
                    item_text += f"  [{step.tool_name}]"
                self.steps_list.addItem(item_text)
        else:
            self.task_name.setText("No active task")
            self.progress_bar.setValue(0)
            self.step_label.setText("")
            self.steps_list.clear()


class CommandCenter(QWidget):
    """Command Center dashboard."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.settings = get_settings()
        self._setup_ui()
        self._start_monitoring()

    def _setup_ui(self) -> None:
        """Setup UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # Header
        header = QWidget()
        header.setFixedHeight(60)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)

        title = QLabel("◉ JARVIS COMMAND CENTER")
        title.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        title.setStyleSheet("color: #ffffff;")
        header_layout.addWidget(title)

        header_layout.addStretch()

        # Status indicator
        self.status_indicator = QLabel("● ONLINE")
        self.status_indicator.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.status_indicator.setStyleSheet("color: #00ff66;")
        header_layout.addWidget(self.status_indicator)

        layout.addWidget(header)

        # Main content area with splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        # Left panel - Current task + System
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(16)

        self.current_task_widget = CurrentTaskWidget()
        left_layout.addWidget(self.current_task_widget, 1)

        self.system_widget = SystemWidget()
        left_layout.addWidget(self.system_widget)

        splitter.addWidget(left_panel)

        # Right panel - Apps, Tasks, Memory
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(16)

        self.apps_widget = ActiveAppWidget([])
        right_layout.addWidget(self.apps_widget)

        self.recent_tasks_widget = RecentTaskWidget([])
        right_layout.addWidget(self.recent_tasks_widget, 1)

        self.activity_timeline = ActivityTimeline()
        right_layout.addWidget(self.activity_timeline, 1)

        self.memory_widget = MemoryWidget([])
        right_layout.addWidget(self.memory_widget)

        splitter.addWidget(right_panel)

        splitter.setSizes([500, 400])
        layout.addWidget(splitter, 1)

        self.setStyleSheet("background-color: #1a1a2e;")

    def _start_monitoring(self) -> None:
        """Start system monitoring and periodic data refresh."""
        self._task_store = get_task_store()
        self._project_memory = ProjectMemory()

        self.monitor_timer = QTimer()
        self.monitor_timer.timeout.connect(self._update_system_metrics)
        self.monitor_timer.start(2000)  # Every 2 seconds

        self.data_timer = QTimer()
        self.data_timer.timeout.connect(self.request_refresh)
        self.data_timer.start(5000)  # Every 5 seconds

        self._update_active_apps()
        self.request_refresh()

    def request_refresh(self) -> None:
        """Refresh live panels from a synchronous context, such as a timer."""
        self._update_active_apps()
        try:
            asyncio.get_running_loop().create_task(self.refresh())
        except RuntimeError:
            # No asyncio loop (for example a bare Qt preview); the system
            # metrics timer still runs.
            pass

    async def refresh(self) -> None:
        """Pull recent tasks and known projects from storage."""
        if not is_database_ready():
            return

        try:
            tasks = await self._task_store.get_recent_tasks(limit=10)
            self.set_recent_tasks(tasks)
        except Exception as e:
            logger.debug(f"Could not load recent tasks: {e}")

        try:
            projects = await self._project_memory.list_projects()
            self.set_projects([p.name for p in projects])
        except Exception as e:
            logger.debug(f"Could not load projects: {e}")

        try:
            await self.activity_timeline.refresh()
        except Exception as e:
            logger.debug(f"Could not refresh timeline: {e}")

    def _update_active_apps(self) -> None:
        """List the visible top-level windows as active applications."""
        try:
            import psutil

            seen = []
            for proc in psutil.process_iter(["name", "memory_info"]):
                try:
                    info = proc.info
                    if info.get("memory_info") is None:
                        continue
                    seen.append((info["memory_info"].rss, info["name"]))
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            seen.sort(reverse=True)
            names = []
            for _, name in seen:
                if name and name not in names:
                    names.append(name)
                if len(names) >= 8:
                    break

            self.set_active_apps(names)
        except Exception as e:
            logger.debug(f"Could not list active applications: {e}")

    def _update_system_metrics(self) -> None:
        """Update system metrics."""
        try:
            import psutil
            cpu = psutil.cpu_percent()
            ram = psutil.virtual_memory().percent
            disk = psutil.disk_usage('/').percent
            net = 0  # Simplified
            self.system_widget.update_metrics(cpu, ram, net, disk)
        except Exception:
            pass

    def set_current_task(self, task: Optional[Task]) -> None:
        """Set current task."""
        self.current_task_widget.set_task(task)

    def update_task(self, task: Task) -> None:
        """Update current task."""
        self.current_task_widget.set_task(task)

    def set_active_apps(self, apps: List[str]) -> None:
        """Set active applications."""
        self.apps_widget.update_apps(apps)

    def set_recent_tasks(self, tasks: List[Task]) -> None:
        """Set recent tasks."""
        self.recent_tasks_widget.update_tasks(tasks)

    def set_projects(self, projects: List[str]) -> None:
        """Set projects."""
        self.memory_widget.update_projects(projects)


CommandCenterDashboard = CommandCenter