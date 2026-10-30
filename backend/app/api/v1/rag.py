import logging
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.rate_limiter import rate_limit_llm
from app.models.user import User
from app.schemas.rag import RAGQueryRequest, RAGQueryResponse
from app.services.rag.service import rag_service

logger = logging.getLogger("cogniva.api.rag")

router = APIRouter(prefix="/rag", tags=["rag"])


@router.post(
    "/query",
    response_model=RAGQueryResponse,
    status_code=status.HTTP_200_OK,
    summary="Ask Cogniva: Grounded RAG question answering",
    description="Executes semantic retrieval across user knowledge base, packages evidence into structured context, and generates a grounded factual answer via LLM.",
    dependencies=[Depends(rate_limit_llm)],
)
async def query_rag(
    payload: RAGQueryRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RAGQueryResponse:
    """
    RAG Query endpoint.
    Performs tenant-isolated retrieval and grounded answer synthesis.
    """
    return await rag_service.answer_query(
        db=db,
        user_id=current_user.id,
        query=payload.query,
        top_k=payload.top_k,
        document_id=payload.document_id,
        min_similarity=payload.min_similarity,
        conversation_id=payload.conversation_id,
    )
