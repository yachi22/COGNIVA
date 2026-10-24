from typing import Any, Dict
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.schemas.audit import AuditLogListResponse
from app.services.audit_service import audit_service

router = APIRouter(tags=["audit"])


@router.get(
    "/audit-logs",
    response_model=AuditLogListResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve tenant security and operational audit logs",
)
async def list_audit_logs(
    limit: int = Query(50, ge=1, le=100),
    skip: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    logs, total = await audit_service.list_user_logs(
        db=db,
        user_id=current_user.id,
        limit=limit,
        skip=skip,
    )
    return {
        "items": logs,
        "total": total,
    }


@router.get(
    "/audit",
    response_model=AuditLogListResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve tenant security and operational audit logs (alias)",
)
async def list_audit_logs_alias(
    limit: int = Query(50, ge=1, le=100),
    skip: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await list_audit_logs(limit=limit, skip=skip, db=db, current_user=current_user)

