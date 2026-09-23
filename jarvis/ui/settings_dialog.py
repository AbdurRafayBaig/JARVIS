"""Settings Dialog

Provides a settings editor for all configuration categories.
"""

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QTabWidget,
    QWidget,
    QFormLayout,
    QLineEdit,
    QComboBox,
    QSpinBox,
    QCheckBox,
    QPushButton,
    QLabel,
    QGroupBox,
)
from PySide6.QtCore import Qt
from loguru import logger

from jarvis.core.config import get_settings, reload_settings


class SettingsDialog(QDialog):
    """Settings editor dialog."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("JARVIS Settings")
        self.setMinimumSize(600, 500)
        self._settings = get_settings()
        self._init_ui()

    def _init_ui(self):
        """Initialize the UI."""
        layout = QVBoxLayout(self)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        self._create_llm_tab()
        self._create_voice_tab()
        self._create_agent_tab()
        self._create_ui_tab()

        button_layout = QHBoxLayout()
        button_layout.addStretch()

        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self._save_settings)
        button_layout.addWidget(save_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        layout.addLayout(button_layout)

    def _create_llm_tab(self):
        """Create LLM settings tab."""
        widget = QWidget()
        layout = QFormLayout(widget)

        self.llm_provider = QComboBox()
        self.llm_provider.addItems(["openai", "anthropic", "ollama", "azure"])
        self.llm_provider.setCurrentText(self._settings.llm.provider)
        layout.addRow("Provider:", self.llm_provider)

        self.llm_api_key = QLineEdit()
        self.llm_api_key.setEchoMode(QLineEdit.Password)
        self.llm_api_key.setText(self._settings.llm.api_key or "")
        layout.addRow("API Key:", self.llm_api_key)

        self.llm_model = QLineEdit()
        self.llm_model.setText(self._settings.llm.model)
        layout.addRow("Model:", self.llm_model)

        self.tabs.addTab(widget, "LLM")

    def _create_voice_tab(self):
        """Create voice settings tab."""
        widget = QWidget()
        layout = QFormLayout(widget)

        self.stt_provider = QComboBox()
        self.stt_provider.addItems(["whisper", "google"])
        self.stt_provider.setCurrentText(self._settings.stt.provider)
        layout.addRow("STT Provider:", self.stt_provider)

        self.tts_provider = QComboBox()
        self.tts_provider.addItems(["piper", "edge"])
        self.tts_provider.setCurrentText(self._settings.tts.provider)
        layout.addRow("TTS Provider:", self.tts_provider)

        self.wake_word = QCheckBox()
        self.wake_word.setChecked(self._settings.voice.wake_word_enabled)
        layout.addRow("Wake Word:", self.wake_word)

        self.tabs.addTab(widget, "Voice")

    def _create_agent_tab(self):
        """Create agent settings tab."""
        widget = QWidget()
        layout = QFormLayout(widget)

        self.max_iterations = QSpinBox()
        self.max_iterations.setRange(1, 100)
        self.max_iterations.setValue(self._settings.agent.max_iterations)
        layout.addRow("Max Iterations:", self.max_iterations)

        self.require_approval = QCheckBox()
        self.require_approval.setChecked(self._settings.security.require_approval)
        layout.addRow("Require Approval:", self.require_approval)

        self.sandbox = QCheckBox()
        self.sandbox.setChecked(self._settings.security.sandbox_enabled)
        layout.addRow("Enable Sandbox:", self.sandbox)

        self.tabs.addTab(widget, "Agent")

    def _create_ui_tab(self):
        """Create UI settings tab."""
        widget = QWidget()
        layout = QFormLayout(widget)

        self.theme = QComboBox()
        self.theme.addItems(["dark", "light", "system"])
        self.theme.setCurrentText(self._settings.ui.theme)
        layout.addRow("Theme:", self.theme)

        self.opacity = QSpinBox()
        self.opacity.setRange(50, 100)
        self.opacity.setValue(int(self._settings.ui.opacity * 100))
        layout.addRow("Opacity (%):", self.opacity)

        self.tabs.addTab(widget, "UI")

    def _save_settings(self):
        """Save settings to .env file."""
        try:
            settings = {
                "LLM_PROVIDER": self.llm_provider.currentText(),
                "LLM_API_KEY": self.llm_api_key.text(),
                "LLM_MODEL": self.llm_model.text(),
                "STT_PROVIDER": self.stt_provider.currentText(),
                "TTS_PROVIDER": self.tts_provider.currentText(),
                "VOICE_WAKE_WORD_ENABLED": str(self.wake_word.isChecked()).lower(),
                "AGENT_MAX_ITERATIONS": str(self.max_iterations.value()),
                "SECURITY_REQUIRE_APPROVAL": str(self.require_approval.isChecked()).lower(),
                "SECURITY_SANDBOX_ENABLED": str(self.sandbox.isChecked()).lower(),
                "UI_THEME": self.theme.currentText(),
                "UI_OPACITY": str(self.opacity.value() / 100),
            }

            env_path = Path(".env")
            lines = []
            if env_path.exists():
                lines = env_path.read_text().splitlines()

            for key, value in settings.items():
                found = False
                for i, line in enumerate(lines):
                    if line.startswith(f"{key}="):
                        lines[i] = f"{key}={value}"
                        found = True
                        break
                if not found:
                    lines.append(f"{key}={value}")

            env_path.write_text("\n".join(lines) + "\n")
            reload_settings()

            logger.info("Settings saved")
            self.accept()

        except Exception as e:
            logger.error(f"Failed to save settings: {e}")
