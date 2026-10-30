import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_user
from app.core.rate_limiter import rate_limit_llm
from app.models.user import User
from app.schemas.intelligence import (
    DeepResearchRequest,
    DeepResearchResponse,
    KnowledgeGraphResponse,
)
from app.services.research_service import ResearchService
from app.services.knowledge_graph_service import KnowledgeGraphService
from app.services.audit_service import audit_service

router = APIRouter(tags=["research"])
research_service = ResearchService()
knowledge_graph_service = KnowledgeGraphService()


@router.post(
    "/research/deep-query",
    response_model=DeepResearchResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute multi-step evidence-grounded deep research",
    dependencies=[Depends(rate_limit_llm)],
)
async def execute_deep_research(
    data: DeepResearchRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await research_service.execute_deep_research(
        db=db,
        user_id=current_user.id,
        topic=data.topic,
        document_id=data.document_id,
        max_subquestions=data.max_subquestions,
    )

    await audit_service.log_event(
        db=db,
        action="DEEP_RESEARCH_QUERY",
        resource_type="research",
        user_id=current_user.id,
        resource_id=result.get("research_id"),
        details={"topic": data.topic, "subquestions": len(result.get("subquestions", []))},
    )

    return result


@router.get(
    "/knowledge-graph",
    response_model=KnowledgeGraphResponse,
    status_code=status.HTTP_200_OK,
    summary="Extract authentic entity-relationship graph from tenant documents",
)
async def get_knowledge_graph(
    document_id: Optional[uuid.UUID] = Query(None, description="Optional document filter"),
    max_chunks: int = Query(8, ge=1, le=20, description="Max chunk depth"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await knowledge_graph_service.get_tenant_knowledge_graph(
        db=db,
        user_id=current_user.id,
        document_id=document_id,
        max_chunks=max_chunks,
    )
    return result
