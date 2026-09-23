"""JARVIS LLM - Anthropic Provider"""

import json
from typing import Any, AsyncGenerator, Optional

from anthropic import AsyncAnthropic

from jarvis.llm.providers import (
    BaseLLMProvider,
    Message,
    ChatCompletionResponse,
    EmbeddingResponse,
)
from jarvis.core.logging import get_logger

logger = get_logger(__name__)


class AnthropicProvider(BaseLLMProvider):
    """Anthropic Claude API provider."""

    def __init__(
        self,
        model: str = "claude-3-5-sonnet-20241022",
        api_key: str = "",
        base_url: str = "",
        temperature: float = 0.2,
        max_tokens: int = 4096,
        **kwargs,
    ):
        super().__init__(model, api_key, base_url, temperature, max_tokens, **kwargs)

        client_kwargs = {"api_key": api_key}
        if base_url:
            client_kwargs["base_url"] = base_url

        self.client = AsyncAnthropic(**client_kwargs)

    def _build_messages(self, messages: list[Message]) -> tuple[str, list[dict[str, Any]]]:
        """Convert messages to Anthropic format (system prompt + messages)."""
        system = ""
        anthropic_messages = []

        for m in messages:
            if m.role == "system":
                system = m.content
            elif m.role == "tool":
                # Tool results are handled differently in Anthropic
                anthropic_messages.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": m.tool_call_id or "",
                            "content": m.content,
                        }
                    ],
                })
            elif m.role == "assistant" and m.tool_calls:
                # Assistant with tool calls
                content = []
                if m.content:
                    content.append({"type": "text", "text": m.content})
                for tc in m.tool_calls:
                    content.append({
                        "type": "tool_use",
                        "id": tc["id"],
                        "name": tc["function"]["name"],
                        "input": json.loads(tc["function"]["arguments"]),
                    })
                anthropic_messages.append({"role": "assistant", "content": content})
            else:
                anthropic_messages.append({"role": m.role, "content": m.content})

        return system, anthropic_messages

    def _convert_tools(self, tools: Optional[list[dict[str, Any]]]) -> Optional[list[dict[str, Any]]]:
        """Convert OpenAI tool format to Anthropic format."""
        if not tools:
            return None

        anthropic_tools = []
        for tool in tools:
            if tool.get("type") == "function":
                fn = tool["function"]
                anthropic_tools.append({
                    "name": fn["name"],
                    "description": fn["description"],
                    "input_schema": fn["parameters"],
                })
        return anthropic_tools

    async def chat_completion(
        self,
        messages: list[Message],
        tools: Optional[list[dict[str, Any]]] = None,
        tool_choice: Optional[str] = None,
        stream: bool = False,
    ) -> ChatCompletionResponse:
        """Generate chat completion via Anthropic."""
        try:
            system, anthropic_messages = self._build_messages(messages)
            anthropic_tools = self._convert_tools(tools)

            kwargs = {
                "model": self.model,
                "messages": anthropic_messages,
                "max_tokens": self.max_tokens,
                "temperature": self.temperature,
            }

            if system:
                kwargs["system"] = system

            if anthropic_tools:
                kwargs["tools"] = anthropic_tools
                if tool_choice and tool_choice != "auto":
                    kwargs["tool_choice"] = {"type": "tool", "name": tool_choice}
                else:
                    kwargs["tool_choice"] = {"type": "auto"}

            if stream:
                kwargs["stream"] = True

            response = await self.client.messages.create(**kwargs)

            if stream:
                return ChatCompletionResponse(
                    content="",
                    finish_reason="stream",
                    model=self.model,
                    provider="anthropic",
                )

            content = ""
            tool_calls = []

            for block in response.content:
                if block.type == "text":
                    content += block.text
                elif block.type == "tool_use":
                    tool_calls.append({
                        "id": block.id,
                        "type": "function",
                        "function": {
                            "name": block.name,
                            "arguments": json.dumps(block.input),
                        },
                    })

            return ChatCompletionResponse(
                content=content,
                tool_calls=tool_calls if tool_calls else None,
                finish_reason=response.stop_reason,
                usage={
                    "prompt_tokens": response.usage.input_tokens,
                    "completion_tokens": response.usage.output_tokens,
                    "total_tokens": response.usage.input_tokens + response.usage.output_tokens,
                } if response.usage else None,
                model=response.model,
                provider="anthropic",
            )

        except Exception as e:
            logger.error(f"Anthropic chat completion failed: {e}")
            raise

    async def chat_completion_stream(
        self,
        messages: list[Message],
        tools: Optional[list[dict[str, Any]]] = None,
    ) -> AsyncGenerator[str, None]:
        """Stream chat completion."""
        system, anthropic_messages = self._build_messages(messages)
        anthropic_tools = self._convert_tools(tools)

        kwargs = {
            "model": self.model,
            "messages": anthropic_messages,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "stream": True,
        }

        if system:
            kwargs["system"] = system

        if anthropic_tools:
            kwargs["tools"] = anthropic_tools
            kwargs["tool_choice"] = {"type": "auto"}

        try:
            stream = await self.client.messages.create(**kwargs)
            async for chunk in stream:
                if chunk.type == "content_block_delta" and chunk.delta.type == "text_delta":
                    yield chunk.delta.text
        except Exception as e:
            logger.error(f"Anthropic stream failed: {e}")
            raise

    async def embeddings(self, texts: list[str]) -> EmbeddingResponse:
        """Generate embeddings (not directly supported by Anthropic)."""
        # Anthropic doesn't have embeddings API, return empty
        logger.warning("Anthropic doesn't support embeddings, returning empty")
        return EmbeddingResponse(
            embeddings=[[] for _ in texts],
            model="none",
            provider="anthropic",
        )

    async def health_check(self) -> bool:
        """Check Anthropic API health."""
        try:
            # Simple completion to test
            await self.client.messages.create(
                model=self.model,
                max_tokens=10,
                messages=[{"role": "user", "content": "Hi"}],
            )
            return True
        except Exception:
            return False