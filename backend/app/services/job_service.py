import asyncio
import logging
import random
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy import delete, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.chunk import DocumentChunk
from app.models.document import Document
from app.models.job import DocumentJob
from app.services.documents.chunker import ChunkData, document_chunker
from app.services.documents.cleaner import clean_extracted_text
from app.services.documents.extractor import (
    ExtractedDocument,
    ExtractionError,
    document_extractor,
)
from app.services.embeddings import (
    embedding_service,
    EmbeddingError,
    MissingEmbeddingConfigurationError,
    DimensionMismatchError,
)
from app.services.storage import storage_service

logger = logging.getLogger("cogniva.services.job")

# Transient exceptions eligible for bounded retries with exponential backoff
TRANSIENT_EXCEPTIONS = (
    TimeoutError,
    asyncio.TimeoutError,
    ConnectionError,
    EmbeddingError,
)

try:
    import httpx
    TRANSIENT_EXCEPTIONS = TRANSIENT_EXCEPTIONS + (
        httpx.ConnectTimeout,
        httpx.ReadTimeout,
        httpx.NetworkError,
    )
except ImportError:
    pass

try:
    import openai
    TRANSIENT_EXCEPTIONS = TRANSIENT_EXCEPTIONS + (
        openai.RateLimitError,
        openai.APIConnectionError,
        openai.APITimeoutError,
        openai.InternalServerError,
    )
except ImportError:
    pass


class DocumentJobService:
    """
    Zero-additional-cost reliable background document processing service.
    Orchestrates ingestion pipeline with:
    - Live stage and progress reporting
    - Bounded retries with exponential backoff and jitter
    - Configurable timeouts
    - Strict multi-tenant authorization
    - Idempotent deduplication (duplicate request prevention)
    - Safe restart recovery for interrupted/zombie jobs
    - Safe handling of missing ephemeral binaries (Phase 11.2 preservation)
    """

    def __init__(self):
        self._concurrency_semaphore: Optional[asyncio.Semaphore] = None
        self._active_tasks: Dict[uuid.UUID, asyncio.Task] = {}

    @property
    def semaphore(self) -> asyncio.Semaphore:
        if self._concurrency_semaphore is None:
            self._concurrency_semaphore = asyncio.Semaphore(settings.DOCUMENT_PROCESSING_MAX_CONCURRENCY)
        return self._concurrency_semaphore

    async def get_user_document(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        document_id: uuid.UUID,
    ) -> Document:
        """Enforces tenant isolation: document must belong to requesting user."""
        stmt = select(Document).where(Document.id == document_id, Document.user_id == user_id)
        result = await db.execute(stmt)
        document = result.scalar_one_or_none()
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found or access denied."
            )
        return document

    async def get_job(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        document_id: uuid.UUID,
        job_id: uuid.UUID,
    ) -> DocumentJob:
        """Enforces tenant isolation for job inspection."""
        stmt = select(DocumentJob).where(
            DocumentJob.id == job_id,
            DocumentJob.document_id == document_id,
            DocumentJob.user_id == user_id,
        )
        res = await db.execute(stmt)
        job = res.scalar_one_or_none()
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Processing job not found."
            )
        return job

    async def get_latest_job(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        document_id: uuid.UUID,
    ) -> Optional[DocumentJob]:
        """Returns the most recent processing job for a document belonging to user."""
        await self.get_user_document(db=db, user_id=user_id, document_id=document_id)
        stmt = (
            select(DocumentJob)
            .where(DocumentJob.document_id == document_id, DocumentJob.user_id == user_id)
            .order_by(desc(DocumentJob.created_at))
            .limit(1)
        )
        res = await db.execute(stmt)
        return res.scalar_one_or_none()

    async def get_document_jobs(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        document_id: uuid.UUID,
    ) -> List[DocumentJob]:
        """Returns all processing jobs for a document belonging to user."""
        await self.get_user_document(db=db, user_id=user_id, document_id=document_id)
        stmt = (
            select(DocumentJob)
            .where(DocumentJob.document_id == document_id, DocumentJob.user_id == user_id)
            .order_by(desc(DocumentJob.created_at))
        )
        res = await db.execute(stmt)
        return list(res.scalars().all())

    async def create_or_get_job(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        document_id: uuid.UUID,
        force: bool = False,
    ) -> Tuple[DocumentJob, bool]:
        """
        Idempotent job creation:
        - If an active job (pending or processing) already exists, returns it without creating a duplicate.
        - If document is already 'processed' and force is False, returns completed job.
        - Otherwise, creates a new job record in 'pending' state.
        Returns: (job, is_new)
        """
        document = await self.get_user_document(db=db, user_id=user_id, document_id=document_id)

        # 1. Check for active running job (Idempotency check)
        active_stmt = (
            select(DocumentJob)
            .where(
                DocumentJob.document_id == document_id,
                DocumentJob.user_id == user_id,
                DocumentJob.status.in_(["pending", "processing"]),
            )
            .order_by(desc(DocumentJob.created_at))
            .limit(1)
        )
        active_res = await db.execute(active_stmt)
        active_job = active_res.scalar_one_or_none()

        if active_job and not force:
            logger.info(f"Returning existing active job {active_job.id} for document {document_id}")
            return active_job, False

        # 2. Check if already processed and not forced
        if document.status == "processed" and not force:
            latest_stmt = (
                select(DocumentJob)
                .where(
                    DocumentJob.document_id == document_id,
                    DocumentJob.user_id == user_id,
                    DocumentJob.status == "completed",
                )
                .order_by(desc(DocumentJob.created_at))
                .limit(1)
            )
            latest_res = await db.execute(latest_stmt)
            latest_job = latest_res.scalar_one_or_none()
            if latest_job:
                return latest_job, False

        # 3. Create fresh job
        job = DocumentJob(
            id=uuid.uuid4(),
            document_id=document_id,
            user_id=user_id,
            status="pending",
            stage="queued",
            progress=0,
            current_stage=0,
            total_stages=4,
            retry_count=0,
            max_retries=settings.DOCUMENT_PROCESSING_MAX_RETRIES,
            error_message=None,
            metadata_={},
        )
        add_res = db.add(job)
        if asyncio.iscoroutine(add_res):
            await add_res

        # Update document status to processing
        document.status = "processing"
        doc_meta = dict(document.metadata_ or {})
        doc_meta["active_job_id"] = str(job.id)
        document.metadata_ = doc_meta

        await db.commit()
        await db.refresh(job)
        await db.refresh(document)
        return job, True

    def dispatch_background_job(self, job_id: uuid.UUID) -> None:
        """
        Dispatches background worker task using asyncio.create_task.
        Maintains reference in active_tasks to prevent garbage collection.
        """
        task = asyncio.create_task(self.run_job(job_id=job_id))
        self._active_tasks[job_id] = task

        def _cleanup(t: asyncio.Task):
            self._active_tasks.pop(job_id, None)
            if t.exception() and not t.cancelled():
                logger.error(f"Background job {job_id} task encountered unhandled error: {t.exception()}")

        task.add_done_callback(_cleanup)

    async def run_job(self, job_id: uuid.UUID) -> DocumentJob:
        """
        Executes background document processing pipeline with:
        - Concurrency bounding via Semaphore
        - Stage progress reporting: extracting -> chunking -> embedding -> indexing -> completed
        - Bounded retries with exponential backoff on transient errors
        - Timeout protection (DOCUMENT_PROCESSING_TIMEOUT_SECONDS)
        """
        async with self.semaphore:
            async with AsyncSessionLocal() as db:
                stmt = select(DocumentJob).where(DocumentJob.id == job_id)
                res = await db.execute(stmt)
                job = res.scalar_one_or_none()
                if not job:
                    logger.error(f"Cannot run job {job_id}: record not found in database.")
                    return None

                doc_stmt = select(Document).where(Document.id == job.document_id)
                doc_res = await db.execute(doc_stmt)
                document = doc_res.scalar_one_or_none()
                if not document:
                    job.status = "failed"
                    job.stage = "failed"
                    job.error_message = "Associated document was deleted."
                    job.completed_at = datetime.now(timezone.utc)
                    await db.commit()
                    return job

                # Set started state
                job.status = "processing"
                job.stage = "extracting"
                job.current_stage = 1
                job.progress = 10
                job.started_at = datetime.now(timezone.utc)
                document.status = "processing"
                await db.commit()

                # Execute with pipeline-level timeout
                try:
                    async with asyncio.timeout(settings.DOCUMENT_PROCESSING_TIMEOUT_SECONDS):
                        await self._execute_pipeline(db=db, job=job, document=document)
                except (TimeoutError, asyncio.TimeoutError):
                    logger.error(f"Job {job.id} timed out after {settings.DOCUMENT_PROCESSING_TIMEOUT_SECONDS}s.")
                    await db.rollback()
                    # Refresh fresh handles
                    res = await db.execute(select(DocumentJob).where(DocumentJob.id == job_id))
                    job = res.scalar_one()
                    d_res = await db.execute(select(Document).where(Document.id == job.document_id))
                    document = d_res.scalar_one()

                    timeout_msg = f"Document processing timed out after {settings.DOCUMENT_PROCESSING_TIMEOUT_SECONDS} seconds."
                    job.status = "failed"
                    job.stage = "failed"
                    job.error_message = timeout_msg
                    job.completed_at = datetime.now(timezone.utc)

                    document.status = "failed"
                    d_meta = dict(document.metadata_ or {})
                    d_meta["error"] = timeout_msg
                    document.metadata_ = d_meta

                    await db.commit()
                except Exception as exc:
                    logger.error(f"Job {job.id} failed with unhandled exception: {exc}", exc_info=True)
                    await db.rollback()
                    res = await db.execute(select(DocumentJob).where(DocumentJob.id == job_id))
                    job = res.scalar_one()
                    d_res = await db.execute(select(Document).where(Document.id == job.document_id))
                    document = d_res.scalar_one()

                    err_msg = str(exc)
                    job.status = "failed"
                    job.stage = "failed"
                    job.error_message = err_msg
                    job.completed_at = datetime.now(timezone.utc)

                    document.status = "failed"
                    d_meta = dict(document.metadata_ or {})
                    d_meta["error"] = err_msg
                    document.metadata_ = d_meta

                    await db.commit()

                return job

    async def _execute_pipeline(
        self,
        db: AsyncSession,
        job: DocumentJob,
        document: Document,
    ) -> None:
        """Internal execution pipeline with stage updates and retries."""
        user_id = job.user_id
        document_id = document.id

        # -------------------------------------------------------------
        # Stage 1: Text Extraction (PyMuPDF / docx / local storage verification)
        # -------------------------------------------------------------
        full_file_path = storage_service.get_full_path(document.storage_path)
        if not full_file_path.exists() or not full_file_path.is_file():
            # Ephemeral container restart: attempt restore from storage provider
            try:
                binary_bytes = await storage_service.get_document_bytes(
                    user_id=user_id,
                    storage_path=document.storage_path,
                    metadata_=document.metadata_,
                )
                user_dir = storage_service.get_user_storage_dir(user_id)
                full_file_path = user_dir / document.filename
                with open(full_file_path, "wb") as f:
                    f.write(binary_bytes)
            except Exception as e:
                logger.warning(f"Could not restore binary from storage provider for doc {document.id}: {e}")

        # Missing physical binary check (Zero-Budget recovery)
        if not full_file_path.exists() or not full_file_path.is_file():
            chunk_stmt = (
                select(DocumentChunk)
                .where(DocumentChunk.document_id == document.id)
                .order_by(DocumentChunk.chunk_index.asc())
            )
            res = await db.execute(chunk_stmt)
            existing_chunks = list(res.scalars().all())

            if existing_chunks:
                logger.info(
                    f"Document {document_id} original binary is not on ephemeral disk, "
                    f"but {len(existing_chunks)} chunks are already safely persisted in PostgreSQL. Preserving processed state."
                )
                current_metadata = dict(document.metadata_ or {})
                current_metadata["missing_binary_on_ephemeral_disk"] = True
                current_metadata["recovered_from_chunks"] = True
                document.status = "processed"
                document.metadata_ = current_metadata

                job.status = "completed"
                job.stage = "completed"
                job.progress = 100
                job.current_stage = 4
                job.completed_at = datetime.now(timezone.utc)
                job_meta = dict(job.metadata_ or {})
                job_meta["recovered_from_chunks"] = True
                job.metadata_ = job_meta

                await db.commit()
                return
            else:
                missing_msg = (
                    "Original document binary was lost during ephemeral container restart before text extraction. "
                    "Please re-upload the document."
                )
                document.status = "failed"
                doc_meta = dict(document.metadata_ or {})
                doc_meta["error"] = missing_msg
                document.metadata_ = doc_meta

                job.status = "failed"
                job.stage = "failed"
                job.error_message = missing_msg
                job.completed_at = datetime.now(timezone.utc)
                await db.commit()
                return

        # Execute extraction
        try:
            extracted: ExtractedDocument = document_extractor.extract(
                file_path=full_file_path,
                file_type=document.file_type,
                document_id=document.id,
            )
        except Exception as e:
            raise ExtractionError(f"Extraction failed: {str(e)}")

        extracted_path = storage_service.save_extracted_json(
            user_id=user_id,
            relative_storage_path=document.storage_path,
            data=extracted.model_dump(mode="json"),
        )

        # -------------------------------------------------------------
        # Stage 2: Chunking
        # -------------------------------------------------------------
        job.stage = "chunking"
        job.current_stage = 2
        job.progress = 35
        await db.commit()

        chunks: List[ChunkData] = document_chunker.chunk_document(extracted)

        # -------------------------------------------------------------
        # Stage 3: Embedding with Bounded Retries & Backoff
        # -------------------------------------------------------------
        job.stage = "embedding"
        job.current_stage = 3
        job.progress = 60
        await db.commit()

        embeddings = await self._embed_chunks_with_retry(db=db, job=job, chunks=chunks)

        # -------------------------------------------------------------
        # Stage 4: Indexing & Atomic Database Persistence
        # -------------------------------------------------------------
        job.stage = "indexing"
        job.current_stage = 4
        job.progress = 85
        await db.commit()

        # Idempotently delete previous chunks for this document
        await db.execute(
            delete(DocumentChunk).where(DocumentChunk.document_id == document.id)
        )

        for i, chunk in enumerate(chunks):
            chunk_record = DocumentChunk(
                id=uuid.uuid4(),
                document_id=document.id,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                page_number=chunk.page_number,
                metadata_=chunk.metadata,
                embedding=embeddings[i] if i < len(embeddings) else None,
            )
            db.add(chunk_record)

        # Finalize Document and Job states
        current_metadata = dict(document.metadata_ or {})
        current_metadata.update({
            "extracted_path": extracted_path,
            "extracted_at": extracted.extracted_at.isoformat(),
            "total_pages": extracted.total_pages,
            "total_units": extracted.total_units,
            "total_characters": extracted.total_characters,
            "total_words": extracted.total_words,
            "total_chunks": len(chunks),
            "embedding_model": settings.EMBEDDING_MODEL,
            "embedding_dimension": settings.EMBEDDING_DIMENSION,
            "embedded_at": datetime.now(timezone.utc).isoformat(),
            "last_completed_job_id": str(job.id),
        })
        current_metadata.pop("error", None)

        document.status = "processed"
        document.metadata_ = current_metadata

        job.status = "completed"
        job.stage = "completed"
        job.progress = 100
        job.completed_at = datetime.now(timezone.utc)
        job.error_message = None
        job_meta = dict(job.metadata_ or {})
        job_meta.update({
            "total_chunks": len(chunks),
            "total_pages": extracted.total_pages,
            "total_units": extracted.total_units,
            "completed_stage": 4,
        })
        job.metadata_ = job_meta

        await db.commit()
        await db.refresh(job)
        await db.refresh(document)

    async def _embed_chunks_with_retry(
        self,
        db: AsyncSession,
        job: DocumentJob,
        chunks: List[ChunkData],
    ) -> List[List[float]]:
        """
        Embeds chunks with bounded retries and exponential backoff with jitter
        for transient OpenAI / network exceptions.
        """
        if not chunks:
            return []

        chunk_texts = [c.content for c in chunks]
        attempt = 0
        max_retries = job.max_retries

        while attempt <= max_retries:
            try:
                embeddings = await embedding_service.embed_chunks(chunk_texts)
                return embeddings
            except TRANSIENT_EXCEPTIONS as exc:
                attempt += 1
                job.retry_count = attempt
                job_meta = dict(job.metadata_ or {})
                retry_log = job_meta.setdefault("retries", [])
                retry_log.append({
                    "attempt": attempt,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "error": str(exc),
                })
                job.metadata_ = job_meta

                if attempt > max_retries:
                    err = f"Embedding failed after {max_retries} retries: {str(exc)}"
                    job.error_message = err
                    await db.commit()
                    raise EmbeddingError(err)

                # Exponential backoff with jitter
                backoff_delay = min(30.0, (settings.DOCUMENT_PROCESSING_BASE_BACKOFF_SECONDS ** attempt) + random.uniform(0.1, 0.8))
                job.error_message = f"Transient error on attempt {attempt}/{max_retries}: {str(exc)}. Retrying in {backoff_delay:.1f}s..."
                await db.commit()
                logger.warning(f"Transient error embedding doc {job.document_id} (attempt {attempt}/{max_retries}): {exc}. Sleeping {backoff_delay:.1f}s")
                await asyncio.sleep(backoff_delay)
            except Exception as non_transient:
                # Permanent failure: configuration error, dimension mismatch, etc.
                raise non_transient

        return []

    async def retry_job(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        document_id: uuid.UUID,
        job_id: uuid.UUID,
    ) -> DocumentJob:
        """
        Manually triggers retry for a failed job or creates a new job.
        Enforces tenant authorization.
        """
        job = await self.get_job(db=db, user_id=user_id, document_id=document_id, job_id=job_id)
        if job.status in ("pending", "processing"):
            return job

        # Reset job state
        job.status = "pending"
        job.stage = "queued"
        job.progress = 0
        job.current_stage = 0
        job.retry_count = 0
        job.error_message = None
        job.started_at = None
        job.completed_at = None

        doc = await self.get_user_document(db=db, user_id=user_id, document_id=document_id)
        doc.status = "processing"

        await db.commit()
        await db.refresh(job)

        self.dispatch_background_job(job.id)
        return job

    async def recover_interrupted_jobs(self, db: AsyncSession) -> Dict[str, Any]:
        """
        Startup recovery sweeper for interrupted/zombie jobs:
        When backend restarts or container redeploys while jobs were in progress:
        - If document chunks already exist in PostgreSQL -> mark completed.
        - If physical file is still present on disk -> re-queue for background completion.
        - If physical file is missing and no chunks exist -> mark failed with clear restart recovery message.
        """
        logger.info("Running startup recovery sweep for interrupted document processing jobs...")
        stmt = (
            select(DocumentJob)
            .where(DocumentJob.status.in_(["pending", "processing"]))
            .order_by(DocumentJob.created_at.asc())
        )
        res = await db.execute(stmt)
        interrupted_jobs = list(res.scalars().all())

        recovered_count = 0
        requeued_count = 0
        failed_count = 0

        for job in interrupted_jobs:
            doc_stmt = select(Document).where(Document.id == job.document_id)
            doc_res = await db.execute(doc_stmt)
            document = doc_res.scalar_one_or_none()

            if not document:
                job.status = "failed"
                job.stage = "failed"
                job.error_message = "Document deleted."
                job.completed_at = datetime.now(timezone.utc)
                failed_count += 1
                continue

            # Check if document has chunks in PostgreSQL
            chunk_stmt = select(DocumentChunk).where(DocumentChunk.document_id == document.id).limit(1)
            chunk_res = await db.execute(chunk_stmt)
            has_chunks = chunk_res.scalar_one_or_none() is not None

            if has_chunks:
                # Chunks were already saved before restart: mark complete
                job.status = "completed"
                job.stage = "completed"
                job.progress = 100
                job.completed_at = datetime.now(timezone.utc)
                job_meta = dict(job.metadata_ or {})
                job_meta["recovered_on_startup"] = True
                job.metadata_ = job_meta

                document.status = "processed"
                recovered_count += 1
            else:
                # Check if physical binary is on disk
                full_file_path = storage_service.get_full_path(document.storage_path)
                if full_file_path.exists() and full_file_path.is_file():
                    # Re-queue job for completion
                    if job.retry_count < job.max_retries:
                        job.status = "pending"
                        job.stage = "queued"
                        job.progress = 0
                        job.retry_count += 1
                        job_meta = dict(job.metadata_ or {})
                        job_meta["requeued_on_startup"] = True
                        job.metadata_ = job_meta

                        self.dispatch_background_job(job.id)
                        requeued_count += 1
                    else:
                        job.status = "failed"
                        job.stage = "failed"
                        job.error_message = "Interrupted by container restart and retry limit exceeded."
                        job.completed_at = datetime.now(timezone.utc)
                        document.status = "failed"
                        failed_count += 1
                else:
                    # Ephemeral binary was lost on container reset before chunking
                    missing_msg = (
                        "Document processing was interrupted by container restart and original file is missing "
                        "from ephemeral disk. Please re-upload the document."
                    )
                    job.status = "failed"
                    job.stage = "failed"
                    job.error_message = missing_msg
                    job.completed_at = datetime.now(timezone.utc)
                    job_meta = dict(job.metadata_ or {})
                    job_meta["missing_binary_on_ephemeral_disk"] = True
                    job.metadata_ = job_meta

                    document.status = "failed"
                    d_meta = dict(document.metadata_ or {})
                    d_meta["error"] = missing_msg
                    document.metadata_ = d_meta
                    failed_count += 1

        await db.commit()
        report = {
            "total_interrupted": len(interrupted_jobs),
            "recovered_completed": recovered_count,
            "requeued": requeued_count,
            "marked_failed": failed_count,
        }
        logger.info(f"Startup job recovery complete: {report}")
        return report


# Singleton instance
document_job_service = DocumentJobService()
