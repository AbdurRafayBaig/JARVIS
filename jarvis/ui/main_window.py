"""JARVIS UI - Main Window"""

import sys
from typing import Optional
import asyncio

from PySide6.QtCore import Qt, QTimer, Signal, QPoint, QRect
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QApplication, QSystemTrayIcon, QMenu, QMessageBox
)
from PySide6.QtGui import (
    QIcon, QAction, QPixmap, QPainter, QColor, QFont, QShortcut, QKeySequence
)
from PySide6.QtWidgets import QStyle

from jarvis.ui.floating_orb import FloatingOrb, OrbState, OrbController
from jarvis.ui.side_panel import SidePanel, SidePanelController
from jarvis.core.config import get_settings
from jarvis.core.logging import get_logger

logger = get_logger(__name__)


class MainWindow(QMainWindow):
    """Main JARVIS window - hidden by default, shows side panel."""

    # Signals
    toggle_panel_requested = Signal()
    toggle_voice = Signal()
    open_settings = Signal()
    open_command_center = Signal()
    quit_requested = Signal()

    def __init__(self):
        super().__init__()

        self.settings = get_settings()
        self._panel_visible = False
        self._voice_enabled = True
        self.agent = None

        self._setup_ui()
        self._setup_tray()
        self._setup_hotkeys()

    def _setup_ui(self) -> None:
        """Setup main window UI."""
        # Window properties
        self.setWindowTitle("JARVIS")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        # Central widget
        central = QWidget()
        central.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCentralWidget(central)

        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Side panel (hidden by default)
        self.side_panel = SidePanel()
        self.side_panel.hide()
        self.side_panel.send_message.connect(self._on_user_message)
        self.side_panel.toggle_voice.connect(self.toggle_voice.emit)
        self.side_panel.open_settings.connect(self.open_settings.emit)
        self.side_panel.open_command_center.connect(self.open_command_center.emit)

        layout.addWidget(self.side_panel)
        layout.addStretch()

        # Position window to cover screen for panel sliding
        self._position_window()

        # Panel controller
        self.panel_controller = SidePanelController(self.side_panel)

        # Orb
        self.orb = FloatingOrb()
        self.orb.clicked.connect(self._on_orb_clicked)
        self.orb.right_clicked.connect(self._show_orb_menu)
        self.orb.state_changed.connect(self._on_orb_state_changed)

        self.orb_controller = OrbController(self.orb)

    def _position_window(self) -> None:
        """Position window to cover screen."""
        screen = QApplication.primaryScreen()
        if screen:
            geometry = screen.geometry()
            self.setGeometry(geometry)

    def _setup_tray(self) -> None:
        """Setup system tray icon."""
        # Create tray icon
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(self._create_tray_icon())

        # Tray menu
        tray_menu = QMenu()

        show_action = QAction("Show Panel", self)
        show_action.triggered.connect(self.panel_controller.show)
        tray_menu.addAction(show_action)

        hide_action = QAction("Hide Panel", self)
        hide_action.triggered.connect(self.panel_controller.hide)
        tray_menu.addAction(hide_action)

        tray_menu.addSeparator()

        voice_action = QAction("Toggle Voice", self)
        voice_action.triggered.connect(self.toggle_voice.emit)
        tray_menu.addAction(voice_action)

        tray_menu.addSeparator()

        settings_action = QAction("Settings", self)
        settings_action.triggered.connect(self.open_settings.emit)
        tray_menu.addAction(settings_action)

        cmd_center_action = QAction("Command Center", self)
        cmd_center_action.triggered.connect(self.open_command_center.emit)
        tray_menu.addAction(cmd_center_action)

        tray_menu.addSeparator()

        quit_action = QAction("Quit JARVIS", self)
        quit_action.triggered.connect(self._quit)
        tray_menu.addAction(quit_action)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self._on_tray_activated)
        self.tray_icon.show()

    def _create_tray_icon(self) -> QIcon:
        """Create tray icon."""
        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor(0, 150, 255))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(4, 4, 24, 24)
        painter.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        painter.setPen(QColor(255, 255, 255))
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "J")
        painter.end()

        return QIcon(pixmap)

    def _setup_hotkeys(self) -> None:
        """Setup window-local shortcuts.

        System-wide hotkeys are owned by jarvis.services.hotkeys, which
        registers them with Windows; Qt shortcuts only fire when a JARVIS
        window has focus, so they are the in-window equivalents.
        """
        toggle = QShortcut(QKeySequence("Ctrl+Space"), self)
        toggle.setContext(Qt.ShortcutContext.ApplicationShortcut)
        toggle.activated.connect(self.toggle_panel_requested.emit)

        hide = QShortcut(QKeySequence("Esc"), self)
        hide.setContext(Qt.ShortcutContext.ApplicationShortcut)
        hide.activated.connect(self.panel_controller.hide)

    def _on_orb_clicked(self) -> None:
        """Handle orb click."""
        self.panel_controller.toggle()

    def _on_orb_state_changed(self, state: str) -> None:
        """Handle orb state change."""
        self.side_panel.set_orb_state(state)

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        """Handle tray activation."""
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.panel_controller.toggle()

    def _show_orb_menu(self) -> None:
        """Show orb right-click menu."""
        menu = QMenu()

        panel_action = QAction("Toggle Panel", self)
        panel_action.triggered.connect(self.panel_controller.toggle)
        menu.addAction(panel_action)

        voice_action = QAction("Toggle Voice", self)
        voice_action.triggered.connect(self.toggle_voice.emit)
        menu.addAction(voice_action)

        menu.addSeparator()

        settings_action = QAction("Settings", self)
        settings_action.triggered.connect(self.open_settings.emit)
        menu.addAction(settings_action)

        cmd_action = QAction("Command Center", self)
        cmd_action.triggered.connect(self.open_command_center.emit)
        menu.addAction(cmd_action)

        menu.addSeparator()

        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self._quit)
        menu.addAction(quit_action)

        menu.exec(self.orb.mapToGlobal(QPoint(0, 0)))

    def set_agent(self, agent) -> None:
        """Set agent instance."""
        self.agent = agent

    def _on_user_message(self, message: str) -> None:
        """Handle user message from panel."""
        self.side_panel.add_message("user", message)
        logger.info(f"User message: {message}")

        if hasattr(self, "agent") and self.agent:
            import asyncio
            self.set_orb_state(OrbState.THINKING)
            asyncio.create_task(self._process_user_message(message))
        else:
            self.side_panel.add_message("assistant", "Agent runtime is not initialized.")

    async def _process_user_message(self, message: str) -> None:
        """Process user message using agent."""
        try:
            self.set_orb_state(OrbState.EXECUTING)
            task = await self.agent.execute_task(message)

            if task.status.value == "completed":
                self.set_orb_state(OrbState.SUCCESS)
                response = task.result or "Task completed successfully."
            else:
                self.set_orb_state(OrbState.ERROR)
                response = task.result or f"Error: {task.error}"

            self.side_panel.add_message("assistant", response)

        except Exception as e:
            logger.error(f"Error processing message in UI: {e}")
            self.set_orb_state(OrbState.ERROR)
            self.side_panel.add_message("assistant", f"Error: {e}")
        finally:
            # Revert orb state back to IDLE after 3 seconds
            QTimer.singleShot(3000, lambda: self.set_orb_state(OrbState.IDLE))

    async def request_approval(self, tool_name: str, tool_args) -> bool:
        """Ask the user to approve a sensitive or dangerous tool call."""
        self.panel_controller.show()
        self.set_orb_state(OrbState.IDLE)

        box = QMessageBox(self)
        box.setWindowTitle("JARVIS - Approval Required")
        box.setIcon(QMessageBox.Icon.Warning)
        box.setText(f"Allow JARVIS to run '{tool_name}'?")
        box.setInformativeText(str(tool_args)[:1000])
        box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        box.setDefaultButton(QMessageBox.StandardButton.No)

        # exec() spins Qt's own loop, so run it without blocking asyncio.
        future = asyncio.get_running_loop().create_future()

        def finished(result: int) -> None:
            if not future.done():
                future.set_result(int(result) == int(QMessageBox.StandardButton.Yes))

        box.finished.connect(finished)
        box.open()

        approved = await future
        self.side_panel.add_message(
            "system",
            f"{'Approved' if approved else 'Denied'}: {tool_name}",
        )
        return approved

    def on_wake_word(self) -> None:
        """Show that JARVIS heard its wake word and is listening."""
        self.set_orb_state(OrbState.LISTENING)
        self.panel_controller.show()

    def _quit(self) -> None:
        """Request application quit.

        Only emits: the application performs an async shutdown and then stops
        the event loop. Quitting Qt here would cut that short.
        """
        self.quit_requested.emit()

    def show_panel(self) -> None:
        """Show side panel."""
        if not self._panel_visible:
            self.side_panel.show()
            self._animate_panel_show()
            self._panel_visible = True

    def hide_panel(self) -> None:
        """Hide side panel."""
        if self._panel_visible:
            self._animate_panel_hide()
            self._panel_visible = False

    def _animate_panel_show(self) -> None:
        """Animate panel show."""
        self.side_panel.show()
        # Animation would go here

    def _animate_panel_hide(self) -> None:
        """Animate panel hide."""
        self.side_panel.hide()

    def toggle_panel(self) -> None:
        """Toggle panel visibility."""
        if self._panel_visible:
            self.hide_panel()
        else:
            self.show_panel()

    def set_orb_state(self, state: OrbState) -> None:
        """Set orb state."""
        self.orb_controller.set_state(state)

    def add_message(self, role: str, content: str) -> None:
        """Add message to chat."""
        self.side_panel.add_message(role, content)

    def set_task(self, task) -> None:
        """Set current task."""
        self.side_panel.set_task(task)

    def update_task(self, task) -> None:
        """Update current task."""
        self.side_panel.update_task(task)

    def closeEvent(self, event) -> None:
        """Handle close event."""
        event.ignore()
        self.hide_panel()
        self.orb.hide()


def create_app() -> QApplication:
    """Create QApplication instance."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    app.setApplicationName("JARVIS")
    app.setApplicationDisplayName("JARVIS")
    app.setQuitOnLastWindowClosed(False)
    return app