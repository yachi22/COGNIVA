import logging
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.retrieval import RetrievalRequest, RetrievalResponse
from app.services.retrieval_service import retrieval_service

logger = logging.getLogger("cogniva.api.retrieval")

router = APIRouter(prefix="/retrieval", tags=["retrieval"])


@router.post(
    "/search",
    response_model=RetrievalResponse,
    status_code=status.HTTP_200_OK,
    summary="Semantic vector retrieval across user knowledge chunks",
    description="Vectorizes query text and performs PostgreSQL pgvector cosine similarity search over processed document chunks. Strictly isolated to the authenticated user.",
)
async def search_chunks(
    payload: RetrievalRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RetrievalResponse:
    """
    Search document chunks semantically.
    Enforces user isolation, optional document scoping, and top-K limits.
    """
    return await retrieval_service.search(
        db=db,
        user_id=current_user.id,
        query=payload.query,
        top_k=payload.top_k,
        document_id=payload.document_id,
        min_similarity=payload.min_similarity,
    )
