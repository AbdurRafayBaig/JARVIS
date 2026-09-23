"""JARVIS UI - Floating Orb"""

from enum import Enum
from typing import Optional
from PySide6.QtCore import (
    Qt, QTimer, QPropertyAnimation, QEasingCurve,
    QPoint, QRect, Signal, QObject, QSize
)
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QGraphicsDropShadowEffect
)
from PySide6.QtGui import (
    QPainter, QColor, QBrush, QPen, QFont, QPixmap,
    QIcon, QCursor, QGuiApplication
)

from jarvis.core.config import get_settings
from jarvis.core.logging import get_logger

logger = get_logger(__name__)


class OrbState(Enum):
    """Orb visual states."""
    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    EXECUTING = "executing"
    SUCCESS = "success"
    ERROR = "error"
    SPEAKING = "speaking"


class FloatingOrb(QWidget):
    """Floating JARVIS orb widget."""

    # Signals
    clicked = Signal()
    right_clicked = Signal()
    state_changed = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self.settings = get_settings()
        self._state = OrbState.IDLE
        self._animation_timer = QTimer()
        self._pulse_animation: Optional[QPropertyAnimation] = None
        self._drag_position: Optional[QPoint] = None

        self._setup_ui()
        self._setup_animations()
        self._position_orb()

    def _setup_ui(self) -> None:
        """Setup UI."""
        # Window flags - frameless, always on top, tool window
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool |
            Qt.WindowType.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        # Size
        size = self._get_size()
        self.setFixedSize(size, size)

        # Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Orb button
        self.orb_button = QPushButton()
        self.orb_button.setFixedSize(size, size)
        self.orb_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.orb_button.clicked.connect(self._on_clicked)
        self.orb_button.setStyleSheet("""
            QPushButton {
                border: none;
                background: transparent;
            }
        """)

        layout.addWidget(self.orb_button)

        # Shadow effect
        self.shadow = QGraphicsDropShadowEffect()
        self.shadow.setBlurRadius(20)
        self.shadow.setColor(QColor(0, 150, 255, 100))
        self.shadow.setOffset(0, 0)
        self.orb_button.setGraphicsEffect(self.shadow)

        # Tooltip
        self.setToolTip("JARVIS - Click to interact\nRight-click for menu\nCtrl+Space to toggle")

    def _get_size(self) -> int:
        """Get orb size from settings."""
        sizes = {"compact": 48, "standard": 64, "large": 80}
        return sizes.get(self.settings.ui.floating_orb_size, 64)

    def _position_orb(self) -> None:
        """Position orb on screen."""
        screen = QGuiApplication.primaryScreen()
        if not screen:
            return

        geometry = screen.availableGeometry()
        size = self._get_size()
        margin = 20

        if self.settings.ui.floating_orb_position == "left":
            x = margin
        else:
            x = geometry.width() - size - margin

        y = (geometry.height() - size) // 2
        self.move(x, y)

    def _setup_animations(self) -> None:
        """Setup state animations."""
        self._animation_timer.timeout.connect(self._animate_pulse)
        self._animation_timer.setInterval(50)

    def _animate_pulse(self) -> None:
        """Animate pulse effect."""
        self.update()

    @property
    def state(self) -> OrbState:
        return self._state

    @state.setter
    def state(self, value: OrbState) -> None:
        if self._state != value:
            self._state = value
            self.state_changed.emit(value.value)
            self._update_appearance()
            self.update()

    def _update_appearance(self) -> None:
        """Update visual appearance based on state."""
        colors = {
            OrbState.IDLE: QColor(0, 150, 255, 180),
            OrbState.LISTENING: QColor(0, 255, 100, 220),
            OrbState.THINKING: QColor(255, 200, 0, 220),
            OrbState.EXECUTING: QColor(0, 180, 255, 220),
            OrbState.SUCCESS: QColor(0, 255, 100, 220),
            OrbState.ERROR: QColor(255, 50, 50, 220),
            OrbState.SPEAKING: QColor(200, 100, 255, 220),
        }

        color = colors.get(self._state, colors[OrbState.IDLE])

        # Update shadow
        self.shadow.setColor(QColor(color.red(), color.green(), color.blue(), 150))

        # Start/stop pulse animation
        if self._state in (OrbState.LISTENING, OrbState.THINKING, OrbState.EXECUTING, OrbState.SPEAKING):
            self._animation_timer.start()
        else:
            self._animation_timer.stop()

    def paintEvent(self, event) -> None:
        """Custom paint for orb."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        size = self._get_size()
        center = size // 2
        radius = center - 4

        # State colors
        colors = {
            OrbState.IDLE: QColor(0, 150, 255, 180),
            OrbState.LISTENING: QColor(0, 255, 100, 220),
            OrbState.THINKING: QColor(255, 200, 0, 220),
            OrbState.EXECUTING: QColor(0, 180, 255, 220),
            OrbState.SUCCESS: QColor(0, 255, 100, 220),
            OrbState.ERROR: QColor(255, 50, 50, 220),
            OrbState.SPEAKING: QColor(200, 100, 255, 220),
        }

        base_color = colors.get(self._state, colors[OrbState.IDLE])

        # Draw outer glow
        if self._state in (OrbState.LISTENING, OrbState.THINKING, OrbState.EXECUTING, OrbState.SPEAKING):
            import math
            pulse = (1 + math.sin(self._animation_timer.remainingTime() * 0.01)) * 0.5
            glow_radius = int(radius + 10 * pulse)
            glow_color = QColor(base_color)
            glow_color.setAlpha(int(50 * pulse))
            painter.setBrush(QBrush(glow_color))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(center - glow_radius, center - glow_radius, glow_radius * 2, glow_radius * 2)

        # Draw main orb
        painter.setBrush(QBrush(base_color))
        painter.setPen(QPen(QColor(255, 255, 255, 50), 2))
        painter.drawEllipse(center - radius, center - radius, radius * 2, radius * 2)

        # Draw inner indicator
        inner_radius = radius // 2
        painter.setBrush(QBrush(QColor(255, 255, 255, 200)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(center - inner_radius, center - inner_radius, inner_radius * 2, inner_radius * 2)

        # State-specific indicators
        if self._state == OrbState.LISTENING:
            # Mic icon
            self._draw_mic_icon(painter, center, inner_radius)
        elif self._state == OrbState.THINKING:
            # Thinking dots
            self._draw_thinking_dots(painter, center, inner_radius)
        elif self._state == OrbState.EXECUTING:
            # Spinner
            self._draw_spinner(painter, center, inner_radius)

    def _draw_mic_icon(self, painter: QPainter, center: int, radius: int) -> None:
        """Draw microphone icon."""
        painter.setPen(QPen(QColor(0, 150, 255), 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)

        # Mic body
        mic_rect = QRect(center - radius // 2, center - radius, radius, radius * 2)
        painter.drawRoundedRect(mic_rect, 3, 3)

        # Mic stand
        painter.drawLine(center, center + radius, center, center + radius + 4)
        painter.drawLine(center - 4, center + radius + 4, center + 4, center + radius + 4)

    def _draw_thinking_dots(self, painter: QPainter, center: int, radius: int) -> None:
        """Draw thinking animation dots."""
        import time
        t = time.time() * 2
        painter.setBrush(QBrush(QColor(255, 200, 0)))

        for i in range(3):
            offset = (i - 1) * (radius // 1.5)
            y = center + int(radius * 0.3 * abs((t + i * 0.5) % 2 - 1))
            painter.drawEllipse(center + offset - 3, y - 3, 6, 6)

    def _draw_spinner(self, painter: QPainter, center: int, radius: int) -> None:
        """Draw executing spinner."""
        import time
        t = time.time() * 4
        painter.setPen(QPen(QColor(0, 180, 255), 3))

        for i in range(8):
            angle = (t + i * 45) % 360
            alpha = 255 - i * 25
            painter.setPen(QPen(QColor(0, 180, 255, alpha), 3))

            x1 = center + int((radius - 6) * 0.7 * (angle / 360))
            y1 = center + int((radius - 6) * 0.7 * (angle / 360))
            # Simplified - just draw rotating arc
            pass

    def _on_clicked(self) -> None:
        """Handle click."""
        self.clicked.emit()

    def mousePressEvent(self, event) -> None:
        """Handle mouse press for dragging."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
        elif event.button() == Qt.MouseButton.RightButton:
            self.right_clicked.emit()

    def mouseMoveEvent(self, event) -> None:
        """Handle mouse move for dragging."""
        if event.buttons() & Qt.MouseButton.LeftButton and self._drag_position:
            self.move(event.globalPosition().toPoint() - self._drag_position)
            event.accept()

    def mouseReleaseEvent(self, event) -> None:
        """Handle mouse release."""
        self._drag_position = None

    def enterEvent(self, event) -> None:
        """Mouse enter."""
        self.shadow.setBlurRadius(30)

    def leaveEvent(self, event) -> None:
        """Mouse leave."""
        self.shadow.setBlurRadius(20)


class OrbController(QObject):
    """Controller for floating orb."""

    def __init__(self, orb: FloatingOrb):
        super().__init__()
        self.orb = orb
        self._visible = True

    def show(self) -> None:
        """Show orb."""
        if not self._visible:
            self.orb.show()
            self._visible = True

    def hide(self) -> None:
        """Hide orb."""
        if self._visible:
            self.orb.hide()
            self._visible = False

    def toggle(self) -> None:
        """Toggle visibility."""
        if self._visible:
            self.hide()
        else:
            self.show()

    def set_state(self, state: OrbState) -> None:
        """Set orb state."""
        self.orb.state = state