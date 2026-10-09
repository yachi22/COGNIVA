import logging
from typing import List, Optional

from app.core.config import settings
from app.services.llm.base import (
    BaseLLMProvider,
    LLMError,
    LLMMessage,
    LLMResponse,
)
from app.services.llm.client import OpenAILLMProvider, MockLLMProvider

logger = logging.getLogger("cogniva.llm.service")


class LLMService:
    """
    Centralized LLM service coordinating chat completion execution,
    provider resolution, and provider injection for automated testing.
    """

    def __init__(self, provider: Optional[BaseLLMProvider] = None):
        self._provider = provider or self._resolve_default_provider()

    def _resolve_default_provider(self) -> BaseLLMProvider:
        provider_name = settings.LLM_PROVIDER.lower().strip()
        if provider_name == "openai":
            return OpenAILLMProvider()
        elif provider_name in ("mock", "test"):
            return MockLLMProvider()
        else:
            raise LLMError(f"Unsupported LLM provider '{settings.LLM_PROVIDER}'.")

    @property
    def provider(self) -> BaseLLMProvider:
        return self._provider

    def set_provider(self, provider: BaseLLMProvider) -> None:
        """Allows injecting custom or mock LLM providers for testing."""
        self._provider = provider

    def reset_default_provider(self) -> None:
        """Resets active provider back to environment default configuration."""
        self._provider = self._resolve_default_provider()

    async def generate(
        self,
        messages: List[LLMMessage],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> LLMResponse:
        """
        Executes completion generation with active LLM provider.
        """
        return await self._provider.generate(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )


# Singleton instance
llm_service = LLMService()
