import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class RetrievalRequest(BaseModel):
    """
    Input payload for semantic vector search.
    Supports user-wide search or scoped document search.
    """
    query: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Semantic search query string.",
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of top matching chunks to retrieve (1 to 20).",
    )
    document_id: Optional[uuid.UUID] = Field(
        default=None,
        description="Optional document ID to restrict search within a single document.",
    )
    min_similarity: Optional[float] = Field(
        default=None,
        ge=-1.0,
        le=1.0,
        description="Optional minimum cosine similarity threshold (-1.0 to 1.0, higher is more similar).",
    )


class RetrievalResultItem(BaseModel):
    """
    Individual retrieved document chunk ranked by semantic similarity.
    Preserves full source provenance without exposing raw vector embeddings.
    """
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    chunk_index: int
    content: str
    similarity_score: float = Field(
        ...,
        description="Cosine similarity score (1.0 - cosine_distance). Higher indicates greater semantic relevance.",
    )
    cosine_distance: float = Field(
        ...,
        description="Raw pgvector cosine distance (<=> operator, range [0, 2]). Lower indicates closer proximity.",
    )
    page_number: Optional[int] = Field(
        None,
        description="1-indexed source page for PDFs; None for DOCX documents.",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Structural and provenance metadata preserved from extraction/chunking.",
    )
    document_filename: str
    document_original_filename: str

    model_config = ConfigDict(from_attributes=True)


class RetrievalResponse(BaseModel):
    """
    Complete semantic search response containing ranked evidence chunks.
    """
    query: str
    total: int
    results: List[RetrievalResultItem]
