import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from fastapi.responses import Response, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.document import (
    DocumentResponse,
    DocumentDeleteResponse,
    ExtractedDocumentResponse,
    DocumentChunkResponse,
    DocumentChunkListResponse,
    DocumentChunkDetailResponse,
)
from app.schemas.job import (
    DocumentJobResponse,
    DocumentJobListResponse,
    DocumentJobProgressResponse,
)
from app.services.document_service import document_service
from app.services.job_service import document_job_service

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post(
    "",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload an enterprise document (PDF or DOCX)",
    description="Uploads a PDF or DOCX file, validates format and magic bytes, stores the file securely, registers the document record in PostgreSQL, and processes text extraction.",
)
async def upload_document(
    file: UploadFile = File(..., description="Document file (.pdf or .docx)"),
    auto_process: bool = Query(False, description="Automatically trigger text extraction upon upload"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentResponse:
    """
    Upload document endpoint. Ownership is strictly bound to current_user.
    """
    document = await document_service.upload_document(
        db=db,
        user=current_user,
        file=file,
        auto_process=auto_process,
    )
    return DocumentResponse.model_validate(document)


@router.get(
    "",
    response_model=List[DocumentResponse],
    summary="List authenticated user documents",
    description="Returns metadata for all documents uploaded by the authenticated user. Never exposes files belonging to other users.",
)
async def list_documents(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[DocumentResponse]:
    """
    List user's documents.
    """
    docs = await document_service.get_user_documents(db=db, user_id=current_user.id)
    return [DocumentResponse.model_validate(doc) for doc in docs]


@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
    summary="Get document details",
    description="Returns document metadata if owned by the requesting user. Returns 404 if not found or unauthorized.",
)
async def get_document(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentResponse:
    """
    Retrieve single document metadata with tenant isolation.
    """
    doc = await document_service.get_user_document(
        db=db,
        user_id=current_user.id,
        document_id=document_id,
    )
    return DocumentResponse.model_validate(doc)


@router.post(
    "/{document_id}/process",
    response_model=DocumentResponse,
    summary="Trigger text extraction pipeline for a document",
    description="Executes text extraction, chunking, and vector embedding. Defaults to asynchronous background job processing with stage progress tracking.",
)
async def process_document(
    document_id: uuid.UUID,
    background: bool = Query(True, description="Process asynchronously in background task"),
    force: bool = Query(False, description="Force re-processing if already completed"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentResponse:
    """
    Triggers or retries extraction pipeline for the specified document.
    Enforces strict tenant isolation and prevents duplicate concurrent runs.
    """
    if background:
        job, is_new = await document_job_service.create_or_get_job(
            db=db,
            user_id=current_user.id,
            document_id=document_id,
            force=force,
        )
        if is_new or job.status == "pending":
            document_job_service.dispatch_background_job(job.id)

        doc = await document_service.get_user_document(
            db=db,
            user_id=current_user.id,
            document_id=document_id,
        )
        return DocumentResponse.model_validate(doc)
    else:
        doc = await document_service.process_document(
            db=db,
            user_id=current_user.id,
            document_id=document_id,
        )
        return DocumentResponse.model_validate(doc)


@router.get(
    "/{document_id}/job",
    response_model=DocumentJobResponse,
    summary="Get active or latest background processing job",
    description="Returns live stage (extracting, chunking, embedding, indexing), progress (0-100), retry count, and errors.",
)
async def get_latest_document_job(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentJobResponse:
    """
    Poll live processing job progress with tenant authorization.
    """
    job = await document_job_service.get_latest_job(
        db=db,
        user_id=current_user.id,
        document_id=document_id,
    )
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No processing jobs found for this document."
        )
    return DocumentJobResponse.model_validate(job)


@router.get(
    "/{document_id}/jobs",
    response_model=DocumentJobListResponse,
    summary="List all processing jobs for document",
    description="Returns chronological audit history of all processing runs and retries for the document.",
)
async def list_document_jobs(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentJobListResponse:
    """
    List processing jobs for document with tenant authorization.
    """
    jobs = await document_job_service.get_document_jobs(
        db=db,
        user_id=current_user.id,
        document_id=document_id,
    )
    return DocumentJobListResponse(
        total=len(jobs),
        document_id=document_id,
        jobs=[DocumentJobResponse.model_validate(j) for j in jobs],
    )


@router.post(
    "/{document_id}/jobs/{job_id}/retry",
    response_model=DocumentJobResponse,
    summary="Retry a failed background processing job",
    description="Re-queues a failed document processing job with fresh retry budget.",
)
async def retry_document_job(
    document_id: uuid.UUID,
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentJobResponse:
    """
    Manually retries a failed job with tenant isolation.
    """
    job = await document_job_service.retry_job(
        db=db,
        user_id=current_user.id,
        document_id=document_id,
        job_id=job_id,
    )
    return DocumentJobResponse.model_validate(job)


@router.get(
    "/{document_id}/extracted",
    response_model=ExtractedDocumentResponse,
    summary="Get normalized extracted text structure",
    description="Returns the page-aware, cleaned extracted textual structure of a processed document for verification and downstream chunking.",
)
async def get_extracted_content(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ExtractedDocumentResponse:
    """
    Retrieve normalized extracted units and page structure.
    """
    extracted = await document_service.get_extracted_document(
        db=db,
        user_id=current_user.id,
        document_id=document_id,
    )
    return ExtractedDocumentResponse(
        document_id=extracted.document_id,
        file_type=extracted.file_type,
        total_pages=extracted.total_pages,
        total_units=extracted.total_units,
        total_characters=extracted.total_characters,
        total_words=extracted.total_words,
        units=[
            {
                "unit_type": u.unit_type,
                "page_number": u.page_number,
                "sequence_number": u.sequence_number,
                "text": u.text,
                "metadata": u.metadata,
            }
            for u in extracted.units
        ],
        extracted_at=extracted.extracted_at,
    )


@router.get(
    "/{document_id}/chunks",
    response_model=DocumentChunkListResponse,
    summary="Get document chunks with provenance metadata",
    description="Returns all chunked content units and provenance metadata for an ingested document. Excludes raw embedding vectors for readability.",
)
async def get_document_chunks(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentChunkListResponse:
    """
    Retrieve document chunks for the authenticated user's document.
    Enforces strict tenant isolation.
    """
    chunks = await document_service.get_document_chunks(
        db=db,
        user_id=current_user.id,
        document_id=document_id,
    )
    return DocumentChunkListResponse(
        total=len(chunks),
        document_id=document_id,
        chunks=[DocumentChunkResponse.model_validate(c) for c in chunks],
    )


@router.get(
    "/{document_id}/chunks/{chunk_id}",
    response_model=DocumentChunkDetailResponse,
    summary="Get single document chunk for source inspection",
    description="Returns the chunk text and safe provenance metadata for citation inspection. Verifies tenant document ownership and chunk containment.",
)
async def get_document_chunk(
    document_id: uuid.UUID,
    chunk_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentChunkDetailResponse:
    """
    Retrieve single document chunk with tenant ownership verification.
    """
    chunk, doc = await document_service.get_document_chunk(
        db=db,
        user_id=current_user.id,
        document_id=document_id,
        chunk_id=chunk_id,
    )
    return DocumentChunkDetailResponse(
        id=chunk.id,
        document_id=chunk.document_id,
        document_filename=doc.original_filename or doc.filename,
        chunk_index=chunk.chunk_index,
        content=chunk.content,
        page_number=chunk.page_number,
        metadata_=chunk.metadata_,
        created_at=chunk.created_at,
    )


@router.delete(
    "/{document_id}",
    response_model=DocumentDeleteResponse,
    summary="Delete a document",
    description="Deletes document from disk storage and database. Enforces tenant ownership.",
)
async def delete_document(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentDeleteResponse:
    """
    Secure delete endpoint.
    """
    await document_service.delete_user_document(
        db=db,
        user_id=current_user.id,
        document_id=document_id,
    )
    return DocumentDeleteResponse(
        message="Document deleted successfully.",
        id=document_id,
    )


@router.get(
    "/{document_id}/download",
    summary="Download original document binary or recovered text",
    description="Securely downloads the authentic uploaded document binary, redirects to presigned S3/R2 URL, or falls back to reconstructed text from persisted database chunks if the ephemeral binary was purged.",
)
async def download_document(
    document_id: uuid.UUID,
    redirect: bool = Query(True, description="Redirect to presigned S3/R2 URL if available"),
    fallback_text: bool = Query(True, description="Fall back to reconstructed text if original binary is missing on ephemeral disk"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    binary_bytes, filename, content_type, presigned_url, is_reconstructed = (
        await document_service.get_document_download(
            db=db,
            user_id=current_user.id,
            document_id=document_id,
            fallback_text=fallback_text,
        )
    )

    if redirect and presigned_url:
        return RedirectResponse(url=presigned_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)

    safe_name = filename.replace('"', "")
    headers = {
        "Content-Disposition": f'attachment; filename="{safe_name}"',
        "Cache-Control": "private, no-cache, no-store, must-revalidate",
        "X-Cogniva-Recovered": "true" if is_reconstructed else "false",
        "X-Cogniva-Original-Binary-Available": "false" if is_reconstructed else "true",
    }
    return Response(
        content=binary_bytes,
        media_type=content_type,
        headers=headers,
    )


@router.get(
    "/{document_id}/download-url",
    summary="Get presigned download URL or authenticated download path",
    description="Returns signed object URL or secure endpoint route for downloading the document.",
)
async def get_download_url(
    document_id: uuid.UUID,
    fallback_text: bool = Query(True, description="Fall back to reconstructed text if original binary is missing on ephemeral disk"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    binary_bytes, filename, content_type, presigned_url, is_reconstructed = (
        await document_service.get_document_download(
            db=db,
            user_id=current_user.id,
            document_id=document_id,
            fallback_text=fallback_text,
        )
    )

    return {
        "document_id": str(document_id),
        "filename": filename,
        "content_type": content_type,
        "download_url": presigned_url or f"/api/v1/documents/{document_id}/download",
        "is_presigned": presigned_url is not None,
        "expires_in_seconds": 900 if presigned_url else None,
        "is_reconstructed": is_reconstructed,
        "original_binary_available": not is_reconstructed,
    }

