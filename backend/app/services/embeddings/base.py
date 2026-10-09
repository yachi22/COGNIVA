from abc import ABC, abstractmethod
from typing import List


class EmbeddingError(Exception):
    """Base exception for all embedding operations."""
    pass


class MissingEmbeddingConfigurationError(EmbeddingError):
    """Raised when an embedding provider lacks required API credentials or configuration."""
    pass


class DimensionMismatchError(EmbeddingError):
    """Raised when the embedding provider returns an unexpected vector dimension."""
    pass


class BaseEmbeddingProvider(ABC):
    """
    Abstract contract for vector embedding providers in Cogniva.
    Keeps embedding generation modular and decoupled from any specific model or cloud vendor.
    """

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Returns the embedding vector dimensionality (must be 1536 for pgvector schema)."""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Returns the identifier name of the active model."""
        pass

    @abstractmethod
    async def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Generates dense vector embeddings for the provided list of text chunks.
        Must return vectors of length equal to self.dimension (1536).
        """
        pass
