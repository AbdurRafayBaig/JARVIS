"""Notification Widget

Provides toast notification display.
"""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QHBoxLayout
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont
from loguru import logger


class ToastNotification(QWidget):
    """Toast notification popup."""

    closed = Signal()

    def __init__(
        self,
        title: str,
        message: str,
        level: str = "info",
        duration: int = 3000,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedWidth(300)

        self._level = level
        self._init_ui(title, message)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.close)
        self._timer.start(duration)

    def _init_ui(self, title: str, message: str):
        """Initialize the UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        container = QWidget()
        container.setStyleSheet(self._get_stylesheet())
        container_layout = QVBoxLayout(container)

        title_label = QLabel(title)
        title_label.setFont(QFont("Segoe UI", 10, QFont.Bold))
        container_layout.addWidget(title_label)

        message_label = QLabel(message)
        message_label.setWordWrap(True)
        container_layout.addWidget(message_label)

        layout.addWidget(container)

    def _get_stylesheet(self) -> str:
        """Get stylesheet based on notification level."""
        colors = {
            "info": "#3498db",
            "success": "#2ecc71",
            "warning": "#f39c12",
            "error": "#e74c3c",
        }
        color = colors.get(self._level, "#3498db")

        return f"""
            QWidget {{
                background-color: {color}20;
                border: 1px solid {color};
                border-radius: 8px;
                padding: 10px;
            }}
            QLabel {{
                color: white;
                background: transparent;
            }}
        """

    def close(self):
        """Close the notification."""
        self.closed.emit()
        super().close()


class NotificationManager(QWidget):
    """Manages toast notifications."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._notifications = []
        self._offset = 0

    def show_notification(
        self,
        title: str,
        message: str,
        level: str = "info",
        duration: int = 3000,
    ):
        """Show a toast notification."""
        notification = ToastNotification(title, message, level, duration, self)
        notification.closed.connect(lambda: self._on_notification_closed(notification))

        if self.parent():
            parent_rect = self.parent().geometry()
            x = parent_rect.right() - 320
            y = parent_rect.bottom() - 50 - self._offset
            notification.move(x, y)

        notification.show()
        self._notifications.append(notification)
        self._offset += 80

    def _on_notification_closed(self, notification):
        """Handle notification closed."""
        if notification in self._notifications:
            self._notifications.remove(notification)
            self._offset = max(0, self._offset - 80)

    def clear_all(self):
        """Clear all notifications."""
        for notification in self._notifications:
            notification.close()
        self._notifications.clear()
        self._offset = 0
