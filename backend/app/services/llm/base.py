from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class LLMError(Exception):
    """Base exception for all LLM provider operations."""
    pass


class MissingLLMConfigurationError(LLMError):
    """Raised when an LLM provider lacks required API credentials or configuration."""
    pass


class LLMMessage(BaseModel):
    """Standardized chat message payload."""
    role: str = Field(..., description="Role: 'system', 'user', or 'assistant'")
    content: str = Field(..., description="Text content of the message")


class LLMResponse(BaseModel):
    """Structured response from an LLM provider."""
    content: str
    model: str
    usage: Dict[str, Any] = Field(default_factory=dict)


class BaseLLMProvider(ABC):
    """
    Abstract contract for Large Language Model providers in Cogniva.
    Keeps answer generation decoupled from vendor-specific SDKs.
    """

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Returns the active model identifier."""
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Returns the provider name (e.g., 'openai', 'mock')."""
        pass

    @abstractmethod
    async def generate(
        self,
        messages: List[LLMMessage],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> LLMResponse:
        """
        Executes chat completion generation for the given message list.
        """
        pass
