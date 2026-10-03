"""Settings Dialog

Provides a settings editor for the configuration categories. Values are
written to the project's .env file under the same variable names that
jarvis.core.config reads.
"""

import asyncio

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
)
from loguru import logger

from jarvis.core.config import get_settings, reload_settings, get_env_path


def update_env_file(path, values: dict[str, str]) -> None:
    """Set KEY=value pairs in a .env file, preserving every other line."""
    lines = []
    if path.exists():
        # utf-8-sig drops a leading BOM, which would otherwise hide the first key.
        lines = path.read_text(encoding="utf-8-sig").splitlines()

    for key, value in values.items():
        for i, line in enumerate(lines):
            if line.strip().startswith(f"{key}="):
                lines[i] = f"{key}={value}"
                break
        else:
            lines.append(f"{key}={value}")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


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

        note = QLabel("Provider and voice changes take effect after restarting JARVIS.")
        note.setStyleSheet("color: #888;")
        layout.addWidget(note)

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
        self.llm_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.llm_api_key.setText(self._settings.llm.api_key or "")
        layout.addRow("API Key:", self.llm_api_key)

        self.llm_model = QLineEdit()
        self.llm_model.setText(self._settings.llm.model)
        layout.addRow("Model:", self.llm_model)

        self.llm_base_url = QLineEdit()
        self.llm_base_url.setText(self._settings.llm.base_url or "")
        self.llm_base_url.setPlaceholderText("Optional - custom endpoint or Ollama URL")
        layout.addRow("Base URL:", self.llm_base_url)

        self.tabs.addTab(widget, "LLM")

    def _create_voice_tab(self):
        """Create voice settings tab."""
        widget = QWidget()
        layout = QFormLayout(widget)

        self.voice_enabled = QCheckBox()
        self.voice_enabled.setChecked(self._settings.voice.enabled)
        layout.addRow("Voice Enabled:", self.voice_enabled)

        self.stt_provider = QComboBox()
        self.stt_provider.addItems(["whisper_cpp", "openai", "google"])
        self.stt_provider.setCurrentText(self._settings.stt.provider)
        layout.addRow("STT Provider:", self.stt_provider)

        self.tts_provider = QComboBox()
        self.tts_provider.addItems(["system", "piper", "edge"])
        self.tts_provider.setCurrentText(self._settings.tts.provider)
        layout.addRow("TTS Provider:", self.tts_provider)

        self.wake_word = QLineEdit()
        self.wake_word.setText(self._settings.voice.wake_word)
        layout.addRow("Wake Word:", self.wake_word)

        self.pv_access_key = QLineEdit()
        self.pv_access_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.pv_access_key.setText(self._settings.voice.pv_access_key or "")
        self.pv_access_key.setPlaceholderText("Picovoice key - needed for hands-free wake word")
        layout.addRow("Picovoice Key:", self.pv_access_key)

        self.tabs.addTab(widget, "Voice")

    def _create_agent_tab(self):
        """Create agent settings tab."""
        widget = QWidget()
        layout = QFormLayout(widget)

        self.max_steps = QSpinBox()
        self.max_steps.setRange(1, 200)
        self.max_steps.setValue(self._settings.agent.max_steps)
        layout.addRow("Max Steps per Task:", self.max_steps)

        self.max_retries = QSpinBox()
        self.max_retries.setRange(0, 10)
        self.max_retries.setValue(self._settings.agent.max_retries)
        layout.addRow("Max Retries:", self.max_retries)

        self.confirm_sensitive = QCheckBox()
        self.confirm_sensitive.setChecked(self._settings.security.require_confirmation_sensitive)
        layout.addRow("Confirm Sensitive Actions:", self.confirm_sensitive)

        self.sandbox = QCheckBox()
        self.sandbox.setChecked(self._settings.security.sandbox_mode)
        layout.addRow("Sandbox Mode (block dangerous tools):", self.sandbox)

        self.audit = QCheckBox()
        self.audit.setChecked(self._settings.security.audit_log_enabled)
        layout.addRow("Audit Log:", self.audit)

        self.tabs.addTab(widget, "Agent")

    def _create_ui_tab(self):
        """Create UI settings tab."""
        widget = QWidget()
        layout = QFormLayout(widget)

        self.theme = QComboBox()
        self.theme.addItems(["dark", "light", "system"])
        self.theme.setCurrentText(self._settings.ui.theme)
        layout.addRow("Theme:", self.theme)

        self.auto_start = QCheckBox()
        self.auto_start.setChecked(self._settings.ui.auto_start)
        layout.addRow("Start with Windows:", self.auto_start)

        self.tabs.addTab(widget, "UI")

    def _collect(self) -> dict[str, str]:
        """Current form values keyed by the env variable config reads."""
        flag = lambda box: str(box.isChecked()).lower()
        return {
            "LLM_PROVIDER": self.llm_provider.currentText(),
            "LLM_API_KEY": self.llm_api_key.text(),
            "LLM_MODEL": self.llm_model.text(),
            "LLM_BASE_URL": self.llm_base_url.text(),
            "VOICE_ENABLED": flag(self.voice_enabled),
            "STT_PROVIDER": self.stt_provider.currentText(),
            "TTS_PROVIDER": self.tts_provider.currentText(),
            "JARVIS_WAKE_WORD": self.wake_word.text().strip() or "jarvis",
            "PV_ACCESS_KEY": self.pv_access_key.text(),
            "MAX_AGENT_STEPS": str(self.max_steps.value()),
            "MAX_RETRIES": str(self.max_retries.value()),
            "REQUIRE_CONFIRMATION_SENSITIVE": flag(self.confirm_sensitive),
            "SANDBOX_MODE": flag(self.sandbox),
            "AUDIT_LOG_ENABLED": flag(self.audit),
            "THEME": self.theme.currentText(),
            "AUTO_START": flag(self.auto_start),
        }

    def _apply_auto_start(self) -> None:
        """Add or remove the Windows startup entry to match the checkbox."""
        from jarvis.services.startup import get_startup_service

        service = get_startup_service()
        action = service.enable() if self.auto_start.isChecked() else service.disable()
        try:
            asyncio.get_running_loop().create_task(action)
        except RuntimeError:
            asyncio.run(action)

    def _save_settings(self):
        """Save settings to the .env file."""
        try:
            import os

            values = self._collect()
            update_env_file(get_env_path(), values)

            # The process environment wins over .env, so update it as well or
            # the reload below would read the old values back.
            os.environ.update(values)
            reload_settings()

            from jarvis.llm.manager import get_llm_manager

            get_llm_manager().reload()
            self._apply_auto_start()

            logger.info("Settings saved")
            self.accept()

        except Exception as e:
            logger.error(f"Failed to save settings: {e}")
