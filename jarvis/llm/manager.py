"""JARVIS LLM - Factory and Manager"""

from typing import Any, Optional

from jarvis.llm.providers import BaseLLMProvider
from jarvis.llm.openai_provider import OpenAIProvider, AzureOpenAIProvider
from jarvis.llm.anthropic_provider import AnthropicProvider
from jarvis.llm.ollama_provider import OllamaProvider
from jarvis.core.config import get_settings
from jarvis.core.logging import get_logger
from jarvis.core.exceptions import ConfigurationError

logger = get_logger(__name__)


class LLMManager:
    """Manages LLM provider instances."""

    def __init__(self):
        self._provider: Optional[BaseLLMProvider] = None
        self._settings = get_settings()

    def get_provider(self) -> BaseLLMProvider:
        """Get or create the configured LLM provider."""
        if self._provider is None:
            self._provider = self._create_provider()
        return self._provider

    def _create_provider(self) -> BaseLLMProvider:
        """Create provider based on configuration."""
        llm_config = self._settings.llm
        provider_name = llm_config.provider.lower()

        logger.info(f"Creating LLM provider: {provider_name} ({llm_config.model})")

        if provider_name == "openai":
            if not llm_config.api_key:
                raise ConfigurationError("OpenAI API key not configured")
            return OpenAIProvider(
                model=llm_config.model,
                api_key=llm_config.api_key,
                base_url=llm_config.base_url,
                temperature=llm_config.temperature,
                max_tokens=llm_config.max_tokens,
            )

        elif provider_name == "azure":
            if not llm_config.api_key or not llm_config.base_url:
                raise ConfigurationError("Azure OpenAI requires API key and base URL")
            return AzureOpenAIProvider(
                model=llm_config.model,
                api_key=llm_config.api_key,
                base_url=llm_config.base_url,
                temperature=llm_config.temperature,
                max_tokens=llm_config.max_tokens,
            )

        elif provider_name == "anthropic":
            if not llm_config.api_key:
                raise ConfigurationError("Anthropic API key not configured")
            return AnthropicProvider(
                model=llm_config.model,
                api_key=llm_config.api_key,
                base_url=llm_config.base_url,
                temperature=llm_config.temperature,
                max_tokens=llm_config.max_tokens,
            )

        elif provider_name == "ollama":
            return OllamaProvider(
                model=llm_config.model,
                base_url=llm_config.base_url or "http://localhost:11434",
                temperature=llm_config.temperature,
                max_tokens=llm_config.max_tokens,
            )

        else:
            raise ConfigurationError(f"Unknown LLM provider: {provider_name}")

    async def health_check(self) -> bool:
        """Check provider health."""
        try:
            provider = self.get_provider()
            return await provider.health_check()
        except Exception as e:
            logger.error(f"LLM health check failed: {e}")
            return False

    def reload(self) -> None:
        """Reload provider (e.g., after config change)."""
        self._provider = None
        self._settings = get_settings()


# Global manager instance
_manager: Optional[LLMManager] = None


def get_llm_manager() -> LLMManager:
    """Get global LLM manager."""
    global _manager
    if _manager is None:
        _manager = LLMManager()
    return _manager


def get_llm() -> BaseLLMProvider:
    """Get configured LLM provider."""
    return get_llm_manager().get_provider()