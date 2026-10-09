import logging
from typing import List, Optional
import httpx

from app.core.config import settings
from app.services.embeddings.base import (
    BaseEmbeddingProvider,
    EmbeddingError,
    MissingEmbeddingConfigurationError,
    DimensionMismatchError,
)

logger = logging.getLogger("cogniva.embeddings")


class OpenAIEmbeddingProvider(BaseEmbeddingProvider):
    """
    Production embedding provider calling the OpenAI Embeddings REST API.
    Uses async httpx with connection pooling and chunk batching.
    Produces vectors compatible with PostgreSQL Vector(1536).
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        batch_size: Optional[int] = None,
    ):
        self._api_key = api_key or settings.OPENAI_API_KEY
        self._model = model or settings.EMBEDDING_MODEL
        self._base_url = (base_url or settings.OPENAI_BASE_URL or "https://api.openai.com/v1").rstrip("/")
        self._batch_size = batch_size or settings.EMBEDDING_BATCH_SIZE

    @property
    def dimension(self) -> int:
        return settings.EMBEDDING_DIMENSION  # Strictly 1536

    @property
    def model_name(self) -> str:
        return self._model

    async def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []

        # Enforce explicit API key configuration
        if not self._api_key:
            raise MissingEmbeddingConfigurationError(
                "OpenAI API key is missing. Configure OPENAI_API_KEY environment variable to generate embeddings."
            )

        all_embeddings: List[List[float]] = []
        url = f"{self._base_url}/embeddings"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        # Process in batches to respect API payload limits
        async with httpx.AsyncClient(timeout=45.0) as client:
            for i in range(0, len(texts), self._batch_size):
                batch = texts[i : i + self._batch_size]
                payload = {
                    "input": batch,
                    "model": self._model,
                }
                # For models supporting dimensions parameter (e.g. text-embedding-3-small)
                if "text-embedding-3" in self._model:
                    payload["dimensions"] = self.dimension

                try:
                    resp = await client.post(url, json=payload, headers=headers)
                except Exception as e:
                    logger.error(f"Network error contacting OpenAI embeddings endpoint: {str(e)}")
                    raise EmbeddingError(f"Network connection failed during embedding generation: {str(e)}")

                if resp.status_code != 200:
                    err_msg = f"OpenAI Embeddings API returned status {resp.status_code}: {resp.text}"
                    logger.error(err_msg)
                    raise EmbeddingError(f"Embedding provider rejected request (status {resp.status_code}).")

                data = resp.json().get("data", [])
                # Ensure ordered results matching batch input order
                data.sort(key=lambda item: item["index"])

                for item in data:
                    vec = item["embedding"]
                    if len(vec) != self.dimension:
                        raise DimensionMismatchError(
                            f"Model produced vector with {len(vec)} dimensions, expected {self.dimension}."
                        )
                    all_embeddings.append(vec)

        return all_embeddings
