from typing import List, Optional
from app.core.config import settings
from app.services.embeddings.base import (
    BaseEmbeddingProvider,
    EmbeddingError,
    DimensionMismatchError,
)
from app.services.embeddings.provider import OpenAIEmbeddingProvider
from app.services.embeddings.mock import MockEmbeddingProvider


class EmbeddingService:
    """
    Centralized embedding service coordinating provider execution,
    vector dimensionality validation (1536), and provider injection.
    """

    def __init__(self, provider: Optional[BaseEmbeddingProvider] = None):
        self._provider = provider or self._resolve_default_provider()

    def _resolve_default_provider(self) -> BaseEmbeddingProvider:
        provider_name = settings.EMBEDDING_PROVIDER.lower().strip().strip("\"'")
        if provider_name == "openai":
            return OpenAIEmbeddingProvider()
        elif provider_name in ("mock", "test"):
            return MockEmbeddingProvider()
        else:
            raise EmbeddingError(f"Unsupported embedding provider '{settings.EMBEDDING_PROVIDER}'.")

    @property
    def provider(self) -> BaseEmbeddingProvider:
        return self._provider

    def set_provider(self, provider: BaseEmbeddingProvider) -> None:
        """
        Allows swapping the embedding provider (e.g. for automated test suites or local models).
        """
        self._provider = provider

    def reset_default_provider(self) -> None:
        """
        Resets active provider back to default configuration.
        """
        self._provider = self._resolve_default_provider()

    async def embed_chunks(self, texts: List[str]) -> List[List[float]]:
        """
        Generates dense embeddings for a list of text strings.
        Validates output dimensionality strictly matches 1536.
        """
        if not texts:
            return []

        embeddings = await self._provider.get_embeddings(texts)

        if len(embeddings) != len(texts):
            raise EmbeddingError(
                f"Embedding count mismatch: expected {len(texts)} vectors, got {len(embeddings)}."
            )

        expected_dim = self._provider.dimension
        for idx, vec in enumerate(embeddings):
            if len(vec) != expected_dim:
                raise DimensionMismatchError(
                    f"Vector at index {idx} has dimension {len(vec)}, required {expected_dim}."
                )

        return embeddings

    async def embed_query(self, query: str) -> List[float]:
        """
        Generates dense embedding for a single user query.
        Validates output dimensionality strictly matches 1536.
        """
        clean_query = query.strip()
        if not clean_query:
            raise EmbeddingError("Query text cannot be empty.")

        vectors = await self.embed_chunks([clean_query])
        if not vectors:
            raise EmbeddingError("No embedding vector was generated for the query.")

        return vectors[0]


# Singleton service instance
embedding_service = EmbeddingService()
