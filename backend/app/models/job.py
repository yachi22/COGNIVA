import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, Optional
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.document import Document
    from app.models.user import User


class DocumentJob(Base):
    """
    DocumentJob model representing asynchronous background document processing jobs.
    Tracks live stage progress, bounded retries with backoff, timeouts, and restart recovery state.
    Enforces strict tenant isolation via indexed user_id foreign key.
    """
    __tablename__ = "document_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default="pending",
        index=True,
        nullable=False,
    )  # pending, processing, completed, failed, cancelled
    stage: Mapped[str] = mapped_column(
        String(50),
        default="queued",
        nullable=False,
    )  # queued, extracting, chunking, embedding, indexing, completed, failed
    progress: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )  # 0 to 100
    current_stage: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    total_stages: Mapped[int] = mapped_column(
        Integer,
        default=4,
        nullable=False,
    )
    retry_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    max_retries: Mapped[int] = mapped_column(
        Integer,
        default=3,
        nullable=False,
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    metadata_: Mapped[Dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        default=dict,
        server_default=text("'{}'::jsonb"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    document: Mapped["Document"] = relationship(
        "Document",
        back_populates="jobs",
    )
    user: Mapped["User"] = relationship(
        "User",
    )

    def __repr__(self) -> str:
        return f"<DocumentJob id={self.id} doc_id={self.document_id} status={self.status} stage={self.stage} progress={self.progress}%>"
