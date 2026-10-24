import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.schemas.intelligence import (
    DocumentSummaryRequest,
    DocumentSummaryResponse,
    DocumentComparisonRequest,
    DocumentComparisonResponse,
    StructuredExtractionRequest,
    StructuredExtractionResponse,
    ReportGenerateRequest,
    ReportGenerateResponse,
)
from app.services.summary_service import summary_service
from app.services.comparison_service import comparison_service
from app.services.extraction_service import extraction_service
from app.services.report_service import report_service
from app.services.audit_service import audit_service

router = APIRouter(tags=["intelligence"])


# 1. Document Summarization
@router.post(
    "/documents/{document_id}/summarize",
    response_model=DocumentSummaryResponse,
    status_code=status.HTTP_200_OK,
)
async def summarize_document(
    document_id: uuid.UUID,
    data: DocumentSummaryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    res = await summary_service.get_document_summary(
        db=db,
        user_id=current_user.id,
        document_id=document_id,
        mode=data.mode,
        force_refresh=data.force_refresh,
    )
    await audit_service.log_event(
        db=db,
        action="DOCUMENT_SUMMARIZE",
        resource_type="document",
        user_id=current_user.id,
        resource_id=str(document_id),
        details={"mode": data.mode},
    )
    return res


# 2. Multi-Document Comparison
@router.post(
    "/documents/compare",
    response_model=DocumentComparisonResponse,
    status_code=status.HTTP_200_OK,
)
async def compare_documents(
    data: DocumentComparisonRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    res = await comparison_service.compare_documents(
        db=db,
        user_id=current_user.id,
        document_ids=data.document_ids,
        comparison_prompt=data.comparison_prompt,
    )
    await audit_service.log_event(
        db=db,
        action="DOCUMENT_COMPARE",
        resource_type="documents",
        user_id=current_user.id,
        details={"count": len(data.document_ids)},
    )
    return res


# 3. Structured Data Extraction
@router.post(
    "/documents/{document_id}/extract-structured",
    response_model=StructuredExtractionResponse,
    status_code=status.HTTP_200_OK,
)
async def extract_structured_fields(
    document_id: uuid.UUID,
    data: StructuredExtractionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    res = await extraction_service.extract_structured_data(
        db=db,
        user_id=current_user.id,
        document_id=document_id,
        target_fields=data.target_fields,
    )
    await audit_service.log_event(
        db=db,
        action="DOCUMENT_EXTRACT_STRUCTURED",
        resource_type="document",
        user_id=current_user.id,
        resource_id=str(document_id),
    )
    return res


@router.get(
    "/documents/{document_id}/extract-structured/export.csv",
    status_code=status.HTTP_200_OK,
)
async def export_extracted_csv(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    res = await extraction_service.extract_structured_data(
        db=db,
        user_id=current_user.id,
        document_id=document_id,
    )
    csv_str = extraction_service.export_as_csv(res)
    filename = f"extracted_{res.get('document_filename', 'data')}.csv"
    return Response(
        content=csv_str,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# 4. Report Generation
@router.post(
    "/reports/generate",
    response_model=ReportGenerateResponse,
    status_code=status.HTTP_200_OK,
)
async def generate_research_report(
    data: ReportGenerateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    res = await report_service.generate_report(
        db=db,
        user_id=current_user.id,
        topic=data.topic,
        title=data.title,
        document_ids=data.document_ids,
        collection_id=data.collection_id,
    )
    await audit_service.log_event(
        db=db,
        action="REPORT_GENERATE",
        resource_type="report",
        user_id=current_user.id,
        resource_id=res["report_id"],
        details={"topic": data.topic},
    )
    return res
