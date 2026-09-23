"""JARVIS Core Exceptions"""

from typing import Any, Optional


class JarvisError(Exception):
    """Base exception for all JARVIS errors."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "JARVIS_ERROR",
        details: Optional[dict[str, Any]] = None,
        recoverable: bool = True,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}
        self.recoverable = recoverable

    def to_dict(self) -> dict[str, Any]:
        return {
            "error": self.__class__.__name__,
            "code": self.code,
            "message": self.message,
            "details": self.details,
            "recoverable": self.recoverable,
        }


class ConfigurationError(JarvisError):
    """Raised when configuration is invalid or missing."""

    def __init__(self, message: str, **kwargs):
        super().__init__(message, code="CONFIG_ERROR", **kwargs)


class AuthenticationError(JarvisError):
    """Raised when authentication fails."""

    def __init__(self, message: str, **kwargs):
        super().__init__(message, code="AUTH_ERROR", recoverable=False, **kwargs)


class PermissionDeniedError(JarvisError):
    """Raised when an action is denied due to permissions."""

    def __init__(self, message: str, **kwargs):
        super().__init__(message, code="PERMISSION_DENIED", recoverable=False, **kwargs)


class ToolError(JarvisError):
    """Raised when a tool execution fails."""

    def __init__(
        self,
        message: str,
        *,
        tool_name: str,
        tool_args: dict[str, Any],
        **kwargs,
    ):
        super().__init__(message, code="TOOL_ERROR", **kwargs)
        self.tool_name = tool_name
        self.tool_args = tool_args

    def to_dict(self) -> dict[str, Any]:
        base = super().to_dict()
        base["tool_name"] = self.tool_name
        base["tool_args"] = self.tool_args
        return base


class ToolNotFoundError(JarvisError):
    """Raised when a requested tool is not found."""

    def __init__(self, tool_name: str, **kwargs):
        super().__init__(
            f"Tool not found: {tool_name}",
            code="TOOL_NOT_FOUND",
            details={"tool_name": tool_name},
            **kwargs,
        )


class AgentError(JarvisError):
    """Raised when the agent encounters an error."""

    def __init__(self, message: str, **kwargs):
        super().__init__(message, code="AGENT_ERROR", **kwargs)


class PlanningError(JarvisError):
    """Raised when task planning fails."""

    def __init__(self, message: str, **kwargs):
        super().__init__(message, code="PLANNING_ERROR", **kwargs)


class VerificationError(JarvisError):
    """Raised when verification of an action fails."""

    def __init__(
        self,
        message: str,
        *,
        expected: Any = None,
        actual: Any = None,
        **kwargs,
    ):
        super().__init__(message, code="VERIFICATION_ERROR", **kwargs)
        self.expected = expected
        self.actual = actual


class RecoveryError(JarvisError):
    """Raised when error recovery fails."""

    def __init__(self, message: str, **kwargs):
        super().__init__(message, code="RECOVERY_ERROR", recoverable=False, **kwargs)


class VoiceError(JarvisError):
    """Raised when voice processing fails."""

    def __init__(self, message: str, **kwargs):
        super().__init__(message, code="VOICE_ERROR", **kwargs)


class VisionError(JarvisError):
    """Raised when screen vision fails."""

    def __init__(self, message: str, **kwargs):
        super().__init__(message, code="VISION_ERROR", **kwargs)


class BrowserError(JarvisError):
    """Raised when browser automation fails."""

    def __init__(self, message: str, **kwargs):
        super().__init__(message, code="BROWSER_ERROR", **kwargs)


class GitError(JarvisError):
    """Raised when Git operations fail."""

    def __init__(self, message: str, **kwargs):
        super().__init__(message, code="GIT_ERROR", **kwargs)


class GitHubError(JarvisError):
    """Raised when GitHub API operations fail."""

    def __init__(self, message: str, **kwargs):
        super().__init__(message, code="GITHUB_ERROR", **kwargs)


class MemoryError(JarvisError):
    """Raised when memory operations fail."""

    def __init__(self, message: str, **kwargs):
        super().__init__(message, code="MEMORY_ERROR", **kwargs)


class DatabaseError(JarvisError):
    """Raised when database operations fail."""

    def __init__(self, message: str, **kwargs):
        super().__init__(message, code="DATABASE_ERROR", **kwargs)


class UIError(JarvisError):
    """Raised when UI operations fail."""

    def __init__(self, message: str, **kwargs):
        super().__init__(message, code="UI_ERROR", **kwargs)


class ShutdownError(JarvisError):
    """Raised when shutdown fails."""

    def __init__(self, message: str, **kwargs):
        super().__init__(message, code="SHUTDOWN_ERROR", recoverable=False, **kwargs)