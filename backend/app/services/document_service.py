import uuid
import logging
from datetime import datetime, timezone
from typing import List, Optional, Tuple
from fastapi import UploadFile, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.document import Document
from app.models.chunk import DocumentChunk
from app.models.user import User
from app.services.storage import storage_service, StorageObjectNotFoundError
from app.services.documents.extractor import document_extractor, ExtractedDocument, ExtractedUnit, ExtractionError
from app.services.documents.chunker import document_chunker, ChunkData
from app.services.embeddings import (
    embedding_service,
    EmbeddingError,
    MissingEmbeddingConfigurationError,
    DimensionMismatchError,
)

logger = logging.getLogger("cogniva.document_service")


class DocumentService:
    """
    Business logic and database persistence service for document management, text extraction,
    deterministic chunking, and embedding generation.
    Enforces strict user isolation and lifecycle coordination between storage and PostgreSQL.
    """

    async def upload_document(
        self,
        db: AsyncSession,
        user: User,
        file: UploadFile,
        auto_process: bool = False,
    ) -> Document:
        """
        Validates, saves to disk, and persists a Document record in PostgreSQL.
        Optionally executes immediate synchronous text extraction and embedding.
        """
        # Save file securely to user-isolated directory and durable object storage
        doc_id = uuid.uuid4()
        stored_filename, original_name, file_type, total_bytes, relative_path, metadata = (
            await storage_service.save_uploaded_file(file=file, user_id=user.id, document_id=doc_id)
        )

        try:
            document = Document(
                id=doc_id,
                user_id=user.id,
                filename=stored_filename,
                original_filename=original_name,
                file_type=file_type,
                storage_path=relative_path,
                status="uploaded",
                metadata_=metadata,
            )
            db.add(document)
            await db.commit()
            await db.refresh(document)
        except Exception:
            # If database persistence fails, purge the saved file to avoid orphaned storage
            await storage_service.delete_document_completely(user.id, relative_path, metadata)
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to persist document metadata in database."
            )

        # Trigger synchronous processing if requested
        if auto_process:
            document = await self.process_document(db=db, user_id=user.id, document_id=document.id)

        return document

    async def process_document(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        document_id: uuid.UUID
    ) -> Document:
        """
        Executes full document ingestion pipeline:
        1. Text extraction (page-aware)
        2. Extracted JSON persistence
        3. Deterministic chunking with provenance
        4. Dense vector embedding generation (1536-dim)
        5. Idempotent database chunk persistence (document_chunks table)
        6. State transitions: uploaded -> processing -> processed (or failed)
        """
        document = await self.get_user_document(db=db, user_id=user_id, document_id=document_id)

        # 1. Transition to 'processing' and track job
        from app.services.job_service import document_job_service
        job, _ = await document_job_service.create_or_get_job(
            db=db, user_id=user_id, document_id=document_id, force=True
        )
        job.status = "processing"
        job.stage = "extracting"
        job.current_stage = 1
        job.progress = 10
        job.started_at = datetime.now(timezone.utc)

        document.status = "processing"
        doc_meta = dict(document.metadata_ or {})
        doc_meta["active_job_id"] = str(job.id)
        document.metadata_ = doc_meta
        await db.commit()
        await db.refresh(document)

        full_file_path = storage_service.get_full_path(document.storage_path)
        if not full_file_path.exists() or not full_file_path.is_file():
            # Ephemeral container restart: attempt restore from storage provider into local user cache if configured
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

        # Check if physical file is missing after restoration attempt
        if not full_file_path.exists() or not full_file_path.is_file():
            # Check if this document already has chunks persisted in PostgreSQL
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
                job.completed_at = datetime.now(timezone.utc)

                await db.commit()
                await db.refresh(document)
                return document
            else:
                # Document was never processed and original binary is missing from ephemeral disk
                current_metadata = dict(document.metadata_ or {})
                current_metadata["error"] = (
                    "Original document binary was lost during ephemeral container restart before text extraction. "
                    "Please re-upload the document."
                )
                document.status = "failed"
                document.metadata_ = current_metadata

                job.status = "failed"
                job.stage = "failed"
                job.error_message = current_metadata["error"]
                job.completed_at = datetime.now(timezone.utc)

                await db.commit()
                await db.refresh(document)
                return document

        try:
            # 2. Execute extraction
            extracted: ExtractedDocument = document_extractor.extract(
                file_path=full_file_path,
                file_type=document.file_type,
                document_id=document.id,
            )

            # 3. Save extracted artifact in user's isolated storage
            extracted_path = storage_service.save_extracted_json(
                user_id=user_id,
                relative_storage_path=document.storage_path,
                data=extracted.model_dump(mode="json"),
            )

            # 4. Execute deterministic chunking
            chunks: List[ChunkData] = document_chunker.chunk_document(extracted)

            # 5. Generate embeddings for chunks
            embeddings: List[List[float]] = []
            if chunks:
                chunk_texts = [c.content for c in chunks]
                embeddings = await embedding_service.embed_chunks(chunk_texts)

            # 6. Idempotently replace existing chunks for this document
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

            # 7. Transition to 'processed' and record metrics in metadata_
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
            })
            current_metadata.pop("error", None)

            document.status = "processed"
            document.metadata_ = current_metadata

            job.status = "completed"
            job.stage = "completed"
            job.progress = 100
            job.completed_at = datetime.now(timezone.utc)
            job.error_message = None

            await db.commit()
            await db.refresh(document)
            return document

        except Exception as e:
            logger.error(f"Processing failed for document {document_id}: {str(e)}", exc_info=True)
            # Rollback uncommitted transactions cleanly
            await db.rollback()
            # Reload document in fresh transaction state
            document = await self.get_user_document(db=db, user_id=user_id, document_id=document_id)
            current_metadata = dict(document.metadata_ or {})
            if isinstance(e, (ExtractionError, EmbeddingError, MissingEmbeddingConfigurationError, DimensionMismatchError)):
                current_metadata["error"] = str(e)
            else:
                current_metadata["error"] = f"Document processing failed: {str(e)}"
            document.status = "failed"
            document.metadata_ = current_metadata

            # Reload job and mark failed
            job = await document_job_service.get_latest_job(db=db, user_id=user_id, document_id=document_id)
            if job:
                job.status = "failed"
                job.stage = "failed"
                job.error_message = current_metadata["error"]
                job.completed_at = datetime.now(timezone.utc)

            await db.commit()
            await db.refresh(document)
            return document

    async def get_extracted_document(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        document_id: uuid.UUID
    ) -> ExtractedDocument:
        """
        Retrieves the normalized extracted document structure for an authenticated user.
        """
        document = await self.get_user_document(db=db, user_id=user_id, document_id=document_id)

        if document.status != "processed":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Document has not been processed yet. Current status: {document.status}"
            )

        # 1. Attempt loading from user's storage path if present
        extracted_path = (document.metadata_ or {}).get("extracted_path")
        if extracted_path:
            data = storage_service.load_extracted_json(user_id=user_id, relative_json_path=extracted_path)
            if data:
                return ExtractedDocument(**data)

        # 2. Resilient fallback: reconstruct normalized units from persisted database chunks
        stmt = (
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document.id)
            .order_by(DocumentChunk.chunk_index.asc())
        )
        result = await db.execute(stmt)
        chunks = list(result.scalars().all())

        if chunks:
            units: List[ExtractedUnit] = []
            full_text_parts: List[str] = []
            for c in chunks:
                meta = dict(c.metadata_ or {})
                units.append(
                    ExtractedUnit(
                        unit_type=meta.get("unit_type", "paragraph"),
                        page_number=c.page_number,
                        sequence_number=c.chunk_index + 1,
                        text=c.content,
                        metadata=meta,
                    )
                )
                full_text_parts.append(c.content)

            full_text = "\n\n".join(full_text_parts)
            pages = [c.page_number for c in chunks if c.page_number is not None]
            total_pages = max(pages) if pages else (1 if document.file_type == "pdf" else None)

            extracted_doc = ExtractedDocument(
                document_id=document.id,
                file_type=document.file_type,
                units=units,
                total_pages=total_pages,
                total_units=len(units),
                total_characters=sum(len(u.text) for u in units),
                total_words=sum(len(u.text.split()) for u in units),
                full_text=full_text,
                extracted_at=document.created_at or datetime.now(timezone.utc),
            )

            # Re-cache JSON locally if user storage directory exists so subsequent reads are instant
            try:
                storage_service.save_extracted_json(
                    user_id=user_id,
                    relative_storage_path=document.storage_path,
                    data=extracted_doc.model_dump(mode="json"),
                )
            except Exception:
                pass

            return extracted_doc

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Extracted content artifact not found in storage or database."
        )

    async def get_user_documents(
        self,
        db: AsyncSession,
        user_id: uuid.UUID
    ) -> List[Document]:
        """
        Retrieves all documents belonging strictly to the specified authenticated user.
        """
        stmt = (
            select(Document)
            .where(Document.user_id == user_id)
            .order_by(Document.created_at.desc())
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_user_document(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        document_id: uuid.UUID
    ) -> Document:
        """
        Retrieves a specific document. Returns 404 if the document does not exist
        or does not belong to the requesting user.
        """
        stmt = (
            select(Document)
            .where(Document.id == document_id, Document.user_id == user_id)
        )
        result = await db.execute(stmt)
        document = result.scalar_one_or_none()

        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found."
            )
        return document

    async def get_document_chunks(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        document_id: uuid.UUID,
    ) -> List[DocumentChunk]:
        """
        Retrieves all chunks for a document belonging strictly to the specified authenticated user.
        Ordered deterministically by chunk_index ascending.
        """
        # Ensure document exists and belongs to user (raises 404 if unauthorized or not found)
        document = await self.get_user_document(db=db, user_id=user_id, document_id=document_id)

        stmt = (
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document.id)
            .order_by(DocumentChunk.chunk_index.asc())
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_document_chunk(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        document_id: uuid.UUID,
        chunk_id: uuid.UUID,
    ) -> Tuple[DocumentChunk, Document]:
        """
        Retrieves a single chunk verifying ownership of the parent document
        by the authenticated user and association of the chunk with that document.
        Raises 404 if the document is not owned by the user or if the chunk does not belong to the document.
        """
        document = await self.get_user_document(db=db, user_id=user_id, document_id=document_id)

        stmt = (
            select(DocumentChunk)
            .where(
                DocumentChunk.id == chunk_id,
                DocumentChunk.document_id == document.id,
            )
        )
        result = await db.execute(stmt)
        chunk = result.scalar_one_or_none()
        if not chunk:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chunk not found in document.",
            )
        return chunk, document

    async def delete_user_document(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        document_id: uuid.UUID
    ) -> bool:
        """
        Deletes a document from both durable cloud storage, local disk, and database.
        Strictly enforces tenant ownership.
        """
        document = await self.get_user_document(db=db, user_id=user_id, document_id=document_id)

        # Remove physical file and any extracted JSON from disk and durable object storage
        await storage_service.delete_document_completely(
            user_id=user_id,
            storage_path=document.storage_path,
            metadata_=document.metadata_,
        )

        # Delete database record
        await db.delete(document)
        await db.commit()
        return True

    async def get_document_download(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        document_id: uuid.UUID,
        fallback_text: bool = True,
    ) -> Tuple[bytes, str, str, Optional[str], bool]:
        """
        Retrieves authentic document binary and optional presigned download URL.
        If original binary is missing (e.g. after ephemeral container restart),
        recovers full textual content from PostgreSQL chunks when fallback_text=True.
        Enforces tenant isolation.
        Returns:
            Tuple of (binary_bytes, filename, content_type, presigned_url, is_reconstructed)
        """
        document = await self.get_user_document(db=db, user_id=user_id, document_id=document_id)
        meta = dict(document.metadata_ or {})
        content_type = meta.get("content_type", f"application/{document.file_type}")
        original_name = document.original_filename or document.filename

        # Generate presigned URL if durable S3/R2 provider is active
        presigned_url = await storage_service.generate_download_url(
            user_id=user_id,
            storage_path=document.storage_path,
            original_filename=original_name,
            metadata_=meta,
        )

        # Retrieve bytes (from local cache or fetched from S3)
        try:
            binary_bytes = await storage_service.get_document_bytes(
                user_id=user_id,
                storage_path=document.storage_path,
                metadata_=meta,
            )
            return binary_bytes, original_name, content_type, presigned_url, False
        except StorageObjectNotFoundError:
            if not fallback_text:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Original document binary is not available. (File was not durably stored before ephemeral container reset)."
                )

            # Resilient recovery: reconstruct text from persisted database chunks
            try:
                extracted = await self.get_extracted_document(db=db, user_id=user_id, document_id=document_id)
            except HTTPException:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Original document binary and extracted content are not available on this ephemeral instance."
                )

            from pathlib import Path
            header = (
                f"# Cogniva Extracted Content Recovery\n"
                f"# Original Document: {original_name}\n"
                f"# Note: The original uploaded file binary is unavailable on this ephemeral container instance.\n"
                f"# This content was recovered from persisted PostgreSQL chunks and vector embeddings.\n"
                f"# Total Pages: {extracted.total_pages or 'N/A'} | Total Units: {extracted.total_units} | Total Words: {extracted.total_words}\n\n"
            )
            text_content = header + extracted.full_text
            text_bytes = text_content.encode("utf-8")
            stem = Path(original_name).stem
            recovered_filename = f"{stem}_recovered.txt"
            return text_bytes, recovered_filename, "text/plain; charset=utf-8", None, True


# Singleton instance
document_service = DocumentService()

