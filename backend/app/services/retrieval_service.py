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


RETRIEVAL_STOP_WORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are",
    "as", "at", "be", "because", "been", "before", "being", "below", "between", "both",
    "but", "by", "can", "could", "did", "do", "does", "doing", "down", "during", "each", "few",
    "for", "from", "further", "had", "has", "have", "having", "he", "her", "here", "hers",
    "him", "his", "how", "i", "if", "in", "into", "is", "it", "it's", "its", "itself",
    "me", "more", "most", "my", "myself", "no", "nor", "not", "of", "off", "on", "once", "only",
    "or", "other", "our", "ours", "out", "over", "own", "same", "she", "should", "so", "some",
    "such", "than", "that", "the", "their", "theirs", "them", "then", "there", "these", "they",
    "this", "those", "through", "to", "too", "under", "until", "up", "very", "was", "we", "were",
    "what", "when", "where", "which", "while", "who", "whom", "why", "with", "would", "you", "your",
}

RETRIEVAL_FRAMING_WORDS = {
    "list", "every", "each", "all", "explicitly", "mentioned", "mention", "document", "documents",
    "add", "anything", "nothing", "stated", "state", "according", "based", "tell", "describe",
    "explain", "provide", "give", "show", "question", "answer", "find", "identify", "detail",
}


def _stem_retrieval_token(w: str) -> str:
    w = w.lower().strip()
    for suffix in (
        "ations", "ation", "ating", "ated", "ates", "ments", "ment", "ities", "ity",
        "ences", "ence", "ances", "ance", "ously", "able", "ible", "ness", "less",
        "ings", "ing", "ies", "ied", "ed", "es", "s"
    ):
        if len(w) > len(suffix) + 2 and w.endswith(suffix):
            w = w[:-len(suffix)]
            break
    return w


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
        hybrid: bool = False,
    ) -> RetrievalResponse:
        """
        Executes semantic similarity search (with optional hybrid keyword re-ranking):
        1. Validates document ownership if document_id is specified.
        2. Generates query vector embedding (1536-dim).
        3. Executes pgvector cosine similarity search (<=>) directly in PostgreSQL.
        4. When hybrid=True, applies reciprocal keyword overlap weighting.
        5. Returns top-K ranked RetrievalResultItem objects with complete provenance.
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

        # Derive topical query tokens and stems for hybrid candidate gathering and scoring
        import re
        clean_tokens = [w.lower() for w in re.findall(r"\b[a-zA-Z0-9_\-]+\b", query) if len(w) > 2]
        topical_tokens = [w for w in clean_tokens if w not in RETRIEVAL_STOP_WORDS and w not in RETRIEVAL_FRAMING_WORDS]
        topical_stems = {_stem_retrieval_token(w) for w in topical_tokens}

        # Check for semantic evaluation intent
        eval_intent = any(s in topical_stems for s in ("evalu", "metric", "measur", "method", "assess"))
        eval_synonyms = {"evalu", "metric", "measur", "method", "assess", "test", "precis", "recal", "rate"}

        # Candidate pool limit: for document-scoped queries, ensure full document coverage (up to 200 chunks)
        if document_id is not None:
            candidate_k = max(bounded_top_k * 20, 200)
        else:
            candidate_k = max(bounded_top_k * 8, 50) if hybrid else bounded_top_k

        # 1. Fetch dense vector candidates
        vector_stmt = stmt.order_by(distance_expr.asc()).limit(candidate_k)
        vector_res = await db.execute(vector_stmt)
        candidates_by_id = {r.chunk_id: r for r in vector_res.all()}

        # 2. In hybrid mode, also retrieve keyword-matched candidates from SQL
        if hybrid and topical_tokens:
            from sqlalchemy import or_
            kw_conditions = [DocumentChunk.content.ilike(f"%{tok}%") for tok in topical_tokens[:5]]
            kw_stmt = stmt.where(or_(*kw_conditions)).limit(candidate_k)
            kw_res = await db.execute(kw_stmt)
            for r in kw_res.all():
                if r.chunk_id not in candidates_by_id:
                    candidates_by_id[r.chunk_id] = r

        rows = list(candidates_by_id.values())

        results: List[RetrievalResultItem] = []

        for r in rows:
            sim = float(r.similarity_score)
            if hybrid and topical_stems:
                content_words = [w.lower() for w in re.findall(r"\b[a-zA-Z0-9_\-]+\b", r.content) if len(w) > 1]
                content_stems = {_stem_retrieval_token(w) for w in content_words}

                matched_topical = topical_stems & content_stems
                keyword_score = len(matched_topical) / max(len(topical_stems), 1)

                if eval_intent:
                    matched_eval = eval_synonyms & content_stems
                    keyword_score += len(matched_eval) * 0.15

                final_score = (0.60 * sim) + (0.40 * min(keyword_score, 1.0))
            else:
                final_score = sim

            results.append(
                RetrievalResultItem(
                    chunk_id=r.chunk_id,
                    document_id=r.document_id,
                    chunk_index=r.chunk_index,
                    content=r.content,
                    similarity_score=round(final_score, 6),
                    cosine_distance=round(float(r.cosine_distance), 6),
                    page_number=r.page_number,
                    metadata=dict(r.metadata or {}),
                    document_filename=r.document_filename,
                    document_original_filename=r.document_original_filename,
                )
            )

        if hybrid:
            results.sort(key=lambda x: x.similarity_score, reverse=True)
            results = results[:bounded_top_k]

        return RetrievalResponse(
            query=query,
            total=len(results),
            results=results,
        )


# Singleton instance
retrieval_service = RetrievalService()
