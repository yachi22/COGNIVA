import logging
import uuid
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.chunk import DocumentChunk
from app.models.document import Document
from app.schemas.retrieval import RetrievalResponse, RetrievalResultItem
from app.services.embeddings import (
    embedding_service,
    EmbeddingError,
    MissingEmbeddingConfigurationError,
    DimensionMismatchError,
)

logger = logging.getLogger("cogniva.retrieval_service")


class RetrievalService:
    """
    Dedicated semantic vector retrieval service.
    Executes PostgreSQL pgvector similarity queries over user-scoped document chunks.
    Maintains strict tenant isolation directly in SQL.
    """

    async def search(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        query: str,
        top_k: int = 5,
        document_id: Optional[uuid.UUID] = None,
        min_similarity: Optional[float] = None,
    ) -> RetrievalResponse:
        """
        Executes semantic similarity search:
        1. Validates document ownership if document_id is specified.
        2. Generates query vector embedding (1536-dim).
        3. Executes pgvector cosine similarity search (<=>) directly in PostgreSQL.
        4. Returns top-K ranked RetrievalResultItem objects with complete provenance.
        """
        # Bound top_k safely
        bounded_top_k = max(1, min(top_k, settings.MAX_RETRIEVAL_TOP_K))

        # If scoped to a specific document, verify existence and tenant ownership
        if document_id is not None:
            doc_stmt = select(Document).where(
                Document.id == document_id,
                Document.user_id == user_id,
            )
            doc_result = await db.execute(doc_stmt)
            target_doc = doc_result.scalar_one_or_none()
            if not target_doc:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Document not found.",
                )
            if target_doc.status != "processed":
                # Unprocessed documents have no searchable embeddings
                return RetrievalResponse(
                    query=query,
                    total=0,
                    results=[],
                )

        # Generate query embedding vector using active provider
        try:
            query_embedding = await embedding_service.embed_query(query)
        except MissingEmbeddingConfigurationError as e:
            logger.error(f"Embedding configuration missing: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(e),
            )
        except (DimensionMismatchError, EmbeddingError) as e:
            logger.error(f"Embedding generation failed for query: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Semantic retrieval failed during query vectorization: {str(e)}",
            )
        except Exception as e:
            logger.error(f"Unexpected error during query embedding: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal error during semantic query processing.",
            )

        # Build pgvector SQL query with strict tenant isolation
        distance_expr = DocumentChunk.embedding.cosine_distance(query_embedding)
        similarity_expr = (1.0 - distance_expr)

        stmt = (
            select(
                DocumentChunk.id.label("chunk_id"),
                DocumentChunk.document_id.label("document_id"),
                DocumentChunk.chunk_index.label("chunk_index"),
                DocumentChunk.content.label("content"),
                DocumentChunk.page_number.label("page_number"),
                DocumentChunk.metadata_.label("metadata"),
                Document.filename.label("document_filename"),
                Document.original_filename.label("document_original_filename"),
                distance_expr.label("cosine_distance"),
                similarity_expr.label("similarity_score"),
            )
            .join(Document, DocumentChunk.document_id == Document.id)
            .where(
                Document.user_id == user_id,
                Document.status == "processed",
                DocumentChunk.embedding.is_not(None),
            )
        )

        if document_id is not None:
            stmt = stmt.where(DocumentChunk.document_id == document_id)

        if min_similarity is not None:
            stmt = stmt.where(similarity_expr >= min_similarity)

        # Order by ascending cosine distance (closest vectors first)
        stmt = stmt.order_by(distance_expr.asc()).limit(bounded_top_k)

        db_result = await db.execute(stmt)
        rows = db_result.all()

        results: List[RetrievalResultItem] = []
        for r in rows:
            results.append(
                RetrievalResultItem(
                    chunk_id=r.chunk_id,
                    document_id=r.document_id,
                    chunk_index=r.chunk_index,
                    content=r.content,
                    similarity_score=round(float(r.similarity_score), 6),
                    cosine_distance=round(float(r.cosine_distance), 6),
                    page_number=r.page_number,
                    metadata=dict(r.metadata or {}),
                    document_filename=r.document_filename,
                    document_original_filename=r.document_original_filename,
                )
            )

        return RetrievalResponse(
            query=query,
            total=len(results),
            results=results,
        )


# Singleton instance
retrieval_service = RetrievalService()
