import uuid
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict, Field


class CitationItem(BaseModel):
    """
    Backend-owned, response-scoped citation reference pointing to an authentic
    retrieved document chunk belonging to the authenticated user.
    The citation ID is a short response-scoped identifier (e.g. 'S1', 'S2')
    derived strictly from the retrieval rank order.
    """
    citation_id: str = Field(
        ...,
        description="Response-scoped source identifier (e.g. 'S1', 'S2') corresponding to retrieved rank order.",
    )
    document_id: uuid.UUID = Field(
        ...,
        description="UUID of the authentic source document.",
    )
    document_filename: str = Field(
        ...,
        description="Original or stored filename of the source document.",
    )
    chunk_id: uuid.UUID = Field(
        ...,
        description="UUID of the retrieved document chunk.",
    )
    chunk_index: int = Field(
        ...,
        description="0-indexed position of the chunk within the document.",
    )
    page_number: Optional[int] = Field(
        None,
        description="1-indexed source page for PDFs; None for DOCX documents.",
    )
    similarity_score: float = Field(
        ...,
        description="Cosine similarity score (higher indicates greater relevance).",
    )
    cosine_distance: float = Field(
        ...,
        description="pgvector cosine distance.",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Structural and provenance metadata preserved from extraction/chunking.",
    )

    model_config = ConfigDict(from_attributes=True)
