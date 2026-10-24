from typing import Any, Dict
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.services.evaluation_service import EvaluationService

router = APIRouter(tags=["evaluation"])
evaluation_service = EvaluationService()


@router.get(
    "/evaluation/metrics",
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Retrieve live and benchmark retrieval/generation quality metrics",
)
async def get_evaluation_metrics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    metrics = await evaluation_service.get_system_evaluation_metrics(
        db=db,
        user_id=current_user.id,
    )
    return metrics


@router.get(
    "/evaluation/telemetry",
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Retrieve live and benchmark retrieval/generation quality telemetry (alias)",
)
async def get_evaluation_telemetry(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await evaluation_service.get_system_evaluation_metrics(
        db=db,
        user_id=current_user.id,
    )

