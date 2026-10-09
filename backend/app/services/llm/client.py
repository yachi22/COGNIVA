import logging
import re
from typing import Callable, List, Optional
import httpx

from app.core.config import settings
from app.services.llm.base import (
    BaseLLMProvider,
    LLMError,
    LLMMessage,
    LLMResponse,
    MissingLLMConfigurationError,
)
from app.services.llm.prompt import INSUFFICIENT_EVIDENCE_RESPONSE

logger = logging.getLogger("cogniva.llm")


class OpenAILLMProvider(BaseLLMProvider):
    """
    Production LLM provider using OpenAI's Chat Completions API via asynchronous httpx.
    Configurable via environment variables (model, api_key, base_url).
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = 60.0,
    ):
        self._api_key = api_key if api_key is not None else settings.OPENAI_API_KEY
        self._model = model or settings.LLM_MODEL
        self._base_url = (base_url or settings.OPENAI_BASE_URL or "https://api.openai.com/v1").rstrip("/")
        self._timeout = timeout

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def provider_name(self) -> str:
        return "openai"

    async def generate(
        self,
        messages: List[LLMMessage],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> LLMResponse:
        """
        Calls OpenAI chat completion endpoint.
        Fails fast if OPENAI_API_KEY is not configured.
        """
        if not self._api_key or not self._api_key.strip():
            raise MissingLLMConfigurationError(
                "OPENAI_API_KEY is not configured. Set the OPENAI_API_KEY environment variable to enable LLM generation."
            )

        endpoint = f"{self._base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._api_key.strip()}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self._model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature if temperature is not None else settings.LLM_TEMPERATURE,
            "max_tokens": max_tokens if max_tokens is not None else settings.LLM_MAX_TOKENS,
        }

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(endpoint, headers=headers, json=payload)

            if response.status_code != 200:
                logger.error(f"OpenAI API call failed with HTTP {response.status_code}: {response.text}")
                raise LLMError(f"OpenAI API error ({response.status_code}): {response.text}")

            data = response.json()
            choices = data.get("choices", [])
            if not choices:
                raise LLMError("OpenAI API returned empty choices list.")

            content = choices[0].get("message", {}).get("content", "")
            usage = data.get("usage", {})

            return LLMResponse(
                content=content.strip(),
                model=data.get("model", self._model),
                usage=usage,
            )

        except httpx.RequestError as e:
            logger.error(f"Network error communicating with OpenAI API: {str(e)}", exc_info=True)
            raise LLMError(f"Network communication failure with OpenAI LLM service: {str(e)}")


class MockLLMProvider(BaseLLMProvider):
    """
    Deterministic mock LLM provider for tests and offline validation.
    Synthesizes answers grounded strictly on retrieved context, or asserts
    insufficient evidence if relevant keywords are absent.
    Preserves inspection attributes for test assertions.
    """

    def __init__(
        self,
        model: str = "mock-gpt-4o-mini",
        custom_handler: Optional[Callable[[List[LLMMessage]], str]] = None,
        custom_response: Optional[str] = None,
    ):
        self._model = model
        self.custom_handler = custom_handler
        self.custom_response = custom_response
        self.last_messages: List[LLMMessage] = []
        self.call_count: int = 0

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def provider_name(self) -> str:
        return "mock"

    async def generate(
        self,
        messages: List[LLMMessage],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> LLMResponse:
        self.call_count += 1
        self.last_messages = list(messages)

        if self.custom_response is not None:
            return LLMResponse(content=self.custom_response, model=self._model)

        if self.custom_handler is not None:
            ans = self.custom_handler(messages)
            return LLMResponse(content=ans, model=self._model)

        # Default deterministic mock logic
        user_msg = next((m.content for m in messages if m.role == "user"), "")

        # Extract user query and context block
        query_match = re.search(r"USER QUESTION:\s*\n(.*?)\n\nRETRIEVED SOURCE CONTEXT", user_msg, re.DOTALL)
        query = query_match.group(1).strip() if query_match else ""

        context_match = re.search(r"RETRIEVED SOURCE CONTEXT[^\n]*\n(.*?)\n\nTASK:", user_msg, re.DOTALL)
        context = context_match.group(1).strip() if context_match else ""

        # Check for empty context or insufficient evidence
        if not context or "NO_RELEVANT_SOURCES_FOUND" in context:
            return LLMResponse(content=INSUFFICIENT_EVIDENCE_RESPONSE, model=self._model)

        # Check for query keywords in context
        query_words = set(re.findall(r"\w+", query.lower()))
        # Remove common stop words
        stop_words = {"what", "is", "the", "a", "an", "how", "does", "in", "to", "for", "and", "or", "of", "are"}
        meaningful_words = query_words - stop_words

        context_lower = context.lower()
        has_overlap = any(w in context_lower for w in meaningful_words) if meaningful_words else True

        if not has_overlap:
            return LLMResponse(content=INSUFFICIENT_EVIDENCE_RESPONSE, model=self._model)

        # If evidence exists and overlaps, synthesize a clean grounded summary
        # Extract content lines from source blocks, ignoring structural headers
        content_lines = []
        for line in context.splitlines():
            line_s = line.strip()
            if (
                line_s
                and not line_s.startswith("---")
                and not line_s.startswith("[S")
                and not line_s.startswith("Document:")
                and not line_s.startswith("Page:")
                and not line_s.startswith("Chunk:")
                and not line_s.startswith("Similarity:")
                and not line_s.startswith("Content:")
                and not line_s.startswith("Score:")
            ):
                content_lines.append(line_s)

        snippet = " ".join(content_lines[:3]) if content_lines else "the provided documentation"
        has_s1 = "[S1]" in user_msg
        citation_tag = " [S1]" if has_s1 else ""
        answer = f"Based on the provided documents, {snippet}{citation_tag}"
        return LLMResponse(content=answer, model=self._model)
