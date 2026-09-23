"""JARVIS LLM - OpenAI Provider"""

import json
from typing import Any, AsyncGenerator, Optional

from openai import AsyncOpenAI

from jarvis.llm.providers import (
    BaseLLMProvider,
    Message,
    ChatCompletionResponse,
    EmbeddingResponse,
)
from jarvis.core.logging import get_logger

logger = get_logger(__name__)


class OpenAIProvider(BaseLLMProvider):
    """OpenAI API provider."""

    def __init__(
        self,
        model: str = "gpt-4o",
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

        self.client = AsyncOpenAI(**client_kwargs)

    async def chat_completion(
        self,
        messages: list[Message],
        tools: Optional[list[dict[str, Any]]] = None,
        tool_choice: Optional[str] = None,
        stream: bool = False,
    ) -> ChatCompletionResponse:
        """Generate chat completion via OpenAI."""
        try:
            openai_messages = self._build_messages(messages)

            kwargs = {
                "model": self.model,
                "messages": openai_messages,
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
            }

            if tools:
                kwargs["tools"] = tools
                kwargs["tool_choice"] = tool_choice or "auto"

            if stream:
                kwargs["stream"] = True

            response = await self.client.chat.completions.create(**kwargs)

            if stream:
                return ChatCompletionResponse(
                    content="",
                    finish_reason="stream",
                    model=self.model,
                    provider="openai",
                )

            choice = response.choices[0]
            tool_calls = None
            if choice.message.tool_calls:
                tool_calls = [
                    {
                        "id": tc.id,
                        "type": tc.type,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in choice.message.tool_calls
                ]

            return ChatCompletionResponse(
                content=choice.message.content or "",
                tool_calls=tool_calls,
                finish_reason=choice.finish_reason,
                usage={
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                } if response.usage else None,
                model=response.model,
                provider="openai",
            )

        except Exception as e:
            logger.error(f"OpenAI chat completion failed: {e}")
            raise

    async def chat_completion_stream(
        self,
        messages: list[Message],
        tools: Optional[list[dict[str, Any]]] = None,
    ) -> AsyncGenerator[str, None]:
        """Stream chat completion."""
        openai_messages = self._build_messages(messages)

        kwargs = {
            "model": self.model,
            "messages": openai_messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "stream": True,
        }

        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        try:
            stream = await self.client.chat.completions.create(**kwargs)
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            logger.error(f"OpenAI stream failed: {e}")
            raise

    async def embeddings(self, texts: list[str]) -> EmbeddingResponse:
        """Generate embeddings."""
        try:
            response = await self.client.embeddings.create(
                model="text-embedding-3-small",
                input=texts,
            )

            return EmbeddingResponse(
                embeddings=[d.embedding for d in response.data],
                usage={
                    "prompt_tokens": response.usage.prompt_tokens,
                    "total_tokens": response.usage.total_tokens,
                } if response.usage else None,
                model="text-embedding-3-small",
                provider="openai",
            )
        except Exception as e:
            logger.error(f"OpenAI embeddings failed: {e}")
            raise

    async def health_check(self) -> bool:
        """Check OpenAI API health."""
        try:
            await self.client.models.list()
            return True
        except Exception:
            return False


class AzureOpenAIProvider(OpenAIProvider):
    """Azure OpenAI provider."""

    def __init__(
        self,
        model: str,
        api_key: str = "",
        base_url: str = "",
        api_version: str = "2024-02-15-preview",
        temperature: float = 0.2,
        max_tokens: int = 4096,
        **kwargs,
    ):
        # Azure uses deployment name as model
        super().__init__(model, api_key, base_url, temperature, max_tokens, **kwargs)

        self.client = AsyncOpenAI(
            api_key=api_key,
            azure_endpoint=base_url,
            api_version=api_version,
        )