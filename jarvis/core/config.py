"""JARVIS Configuration Management"""

import os
from pathlib import Path
from typing import Optional
from functools import lru_cache

from pydantic import Field, field_validator
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMSettings(BaseSettings):
    """LLM Provider Configuration"""

    model_config = SettingsConfigDict(env_prefix="LLM_", extra="ignore")

    provider: str = Field(default="openai", description="LLM provider: openai, anthropic, ollama, llama_cpp")
    api_key: str = Field(default="", description="API key for the LLM provider")
    model: str = Field(default="gpt-4o", description="Model name")
    base_url: str = Field(default="", description="Base URL for custom endpoints")
    temperature: float = Field(default=0.2, ge=0.0, le=2.0, description="Sampling temperature")
    max_tokens: int = Field(default=4096, gt=0, description="Maximum tokens in response")


class STTSettings(BaseSettings):
    """Speech-to-Text Configuration"""

    model_config = SettingsConfigDict(env_prefix="STT_", extra="ignore")

    provider: str = Field(default="whisper_cpp", description="STT provider: whisper_cpp, openai, google, azure")
    model: str = Field(default="base.en", description="Model name")
    language: str = Field(default="en", description="Language code")
    api_key: str = Field(default="", description="API key for cloud providers")


class TTSSettings(BaseSettings):
    """Text-to-Speech Configuration"""

    model_config = SettingsConfigDict(env_prefix="TTS_", extra="ignore")

    provider: str = Field(default="piper", description="TTS provider: piper, openai, azure, elevenlabs, system")
    model: str = Field(default="en_US-lessac-medium", description="Model/voice name")
    voice: str = Field(default="", description="Specific voice identifier")
    speed: float = Field(default=1.0, ge=0.5, le=2.0, description="Speech speed")
    api_key: str = Field(default="", description="API key for cloud providers")


class VoiceSettings(BaseSettings):
    """Voice System Configuration"""

    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    enabled: bool = Field(default=True, description="Enable voice system")
    wake_word: str = Field(default="jarvis", description="Wake word")
    wake_word_sensitivity: float = Field(default=0.5, ge=0.0, le=1.0, description="Wake word detection sensitivity")
    microphone_device_index: int = Field(default=0, description="Microphone device index")
    speaker_device_index: int = Field(default=0, description="Speaker device index")
    volume: float = Field(default=0.8, ge=0.0, le=1.0, description="Output volume")
    speech_speed: float = Field(default=1.0, ge=0.5, le=2.0, description="Speech speed multiplier")
    silence_timeout: float = Field(default=5.0, gt=0, description="Silence timeout in seconds")
    pv_access_key: str = Field(default="", description="Picovoice Access Key for Porcupine wake word")


class AgentSettings(BaseSettings):
    """Agent Runtime Configuration"""

    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    max_steps: int = Field(default=30, gt=0, description="Maximum agent steps per task")
    max_retries: int = Field(default=3, ge=0, description="Maximum retries for failed steps")
    timeout_seconds: int = Field(default=300, gt=0, description="Task timeout in seconds")
    enable_verification: bool = Field(default=True, description="Enable self-verification")
    enable_recovery: bool = Field(default=True, description="Enable error recovery")


class SecuritySettings(BaseSettings):
    """Security & Permissions Configuration"""

    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    require_confirmation_sensitive: bool = Field(default=True, description="Require confirmation for sensitive actions")
    require_confirmation_dangerous: bool = Field(default=True, description="Require confirmation for dangerous actions")
    audit_log_enabled: bool = Field(default=True, description="Enable audit logging")
    sandbox_mode: bool = Field(default=False, description="Run in sandbox mode")


class UISettings(BaseSettings):
    """UI Configuration"""

    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    auto_start: bool = Field(default=True, description="Start automatically on login")
    start_minimized: bool = Field(default=False, description="Start minimized to tray")
    theme: str = Field(default="dark", description="UI theme: dark, light, system")
    animations_enabled: bool = Field(default=True, description="Enable UI animations")
    floating_orb_position: str = Field(default="right", description="Floating orb position: left, right")
    floating_orb_size: str = Field(default="compact", description="Floating orb size: compact, standard, large")


class GitHubSettings(BaseSettings):
    """GitHub Integration Configuration"""

    model_config = SettingsConfigDict(env_prefix="GITHUB_", extra="ignore")

    token: str = Field(default="", description="GitHub personal access token")
    username: str = Field(default="", description="GitHub username")
    default_visibility: str = Field(default="private", description="Default repo visibility: private, public")


class PathSettings(BaseSettings):
    """Filesystem Paths Configuration"""

    model_config = SettingsConfigDict(env_prefix="JARVIS_", extra="ignore")

    data_dir: str = Field(default="", description="Data directory")
    projects_dir: str = Field(default="", description="Projects directory")
    temp_dir: str = Field(default="", description="Temporary directory")

    @field_validator("data_dir", "projects_dir", "temp_dir", mode="before")
    @classmethod
    def expand_paths(cls, v: str) -> str:
        if not v:
            return v
        return os.path.expandvars(os.path.expanduser(v))


class LoggingSettings(BaseSettings):
    """Logging Configuration"""

    model_config = SettingsConfigDict(env_prefix="LOG_", extra="ignore")

    level: str = Field(default="INFO", description="Log level: DEBUG, INFO, WARNING, ERROR, CRITICAL")
    file_max_mb: int = Field(default=10, gt=0, description="Max log file size in MB")
    file_count: int = Field(default=5, gt=0, description="Number of log files to keep")
    console: bool = Field(default=True, description="Log to console")


class DiagnosticsSettings(BaseSettings):
    """Diagnostics Configuration"""

    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    enabled: bool = Field(default=True, description="Enable diagnostics")
    telemetry_enabled: bool = Field(default=False, description="Enable anonymous telemetry")


class Settings(BaseSettings):
    """Main JARVIS Settings"""

    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parent.parent.parent / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    llm: LLMSettings = Field(default_factory=LLMSettings)
    stt: STTSettings = Field(default_factory=STTSettings)
    tts: TTSSettings = Field(default_factory=TTSSettings)
    voice: VoiceSettings = Field(default_factory=VoiceSettings)
    agent: AgentSettings = Field(default_factory=AgentSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    ui: UISettings = Field(default_factory=UISettings)
    github: GitHubSettings = Field(default_factory=GitHubSettings)
    paths: PathSettings = Field(default_factory=PathSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    diagnostics: DiagnosticsSettings = Field(default_factory=DiagnosticsSettings)

    def get_data_dir(self) -> Path:
        """Get the data directory, creating it if needed."""
        if self.paths.data_dir:
            path = Path(self.paths.data_dir)
        else:
            path = Path.home() / "AppData" / "Roaming" / "Jarvis"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def get_projects_dir(self) -> Path:
        """Get the projects directory."""
        if self.paths.projects_dir:
            path = Path(self.paths.projects_dir)
        else:
            path = Path.home() / "Projects"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def get_temp_dir(self) -> Path:
        """Get the temp directory."""
        if self.paths.temp_dir:
            path = Path(self.paths.temp_dir)
        else:
            path = Path(os.environ.get("TEMP", "/tmp")) / "jarvis"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def get_log_dir(self) -> Path:
        """Get the log directory."""
        path = self.get_data_dir() / "logs"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def get_db_path(self) -> Path:
        """Get the database path."""
        return self.get_data_dir() / "jarvis.db"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Get cached settings instance."""
    load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env", override=False)
    return Settings()


def reload_settings() -> Settings:
    """Reload settings from environment."""
    get_settings.cache_clear()
    return get_settings()
