from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class AuditLogItem(BaseModel):
    id: str
    action: str
    resource_type: str
    resource_id: Optional[str] = None
    ip_address: Optional[str] = None
    status: str
    details: Dict[str, Any] = {}
    created_at: Optional[str] = None


class AuditLogListResponse(BaseModel):
    items: List[AuditLogItem]
    total: int
