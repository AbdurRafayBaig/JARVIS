"""JARVIS LLM - Ollama Provider"""

import json
from typing import Any, AsyncGenerator, Optional

import httpx

from jarvis.llm.providers import (
    BaseLLMProvider,
    Message,
    ChatCompletionResponse,
    EmbeddingResponse,
)
from jarvis.core.logging import get_logger

logger = get_logger(__name__)


class OllamaProvider(BaseLLMProvider):
    """Ollama local LLM provider."""

    def __init__(
        self,
        model: str = "llama3.1",
        api_key: str = "",
        base_url: str = "http://localhost:11434",
        temperature: float = 0.2,
        max_tokens: int = 4096,
        **kwargs,
    ):
        super().__init__(model, api_key, base_url, temperature, max_tokens, **kwargs)

        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient(base_url=self.base_url, timeout=120.0)

    def _build_messages(self, messages: list[Message]) -> list[dict[str, Any]]:
        """Convert messages to Ollama format."""
        ollama_messages = []
        for m in messages:
            if m.role == "tool":
                ollama_messages.append({
                    "role": "tool",
                    "content": m.content,
                    "name": m.name or "",
                })
            elif m.role == "assistant" and m.tool_calls:
                ollama_messages.append({
                    "role": "assistant",
                    "content": m.content or "",
                    "tool_calls": m.tool_calls,
                })
            else:
                ollama_messages.append({"role": m.role, "content": m.content})
        return ollama_messages

    def _convert_tools(self, tools: Optional[list[dict[str, Any]]]) -> Optional[list[dict[str, Any]]]:
        """Convert OpenAI tool format to Ollama format."""
        if not tools:
            return None

        ollama_tools = []
        for tool in tools:
            if tool.get("type") == "function":
                fn = tool["function"]
                ollama_tools.append({
                    "type": "function",
                    "function": {
                        "name": fn["name"],
                        "description": fn["description"],
                        "parameters": fn["parameters"],
                    },
                })
        return ollama_tools

    async def chat_completion(
        self,
        messages: list[Message],
        tools: Optional[list[dict[str, Any]]] = None,
        tool_choice: Optional[str] = None,
        stream: bool = False,
    ) -> ChatCompletionResponse:
        """Generate chat completion via Ollama."""
        try:
            ollama_messages = self._build_messages(messages)
            ollama_tools = self._convert_tools(tools)

            payload = {
                "model": self.model,
                "messages": ollama_messages,
                "stream": stream,
                "options": {
                    "temperature": self.temperature,
                    "num_predict": self.max_tokens,
                },
            }

            if ollama_tools:
                payload["tools"] = ollama_tools

            if stream:
                return await self._chat_stream(payload)

            response = await self.client.post("/api/chat", json=payload)
            response.raise_for_status()
            data = response.json()

            message = data.get("message", {})
            content = message.get("content", "")
            tool_calls = message.get("tool_calls")

            return ChatCompletionResponse(
                content=content,
                tool_calls=tool_calls,
                finish_reason=data.get("done_reason", "stop"),
                usage={
                    "prompt_tokens": data.get("prompt_eval_count", 0),
                    "completion_tokens": data.get("eval_count", 0),
                    "total_tokens": data.get("prompt_eval_count", 0) + data.get("eval_count", 0),
                },
                model=data.get("model", self.model),
                provider="ollama",
            )

        except Exception as e:
            logger.error(f"Ollama chat completion failed: {e}")
            raise

    async def _chat_stream(self, payload: dict[str, Any]) -> ChatCompletionResponse:
        """Handle streaming response."""
        # For non-streaming, we return a placeholder
        return ChatCompletionResponse(
            content="",
            finish_reason="stream",
            model=self.model,
            provider="ollama",
        )

    async def chat_completion_stream(
        self,
        messages: list[Message],
        tools: Optional[list[dict[str, Any]]] = None,
    ) -> AsyncGenerator[str, None]:
        """Stream chat completion."""
        ollama_messages = self._build_messages(messages)
        ollama_tools = self._convert_tools(tools)

        payload = {
            "model": self.model,
            "messages": ollama_messages,
            "stream": True,
            "options": {
                "temperature": self.temperature,
                "num_predict": self.max_tokens,
            },
        }

        if ollama_tools:
            payload["tools"] = ollama_tools

        try:
            async with self.client.stream("POST", "/api/chat", json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.strip():
                        data = json.loads(line)
                        if "message" in data and "content" in data["message"]:
                            yield data["message"]["content"]
                        if data.get("done"):
                            break
        except Exception as e:
            logger.error(f"Ollama stream failed: {e}")
            raise

    async def embeddings(self, texts: list[str]) -> EmbeddingResponse:
        """Generate embeddings via Ollama."""
        try:
            embeddings = []
            for text in texts:
                response = await self.client.post("/api/embeddings", json={
                    "model": self.model,
                    "prompt": text,
                })
                response.raise_for_status()
                data = response.json()
                embeddings.append(data.get("embedding", []))

            return EmbeddingResponse(
                embeddings=embeddings,
                model=self.model,
                provider="ollama",
            )
        except Exception as e:
            logger.error(f"Ollama embeddings failed: {e}")
            raise

    async def health_check(self) -> bool:
        """Check Ollama health."""
        try:
            response = await self.client.get("/api/tags")
            return response.status_code == 200
        except Exception:
            return False

    async def close(self) -> None:
        """Close HTTP client."""
        await self.client.aclose()