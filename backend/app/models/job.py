import uuid
from datetime import datetime, timezone
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

    @property
    def duration_seconds(self) -> Optional[float]:
        """Calculates runtime duration in seconds."""
        if self.started_at and self.completed_at:
            return round((self.completed_at - self.started_at).total_seconds(), 2)
        return (self.metadata_ or {}).get("duration_seconds")

    @property
    def is_stuck(self) -> bool:
        return self.diagnose()["is_stuck"]

    @property
    def retries_exhausted(self) -> bool:
        return self.diagnose()["retries_exhausted"]

    @property
    def failure_category(self) -> Optional[str]:
        return self.diagnose()["failure_category"]

    @property
    def diagnosis(self) -> Optional[str]:
        return self.diagnose()["diagnosis"]

    def diagnose(self, timeout_seconds: int = 300) -> Dict[str, Any]:
        """
        Diagnoses job operational state, detecting stuck jobs, retry exhaustion,
        failure categories, and actionable recommendations.
        """
        is_stuck = False
        elapsed = 0.0
        if self.status in ("pending", "processing") and self.started_at:
            now = datetime.now(timezone.utc)
            started = self.started_at if self.started_at.tzinfo else self.started_at.replace(tzinfo=timezone.utc)
            elapsed = (now - started).total_seconds()
            if elapsed > timeout_seconds:
                is_stuck = True

        retries_exhausted = self.status == "failed" and self.retry_count >= self.max_retries

        category = (self.metadata_ or {}).get("failure_category")
        if not category:
            if is_stuck:
                category = "timeout_error"
            elif retries_exhausted:
                category = "retry_exhaustion"
            elif self.error_message and "timeout" in self.error_message.lower():
                category = "timeout_error"
            elif self.error_message and "embed" in self.error_message.lower():
                category = "embedding_provider_error"
            elif self.error_message and "extract" in self.error_message.lower():
                category = "extraction_error"
            elif self.error_message and "missing" in self.error_message.lower():
                category = "missing_binary"
            elif self.status == "failed":
                category = "pipeline_failure"

        diagnosis = None
        if is_stuck:
            diagnosis = f"Job appears stuck in stage '{self.stage}' for {int(elapsed)}s (exceeding {timeout_seconds}s limit). Trigger /retry to re-queue."
        elif retries_exhausted:
            diagnosis = f"Job exhausted all {self.max_retries} retries. Cause: {self.error_message or 'Downstream provider failure'}. Trigger /retry to re-attempt."
        elif self.status == "failed":
            diagnosis = f"Job failed: {self.error_message or 'Internal execution failure'}."
        elif self.status == "completed":
            diagnosis = "Job completed successfully."
        else:
            diagnosis = f"Job active in stage '{self.stage}' ({self.progress}% complete)."

        return {
            "is_stuck": is_stuck,
            "retries_exhausted": retries_exhausted,
            "failure_category": category,
            "diagnosis": diagnosis,
            "duration_seconds": self.duration_seconds,
        }

    def __repr__(self) -> str:
        return f"<DocumentJob id={self.id} doc_id={self.document_id} status={self.status} stage={self.stage} progress={self.progress}%>"

