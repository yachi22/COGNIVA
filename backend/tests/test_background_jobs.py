import asyncio
import io
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi import HTTPException, status

from app.models.chunk import DocumentChunk
from app.models.document import Document
from app.models.job import DocumentJob
from app.services.documents.chunker import ChunkData
from app.services.documents.extractor import ExtractedDocument, ExtractedUnit
from app.services.embeddings import EmbeddingError
from app.services.job_service import DocumentJobService


# ---------------------------------------------------------------------------
# 1. Job Creation and Idempotency Tests
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_job_idempotency_returns_existing_active_job():
    """
    Verifies that duplicate concurrent or rapid processing requests for the same
    document return the existing active job rather than spawning redundant pipelines.
    """
    svc = DocumentJobService()
    svc.dispatch_background_job = MagicMock()
    user_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    job_id = uuid.uuid4()

    mock_doc = MagicMock(spec=Document)
    mock_doc.id = doc_id
    mock_doc.user_id = user_id
    mock_doc.status = "uploaded"
    mock_doc.metadata_ = {}

    existing_active_job = MagicMock(spec=DocumentJob)
    existing_active_job.id = job_id
    existing_active_job.document_id = doc_id
    existing_active_job.user_id = user_id
    existing_active_job.status = "processing"
    existing_active_job.stage = "embedding"
    existing_active_job.progress = 60

    mock_db = AsyncMock()

    def db_execute_side_effect(stmt):
        mock_res = MagicMock()
        stmt_str = str(stmt)
        if "FROM documents" in stmt_str:
            mock_res.scalar_one_or_none.return_value = mock_doc
        elif "FROM document_jobs" in stmt_str:
            mock_res.scalar_one_or_none.return_value = existing_active_job
        return mock_res

    mock_db.execute.side_effect = db_execute_side_effect

    job, is_new = await svc.create_or_get_job(
        db=mock_db,
        user_id=user_id,
        document_id=doc_id,
        force=False,
    )

    assert is_new is False
    assert job.id == job_id
    assert job.status == "processing"
    assert job.stage == "embedding"
    mock_db.add.assert_not_called()


@pytest.mark.asyncio
async def test_job_idempotency_already_processed_document():
    """
    Verifies that a request to process an already 'processed' document returns
    the latest completed job without re-triggering embedding unless force=True.
    """
    svc = DocumentJobService()
    svc.dispatch_background_job = MagicMock()
    user_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    job_id = uuid.uuid4()

    mock_doc = MagicMock(spec=Document)
    mock_doc.id = doc_id
    mock_doc.user_id = user_id
    mock_doc.status = "processed"
    mock_doc.metadata_ = {}

    completed_job = MagicMock(spec=DocumentJob)
    completed_job.id = job_id
    completed_job.document_id = doc_id
    completed_job.user_id = user_id
    completed_job.status = "completed"
    completed_job.stage = "completed"
    completed_job.progress = 100

    mock_db = AsyncMock()

    def db_execute_side_effect(stmt):
        mock_res = MagicMock()
        stmt_str = str(stmt)
        if "FROM documents" in stmt_str:
            mock_res.scalar_one_or_none.return_value = mock_doc
        elif "status IN" in stmt_str or "status in" in stmt_str.lower():
            # No active running job
            mock_res.scalar_one_or_none.return_value = None
        elif "status = :status_1" in stmt_str or "completed" in stmt_str:
            mock_res.scalar_one_or_none.return_value = completed_job
        return mock_res

    mock_db.execute.side_effect = db_execute_side_effect

    job, is_new = await svc.create_or_get_job(
        db=mock_db,
        user_id=user_id,
        document_id=doc_id,
        force=False,
    )

    assert is_new is False
    assert job.status == "completed"


# ---------------------------------------------------------------------------
# 2. Bounded Retries with Backoff & Retry Exhaustion Tests
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_embed_chunks_bounded_retries_transient_recovery():
    """
    Verifies that transient errors during embedding trigger bounded retries
    with exponential backoff, updating retry_count, and succeed if error resolves.
    """
    svc = DocumentJobService()
    job = DocumentJob(
        id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        status="processing",
        stage="embedding",
        retry_count=0,
        max_retries=3,
        metadata_={},
    )
    chunks = [ChunkData(chunk_index=0, content="Test content", token_count=2, page_number=1, metadata={})]

    mock_db = AsyncMock()
    call_count = 0

    async def mock_embed_chunks(texts):
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            raise EmbeddingError("Transient rate limit or 503 network error")
        return [[0.1] * 1536]

    with patch("app.services.job_service.embedding_service.embed_chunks", side_effect=mock_embed_chunks):
        with patch("app.services.job_service.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            embeddings = await svc._embed_chunks_with_retry(db=mock_db, job=job, chunks=chunks)

    assert len(embeddings) == 1
    assert len(embeddings[0]) == 1536
    assert job.retry_count == 1
    assert len(job.metadata_["retries"]) == 1
    mock_sleep.assert_awaited_once()


@pytest.mark.asyncio
async def test_embed_chunks_retry_exhaustion_marks_failure():
    """
    Verifies that persistent failures exceeding max_retries exhaust the retry
    budget and raise an error, recording the full attempt history in metadata.
    """
    svc = DocumentJobService()
    job = DocumentJob(
        id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        status="processing",
        stage="embedding",
        retry_count=0,
        max_retries=2,
        metadata_={},
    )
    chunks = [ChunkData(chunk_index=0, content="Exhaustion test", token_count=2, page_number=1, metadata={})]

    mock_db = AsyncMock()

    with patch(
        "app.services.job_service.embedding_service.embed_chunks",
        side_effect=EmbeddingError("Persistent downstream error"),
    ):
        with patch("app.services.job_service.asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(EmbeddingError) as exc_info:
                await svc._embed_chunks_with_retry(db=mock_db, job=job, chunks=chunks)

    assert "failed after 2 retries" in str(exc_info.value).lower()
    assert job.retry_count == 3
    assert len(job.metadata_["retries"]) == 3
    assert "Persistent downstream error" in job.error_message


# ---------------------------------------------------------------------------
# 3. Safe Recovery of Interrupted Jobs after Restart Tests
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_startup_recovery_completes_jobs_with_existing_chunks():
    """
    Simulates container reboot while a job was marked 'processing':
    If PostgreSQL already holds the generated chunks and vector embeddings,
    the startup sweeper marks the job 'completed' and document 'processed'.
    """
    svc = DocumentJobService()
    svc.dispatch_background_job = MagicMock()
    user_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    job_id = uuid.uuid4()

    interrupted_job = DocumentJob(
        id=job_id,
        document_id=doc_id,
        user_id=user_id,
        status="processing",
        stage="indexing",
        progress=85,
        retry_count=0,
        max_retries=3,
        metadata_={},
    )

    mock_doc = Document(
        id=doc_id,
        user_id=user_id,
        filename=f"{doc_id.hex}.pdf",
        original_filename="audit.pdf",
        file_type="pdf",
        storage_path=f"documents/{user_id}/{doc_id.hex}.pdf",
        status="processing",
    )

    mock_chunk = DocumentChunk(
        id=uuid.uuid4(),
        document_id=doc_id,
        chunk_index=0,
        content="Safely persisted chunk content",
        page_number=1,
    )

    mock_db = AsyncMock()

    def db_execute_side_effect(stmt):
        mock_res = MagicMock()
        stmt_str = str(stmt)
        if "FROM document_jobs" in stmt_str:
            mock_res.scalars.return_value.all.return_value = [interrupted_job]
        elif "FROM documents" in stmt_str:
            mock_res.scalar_one_or_none.return_value = mock_doc
        elif "FROM document_chunks" in stmt_str:
            mock_res.scalar_one_or_none.return_value = mock_chunk
        return mock_res

    mock_db.execute.side_effect = db_execute_side_effect

    report = await svc.recover_interrupted_jobs(db=mock_db)

    assert report["total_interrupted"] == 1
    assert report["recovered_completed"] == 1
    assert interrupted_job.status == "completed"
    assert interrupted_job.progress == 100
    assert interrupted_job.metadata_["recovered_on_startup"] is True
    assert mock_doc.status == "processed"


@pytest.mark.asyncio
async def test_startup_recovery_handles_missing_ephemeral_binary():
    """
    Simulates container reboot when no chunks exist and the ephemeral binary was purged:
    Marks the job and document 'failed' with a clear explanatory notice.
    """
    svc = DocumentJobService()
    svc.dispatch_background_job = MagicMock()
    user_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    job_id = uuid.uuid4()

    interrupted_job = DocumentJob(
        id=job_id,
        document_id=doc_id,
        user_id=user_id,
        status="processing",
        stage="extracting",
        progress=10,
        retry_count=0,
        max_retries=3,
        metadata_={},
    )

    mock_doc = Document(
        id=doc_id,
        user_id=user_id,
        filename=f"{doc_id.hex}.pdf",
        original_filename="missing_test.pdf",
        file_type="pdf",
        storage_path=f"documents/{user_id}/nonexistent_{doc_id.hex}.pdf",
        status="processing",
    )

    mock_db = AsyncMock()

    def db_execute_side_effect(stmt):
        mock_res = MagicMock()
        stmt_str = str(stmt)
        if "FROM document_jobs" in stmt_str:
            mock_res.scalars.return_value.all.return_value = [interrupted_job]
        elif "FROM documents" in stmt_str:
            mock_res.scalar_one_or_none.return_value = mock_doc
        elif "FROM document_chunks" in stmt_str:
            mock_res.scalar_one_or_none.return_value = None  # No chunks
        return mock_res

    mock_db.execute.side_effect = db_execute_side_effect

    report = await svc.recover_interrupted_jobs(db=mock_db)

    assert report["total_interrupted"] == 1
    assert report["marked_failed"] == 1
    assert interrupted_job.status == "failed"
    assert "interrupted by container restart" in interrupted_job.error_message
    assert mock_doc.status == "failed"


# ---------------------------------------------------------------------------
# 4. Multi-Tenant Authorization Security Tests
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_job_cross_tenant_denial():
    """
    Verifies that a tenant cannot inspect or retry jobs belonging to another user.
    Enforces strict 404 response to prevent IDOR enumeration.
    """
    svc = DocumentJobService()
    owner_id = uuid.uuid4()
    attacker_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    job_id = uuid.uuid4()

    mock_db = AsyncMock()
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_res

    # 1. Inspect single job
    with pytest.raises(HTTPException) as exc:
        await svc.get_job(db=mock_db, user_id=attacker_id, document_id=doc_id, job_id=job_id)
    assert exc.value.status_code == status.HTTP_404_NOT_FOUND

    # 2. Get latest job for document
    with pytest.raises(HTTPException) as exc_latest:
        await svc.get_latest_job(db=mock_db, user_id=attacker_id, document_id=doc_id)
    assert exc_latest.value.status_code == status.HTTP_404_NOT_FOUND

    # 3. Retry job
    with pytest.raises(HTTPException) as exc_retry:
        await svc.retry_job(db=mock_db, user_id=attacker_id, document_id=doc_id, job_id=job_id)
    assert exc_retry.value.status_code == status.HTTP_404_NOT_FOUND


# ---------------------------------------------------------------------------
# 5. Missing Physical Binary Zero-Budget Recovery Preservation Test
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_pipeline_zero_budget_recovery_preserves_processed_state():
    """
    Verifies that when ephemeral disk file is absent but PostgreSQL has persisted chunks:
    The pipeline preserves document status 'processed' and marks job 'completed' (100%).
    """
    svc = DocumentJobService()
    svc.dispatch_background_job = MagicMock()
    user_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    job_id = uuid.uuid4()

    job = DocumentJob(
        id=job_id,
        document_id=doc_id,
        user_id=user_id,
        status="processing",
        stage="extracting",
        progress=10,
        metadata_={},
    )

    doc = Document(
        id=doc_id,
        user_id=user_id,
        filename=f"{doc_id.hex}.pdf",
        original_filename="recovered.pdf",
        file_type="pdf",
        storage_path=f"documents/{user_id}/missing_{doc_id.hex}.pdf",
        status="processing",
        metadata_={},
    )

    mock_chunk = DocumentChunk(
        id=uuid.uuid4(),
        document_id=doc_id,
        chunk_index=0,
        content="Durable PostgreSQL chunk",
        page_number=1,
    )

    mock_db = AsyncMock()

    def db_execute_side_effect(stmt):
        mock_res = MagicMock()
        stmt_str = str(stmt)
        if "FROM document_chunks" in stmt_str:
            mock_res.scalars.return_value.all.return_value = [mock_chunk]
        return mock_res

    mock_db.execute.side_effect = db_execute_side_effect

    await svc._execute_pipeline(db=mock_db, job=job, document=doc)

    assert doc.status == "processed"
    assert doc.metadata_["missing_binary_on_ephemeral_disk"] is True
    assert doc.metadata_["recovered_from_chunks"] is True
    assert job.status == "completed"
    assert job.stage == "completed"
    assert job.progress == 100
