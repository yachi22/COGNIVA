import logging
import uuid
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog

logger = logging.getLogger("cogniva.audit_service")


class AuditService:
    """
    Records immutable security and operational audit trail records.
    Filters credentials, passwords, and authorization tokens.
    """

    @staticmethod
    def sanitize_details(details: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        if not details:
            return {}
        sanitized = dict(details)
        sensitive_keys = {"password", "token", "secret", "access_token", "hashed_password", "api_key", "secret_key"}
        for k in list(sanitized.keys()):
            if any(s in k.lower() for s in sensitive_keys):
                sanitized[k] = "[REDACTED]"
        return sanitized

    async def log_event(
        self,
        db: AsyncSession,
        action: str,
        resource_type: str,
        user_id: Optional[uuid.UUID] = None,
        resource_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        status: str = "SUCCESS",
        details: Optional[Dict[str, Any]] = None,
    ) -> AuditLog:
        try:
            entry = AuditLog(
                id=uuid.uuid4(),
                user_id=user_id,
                action=action,
                resource_type=resource_type,
                resource_id=str(resource_id) if resource_id else None,
                ip_address=ip_address,
                status=status,
                details=self.sanitize_details(details),
            )
            db.add(entry)
            await db.commit()
            return entry
        except Exception as e:
            logger.error(f"Failed to persist audit log: {str(e)}", exc_info=True)
            await db.rollback()
            # Non-blocking for primary transaction
            return AuditLog(
                id=uuid.uuid4(),
                action=action,
                resource_type=resource_type,
                status="FAILED_TO_LOG",
            )

    async def list_user_logs(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        limit: int = 50,
        skip: int = 0,
    ) -> Tuple[List[Dict[str, Any]], int]:
        count_stmt = select(func.count(AuditLog.id)).where(AuditLog.user_id == user_id)
        count_res = await db.execute(count_stmt)
        total = count_res.scalar() or 0

        stmt = (
            select(AuditLog)
            .where(AuditLog.user_id == user_id)
            .order_by(AuditLog.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        res = await db.execute(stmt)
        entries = res.scalars().all()

        items = [
            {
                "id": str(e.id),
                "action": e.action,
                "resource_type": e.resource_type,
                "resource_id": e.resource_id,
                "ip_address": e.ip_address,
                "status": e.status,
                "details": e.details,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in entries
        ]
        return items, total


audit_service = AuditService()
