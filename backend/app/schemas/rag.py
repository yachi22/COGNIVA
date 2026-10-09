import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class RAGQueryRequest(BaseModel):
    """
    Input request for Retrieval-Augmented Generation (RAG) question answering.
    Supports user-wide and document-scoped queries with bounded top_k.
    """
    query: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="User question to be answered using retrieved document evidence.",
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of relevant document chunks to retrieve as context (1 to 20).",
    )
    document_id: Optional[uuid.UUID] = Field(
        default=None,
        description="Optional document ID to scope retrieval to a specific document.",
    )
    min_similarity: Optional[float] = Field(
        default=None,
        ge=-1.0,
        le=1.0,
        description="Optional minimum cosine similarity score threshold for evidence filtering.",
    )
    conversation_id: Optional[uuid.UUID] = Field(
        default=None,
        description="Optional conversation ID to continue an existing chat session.",
    )


from app.schemas.citation import CitationItem


class RAGSourceItem(BaseModel):
    """
    Structured provenance metadata for an evidence chunk utilized during RAG.
    Excludes raw embedding vectors. Includes response-scoped citation_id (e.g. S1).
    """
    citation_id: str = Field(
        ...,
        description="Response-scoped source identifier (e.g. 'S1', 'S2') corresponding to retrieved rank order.",
    )
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    chunk_index: int
    document_filename: str
    page_number: Optional[int] = Field(
        None,
        description="1-indexed source page for PDFs; None for DOCXs.",
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
        description="Unit type, sequence, and headings from extraction.",
    )

    model_config = ConfigDict(from_attributes=True)


class RAGQueryResponse(BaseModel):
    """
    Output response of the RAG pipeline containing the grounded answer,
    retrieved evidence sources, validated citations, and conversation linkage.
    """
    query: str
    answer: str
    retrieval_count: int
    sources: List[RAGSourceItem]
    citations: List[CitationItem] = Field(
        default_factory=list,
        description="Validated backend citations referenced by the answer.",
    )
    insufficient_evidence: bool = Field(
        default=False,
        description="True if retrieval yielded no evidence and model declined to speculate.",
    )
    conversation_id: Optional[uuid.UUID] = Field(
        default=None,
        description="Conversation ID associated with this query and answer turn.",
    )
    user_message_id: Optional[uuid.UUID] = Field(
        default=None,
        description="UUID of the persisted user question message.",
    )
    assistant_message_id: Optional[uuid.UUID] = Field(
        default=None,
        description="UUID of the persisted assistant response message.",
    )

