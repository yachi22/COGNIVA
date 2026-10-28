import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class DocumentJobResponse(BaseModel):
    """
    Detailed background processing job state and progress model.
    """
    id: uuid.UUID
    document_id: uuid.UUID
    user_id: uuid.UUID
    status: str = Field(..., description="'pending', 'processing', 'completed', 'failed', 'cancelled'")
    stage: str = Field(..., description="'queued', 'extracting', 'chunking', 'embedding', 'indexing', 'completed', 'failed'")
    progress: int = Field(..., ge=0, le=100, description="Percentage of job completed (0-100)")
    current_stage: int
    total_stages: int
    retry_count: int
    max_retries: int
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict, validation_alias="metadata_")
    created_at: datetime
    updated_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class DocumentJobListResponse(BaseModel):
    """
    Collection of background processing jobs for a document.
    """
    total: int
    document_id: uuid.UUID
    jobs: List[DocumentJobResponse]


class DocumentJobProgressResponse(BaseModel):
    """
    Lightweight progress polling response for low-overhead frontend polling.
    """
    job_id: uuid.UUID
    document_id: uuid.UUID
    status: str
    stage: str
    progress: int
    is_active: bool
    retry_count: int
    error_message: Optional[str] = None
    updated_at: datetime
