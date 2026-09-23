"""JARVIS LLM - Provider Abstraction"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, AsyncGenerator, Optional


@dataclass
class Message:
    """Chat message."""
    role: str  # system, user, assistant, tool
    content: str
    name: Optional[str] = None
    tool_calls: Optional[list[dict[str, Any]]] = None
    tool_call_id: Optional[str] = None


@dataclass
class ChatCompletionResponse:
    """Chat completion response."""
    content: str
    tool_calls: Optional[list[dict[str, Any]]] = None
    finish_reason: str = "stop"
    usage: Optional[dict[str, int]] = None
    model: str = ""
    provider: str = ""


@dataclass
class EmbeddingResponse:
    """Embedding response."""
    embeddings: list[list[float]]
    usage: Optional[dict[str, int]] = None
    model: str = ""
    provider: str = ""


class BaseLLMProvider(ABC):
    """Base class for LLM providers."""

    def __init__(
        self,
        model: str,
        api_key: str = "",
        base_url: str = "",
        temperature: float = 0.2,
        max_tokens: int = 4096,
        **kwargs,
    ):
        self.model = model
        self.api_key = api_key
        self.base_url = base_url
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.extra_config = kwargs

    @abstractmethod
    async def chat_completion(
        self,
        messages: list[Message],
        tools: Optional[list[dict[str, Any]]] = None,
        tool_choice: Optional[str] = None,
        stream: bool = False,
    ) -> ChatCompletionResponse:
        """Generate a chat completion."""
        pass

    @abstractmethod
    async def chat_completion_stream(
        self,
        messages: list[Message],
        tools: Optional[list[dict[str, Any]]] = None,
    ) -> AsyncGenerator[str, None]:
        """Stream chat completion."""
        pass

    @abstractmethod
    async def embeddings(
        self,
        texts: list[str],
    ) -> EmbeddingResponse:
        """Generate embeddings."""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check provider health."""
        pass

    def _build_messages(self, messages: list[Message]) -> list[dict[str, Any]]:
        """Convert messages to provider format."""
        return [
            {
                "role": m.role,
                "content": m.content,
                **({"name": m.name} if m.name else {}),
                **({"tool_calls": m.tool_calls} if m.tool_calls else {}),
                **({"tool_call_id": m.tool_call_id} if m.tool_call_id else {}),
            }
            for m in messages
        ]