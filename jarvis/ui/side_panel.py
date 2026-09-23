"""JARVIS UI - Side Panel"""

from typing import Optional, List
from PySide6.QtCore import Qt, Signal, QTimer, QPropertyAnimation, QEasingCurve, QRect
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QLineEdit, QScrollArea, QFrame, QSizePolicy,
    QProgressBar, QListWidget, QListWidgetItem, QMenu
)
from PySide6.QtGui import QFont, QIcon, QPixmap, QAction, QCursor

from jarvis.core.config import get_settings
from jarvis.core.logging import get_logger
from jarvis.agent.task import Task, TaskStep, TaskStatus, StepStatus

logger = get_logger(__name__)


class ChatMessageWidget(QFrame):
    """Single chat message widget."""

    def __init__(self, role: str, content: str, parent=None):
        super().__init__(parent)
        self.role = role
        self.content = content
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(4)

        # Role label
        role_label = QLabel(self.role.title())
        role_label.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        if self.role == "user":
            role_label.setStyleSheet("color: #00aaff;")
        elif self.role == "assistant":
            role_label.setStyleSheet("color: #00ff66;")
        else:
            role_label.setStyleSheet("color: #ffaa00;")
        layout.addWidget(role_label)

        # Content
        content_label = QLabel(self.content)
        content_label.setWordWrap(True)
        content_label.setFont(QFont("Segoe UI", 9))
        content_label.setStyleSheet("color: #e0e0e0;")
        content_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(content_label)

        # Styling
        if self.role == "user":
            self.setStyleSheet("""
                ChatMessageWidget {
                    background-color: #1e2a3a;
                    border-radius: 8px;
                    border: 1px solid #00aaff;
                }
            """)
        elif self.role == "assistant":
            self.setStyleSheet("""
                ChatMessageWidget {
                    background-color: #1a2e1a;
                    border-radius: 8px;
                    border: 1px solid #00ff66;
                }
            """)
        else:
            self.setStyleSheet("""
                ChatMessageWidget {
                    background-color: #2e2a1a;
                    border-radius: 8px;
                    border: 1px solid #ffaa00;
                }
            """)


class TaskProgressWidget(QFrame):
    """Task progress widget."""

    def __init__(self, task: Task, parent=None):
        super().__init__(parent)
        self.task = task
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        # Header
        header_layout = QHBoxLayout()
        title = QLabel(self.task.goal[:50] + "..." if len(self.task.goal) > 50 else self.task.goal)
        title.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        title.setStyleSheet("color: #ffffff;")
        header_layout.addWidget(title)
        header_layout.addStretch()

        # Status badge
        self.status_label = QLabel(self.task.status.value.upper())
        self.status_label.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        self._update_status_color()
        header_layout.addWidget(self.status_label)

        layout.addLayout(header_layout)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(int(self.task.progress * 100))
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #333;
                border-radius: 4px;
                background-color: #1a1a2e;
                text-align: center;
                color: #ffffff;
            }
            QProgressBar::chunk {
                background-color: #00aaff;
                border-radius: 3px;
            }
        """)
        layout.addWidget(self.progress_bar)

        # Current step
        self.step_label = QLabel("")
        self.step_label.setFont(QFont("Segoe UI", 8))
        self.step_label.setStyleSheet("color: #888888;")
        self.step_label.setWordWrap(True)
        layout.addWidget(self.step_label)

        self.setStyleSheet("""
            TaskProgressWidget {
                background-color: #16161e;
                border-radius: 8px;
                border: 1px solid #333;
            }
        """)

    def _update_status_color(self) -> None:
        """Update status label color."""
        colors = {
            TaskStatus.PENDING: "#888888",
            TaskStatus.PLANNING: "#ffaa00",
            TaskStatus.RUNNING: "#00aaff",
            TaskStatus.WAITING_APPROVAL: "#ff6600",
            TaskStatus.COMPLETED: "#00ff66",
            TaskStatus.FAILED: "#ff4444",
            TaskStatus.CANCELLED: "#888888",
        }
        color = colors.get(self.task.status, "#888888")
        self.status_label.setStyleSheet(f"color: {color}; padding: 2px 8px; border-radius: 4px; background-color: {color}22;")

    def update_task(self, task: Task) -> None:
        """Update with new task data."""
        self.task = task
        self.progress_bar.setValue(int(task.progress * 100))
        self.status_label.setText(task.status.value.upper())
        self._update_status_color()

        if task.current_step:
            self.step_label.setText(f"→ {task.current_step.description}")
        else:
            self.step_label.setText("")


class SidePanel(QWidget):
    """Main side panel widget."""

    # Signals
    send_message = Signal(str)
    toggle_voice = Signal()
    open_settings = Signal()
    open_command_center = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self.settings = get_settings()
        self._current_task: Optional[Task] = None
        self._chat_history: List[dict] = []

        self._setup_ui()
        self._apply_theme()

    def _setup_ui(self) -> None:
        """Setup UI."""
        self.setFixedWidth(340)
        self.setMinimumHeight(600)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = self._create_header()
        layout.addWidget(header)

        # Chat area
        self.chat_scroll = QScrollArea()
        self.chat_scroll.setWidgetResizable(True)
        self.chat_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.chat_scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            QScrollBar:vertical {
                background: #1a1a2e;
                width: 8px;
                border: none;
            }
            QScrollBar::handle:vertical {
                background: #333;
                border-radius: 4px;
                min-height: 30px;
            }
        """)

        self.chat_container = QWidget()
        self.chat_layout = QVBoxLayout(self.chat_container)
        self.chat_layout.setContentsMargins(12, 12, 12, 12)
        self.chat_layout.setSpacing(8)
        self.chat_layout.addStretch()

        self.chat_scroll.setWidget(self.chat_container)
        layout.addWidget(self.chat_scroll, 1)

        # Task progress area
        self.task_widget = TaskProgressWidget(Task(goal="No active task"))
        self.task_widget.hide()
        layout.addWidget(self.task_widget)

        # Input area
        input_area = self._create_input_area()
        layout.addWidget(input_area)

    def _create_header(self) -> QWidget:
        """Create header."""
        header = QWidget()
        header.setFixedHeight(60)
        header.setStyleSheet("background-color: #16161e; border-bottom: 1px solid #333;")

        layout = QHBoxLayout(header)
        layout.setContentsMargins(16, 0, 16, 0)

        # Logo/Title
        title_layout = QHBoxLayout()
        title_layout.setSpacing(8)

        # Orb indicator
        self.orb_indicator = QLabel("◉")
        self.orb_indicator.setFont(QFont("Segoe UI", 16))
        self.orb_indicator.setStyleSheet("color: #00aaff;")
        title_layout.addWidget(self.orb_indicator)

        title = QLabel("JARVIS")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title.setStyleSheet("color: #ffffff;")
        title_layout.addWidget(title)

        layout.addLayout(title_layout)
        layout.addStretch()

        # Buttons
        btn_style = """
            QPushButton {
                background: transparent;
                border: none;
                color: #888;
                font-size: 14px;
                padding: 8px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background: #2a2a3e;
                color: #fff;
            }
        """

        self.voice_btn = QPushButton("🎤")
        self.voice_btn.setToolTip("Toggle Voice (Ctrl+Space)")
        self.voice_btn.setStyleSheet(btn_style)
        self.voice_btn.clicked.connect(self.toggle_voice.emit)
        layout.addWidget(self.voice_btn)

        self.cmd_center_btn = QPushButton("☰")
        self.cmd_center_btn.setToolTip("Command Center")
        self.cmd_center_btn.setStyleSheet(btn_style)
        self.cmd_center_btn.clicked.connect(self.open_command_center.emit)
        layout.addWidget(self.cmd_center_btn)

        self.settings_btn = QPushButton("⚙")
        self.settings_btn.setToolTip("Settings")
        self.settings_btn.setStyleSheet(btn_style)
        self.settings_btn.clicked.connect(self.open_settings.emit)
        layout.addWidget(self.settings_btn)

        return header

    def _create_input_area(self) -> QWidget:
        """Create input area."""
        input_widget = QWidget()
        input_widget.setFixedHeight(80)
        input_widget.setStyleSheet("background-color: #16161e; border-top: 1px solid #333;")

        layout = QVBoxLayout(input_widget)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(4)

        # Input field
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Type a command or ask JARVIS...")
        self.input_field.setFont(QFont("Segoe UI", 10))
        self.input_field.setStyleSheet("""
            QLineEdit {
                background-color: #1a1a2e;
                border: 1px solid #333;
                border-radius: 6px;
                padding: 8px 12px;
                color: #ffffff;
                selection-background-color: #00aaff;
            }
            QLineEdit:focus {
                border: 1px solid #00aaff;
            }
        """)
        self.input_field.returnPressed.connect(self._on_send)
        layout.addWidget(self.input_field)

        # Hint
        hint = QLabel("Press Enter to send • Ctrl+Enter for new line")
        hint.setFont(QFont("Segoe UI", 7))
        hint.setStyleSheet("color: #666;")
        layout.addWidget(hint)

        return input_widget

    def _apply_theme(self) -> None:
        """Apply theme."""
        theme = self.settings.ui.theme
        if theme == "dark":
            self.setStyleSheet("background-color: #1a1a2e;")
        else:
            self.setStyleSheet("background-color: #f0f0f0; color: #333;")

    def _on_send(self) -> None:
        """Handle send message."""
        text = self.input_field.text().strip()
        if text:
            self.send_message.emit(text)
            self.input_field.clear()

    def add_message(self, role: str, content: str) -> None:
        """Add message to chat."""
        msg_widget = ChatMessageWidget(role, content)
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, msg_widget)
        self._chat_history.append({"role": role, "content": content})

        # Auto-scroll
        QTimer.singleShot(50, lambda: self.chat_scroll.verticalScrollBar().setValue(
            self.chat_scroll.verticalScrollBar().maximum()
        ))

    def set_task(self, task: Optional[Task]) -> None:
        """Set current task."""
        self._current_task = task
        if task:
            self.task_widget.show()
            self.task_widget.update_task(task)
        else:
            self.task_widget.hide()

    def update_task(self, task: Task) -> None:
        """Update current task."""
        if self._current_task and self._current_task.id == task.id:
            self._current_task = task
            self.task_widget.update_task(task)

    def set_orb_state(self, state: str) -> None:
        """Update orb indicator."""
        colors = {
            "idle": "#00aaff",
            "listening": "#00ff66",
            "thinking": "#ffaa00",
            "executing": "#00aaff",
            "success": "#00ff66",
            "error": "#ff4444",
            "speaking": "#aa66ff",
        }
        color = colors.get(state, "#00aaff")
        self.orb_indicator.setStyleSheet(f"color: {color};")


class SidePanelController:
    """Controller for side panel."""

    def __init__(self, panel: SidePanel):
        self.panel = panel

    def show(self) -> None:
        self.panel.show()

    def hide(self) -> None:
        self.panel.hide()

    def toggle(self) -> None:
        if self.panel.isVisible():
            self.hide()
        else:
            self.show()