import hashlib
import math
import re
from typing import List

from app.services.embeddings.base import BaseEmbeddingProvider


class MockEmbeddingProvider(BaseEmbeddingProvider):
    """
    Deterministic mock embedding provider for tests and offline validation.
    Implements feature-hashing random projection so that semantic word overlap
    yields realistic vector similarity in pgvector, while strictly maintaining
    1536 dimensions and unit vector normalization.
    """

    def __init__(self, dimension: int = 1536):
        self._dimension = dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def model_name(self) -> str:
        return "mock-text-embedding-3-small"

    @property
    def provider_name(self) -> str:
        return "mock"

    async def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []

        embeddings: List[List[float]] = []
        for text in texts:
            words = re.findall(r"\w+", text.lower())
            vec: List[float] = [0.0] * self._dimension

            if words:
                for w in words:
                    base_h = int(hashlib.sha256(w.encode("utf-8")).hexdigest(), 16)
                    for j in range(16):
                        idx = (base_h >> (j * 8)) % self._dimension
                        sign = 1.0 if ((base_h >> (j * 8 + 4)) & 1) else -1.0
                        vec[idx] += sign
            else:
                base_h = int(hashlib.sha256(text.encode("utf-8")).hexdigest(), 16)
                for j in range(16):
                    idx = (base_h >> (j * 8)) % self._dimension
                    sign = 1.0 if ((base_h >> (j * 8 + 4)) & 1) else -1.0
                    vec[idx] += sign

            norm = math.sqrt(sum(v * v for v in vec)) or 1.0
            normalized = [round(v / norm, 6) for v in vec]
            embeddings.append(normalized)

        return embeddings
