import io
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi import HTTPException, UploadFile, status

from app.models.document import Document
from app.models.chunk import DocumentChunk
from app.models.user import User
from app.services.storage import storage_service, LocalStorageProvider, StorageObjectNotFoundError
from app.services.document_service import DocumentService
from app.services.retrieval_service import RetrievalService
from app.services.summary_service import SummaryService
from app.services.report_service import ReportService
from app.services.extraction_service import ExtractionService
from app.services.documents.extractor import ExtractedDocument, ExtractedUnit


# ---------------------------------------------------------------------------
# 1. Upload Validation and Local Persistence
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_upload_validation_and_local_persistence(tmp_path: Path):
    """
    Verifies that under zero-budget constraints:
    - Files are validated (format and magic bytes).
    - Invalid formats and forged headers are rejected.
    - Files are persisted securely to user-isolated local directories.
    - Tenant isolation is preserved.
    """
    user_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    custom_storage = tmp_path / "zero_budget_storage"
    custom_storage.mkdir()

    from app.services.storage.service import StorageService
    svc = StorageService(base_dir=str(custom_storage))

    # Valid PDF upload
    valid_pdf_content = b"%PDF-1.7\nSample Cogniva Enterprise Document Content"
    upload_file = UploadFile(
        file=io.BytesIO(valid_pdf_content),
        filename="quarterly_report.pdf",
        headers={"content-type": "application/pdf"},
    )

    stored_fn, orig_name, file_type, total_bytes, storage_key, metadata = (
        await svc.save_uploaded_file(file=upload_file, user_id=user_id, document_id=doc_id)
    )

    assert orig_name == "quarterly_report.pdf"
    assert file_type == "pdf"
    assert total_bytes == len(valid_pdf_content)
    assert metadata["storage_provider"] == "local"
    assert metadata["durable"] is False

    # Check that file exists on local disk in user-isolated directory
    saved_path = custom_storage / storage_key
    assert saved_path.exists()
    assert saved_path.read_bytes() == valid_pdf_content

    # Path traversal protection
    user_storage_dir = svc.get_user_storage_dir(user_id)
    assert str(saved_path).startswith(str(user_storage_dir))

    # Reject forged magic bytes
    forged_file = UploadFile(
        file=io.BytesIO(b"NOT_A_PDF_CONTENT"),
        filename="fake.pdf",
    )
    with pytest.raises(HTTPException) as exc:
        await svc.save_uploaded_file(file=forged_file, user_id=user_id)
    assert exc.value.status_code == status.HTTP_400_BAD_REQUEST

    # Reject unsupported executable extension
    exe_file = UploadFile(
        file=io.BytesIO(b"MZ\x90\x00malware"),
        filename="program.exe",
    )
    with pytest.raises(HTTPException) as exc_exe:
        await svc.save_uploaded_file(file=exe_file, user_id=user_id)
    assert exc_exe.value.status_code == status.HTTP_415_UNSUPPORTED_MEDIA_TYPE


# ---------------------------------------------------------------------------
# 2. Downloads: Authentic Binary vs. Recovered Text Fallback
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_download_authentic_binary_when_available(tmp_path: Path):
    """
    When local file exists, get_document_download returns the original authentic binary.
    """
    doc_svc = DocumentService()
    user_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    pdf_bytes = b"%PDF-1.4 Authentic Policy Binary Content"

    # Set up user storage with file
    user_dir = storage_service.get_user_storage_dir(user_id)
    test_file = user_dir / f"{doc_id.hex}.pdf"
    test_file.write_bytes(pdf_bytes)

    mock_doc = MagicMock(spec=Document)
    mock_doc.id = doc_id
    mock_doc.user_id = user_id
    mock_doc.filename = f"{doc_id.hex}.pdf"
    mock_doc.original_filename = "policy.pdf"
    mock_doc.file_type = "pdf"
    mock_doc.storage_path = f"documents/{user_id}/{doc_id.hex}.pdf"
    mock_doc.metadata_ = {"content_type": "application/pdf"}

    mock_db = AsyncMock()
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = mock_doc
    mock_db.execute.return_value = mock_res

    binary_bytes, filename, content_type, presigned_url, is_reconstructed = (
        await doc_svc.get_document_download(db=mock_db, user_id=user_id, document_id=doc_id)
    )

    assert binary_bytes == pdf_bytes
    assert filename == "policy.pdf"
    assert content_type == "application/pdf"
    assert presigned_url is None
    assert is_reconstructed is False

    # Cleanup
    if test_file.exists():
        test_file.unlink()


@pytest.mark.asyncio
async def test_download_recovers_text_when_ephemeral_binary_missing():
    """
    Simulates container reboot: local file is missing from ephemeral disk,
    but chunks are safely persisted in PostgreSQL.
    Verifies that get_document_download reconstructs the text with metadata and provenance.
    """
    doc_svc = DocumentService()
    user_id = uuid.uuid4()
    doc_id = uuid.uuid4()

    mock_doc = MagicMock(spec=Document)
    mock_doc.id = doc_id
    mock_doc.user_id = user_id
    mock_doc.filename = f"{doc_id.hex}.pdf"
    mock_doc.original_filename = "annual_audit.pdf"
    mock_doc.file_type = "pdf"
    mock_doc.status = "processed"
    mock_doc.storage_path = f"documents/{user_id}/nonexistent_{doc_id.hex}.pdf"
    mock_doc.metadata_ = {"content_type": "application/pdf"}
    mock_doc.created_at = datetime.now(timezone.utc)

    # Chunks safely stored in PostgreSQL
    mock_chunk1 = MagicMock(spec=DocumentChunk)
    mock_chunk1.id = uuid.uuid4()
    mock_chunk1.document_id = doc_id
    mock_chunk1.chunk_index = 0
    mock_chunk1.content = "Section 1: Enterprise audit completed with 100% compliance."
    mock_chunk1.page_number = 1
    mock_chunk1.metadata_ = {"unit_type": "page"}

    mock_chunk2 = MagicMock(spec=DocumentChunk)
    mock_chunk2.id = uuid.uuid4()
    mock_chunk2.document_id = doc_id
    mock_chunk2.chunk_index = 1
    mock_chunk2.content = "Section 2: Security recommendations implemented across all clusters."
    mock_chunk2.page_number = 2
    mock_chunk2.metadata_ = {"unit_type": "page"}

    mock_db = AsyncMock()

    def db_execute_side_effect(stmt):
        mock_result = MagicMock()
        stmt_str = str(stmt)
        if "FROM documents" in stmt_str or "documents.id" in stmt_str:
            mock_result.scalar_one_or_none.return_value = mock_doc
            mock_result.scalars.return_value.all.return_value = [mock_doc]
        elif "FROM document_chunks" in stmt_str or "document_chunks.document_id" in stmt_str:
            mock_result.scalars.return_value.all.return_value = [mock_chunk1, mock_chunk2]
        return mock_result

    mock_db.execute.side_effect = db_execute_side_effect

    # 1. Download with fallback_text=True (default): returns recovered text
    recovered_bytes, filename, content_type, presigned_url, is_reconstructed = (
        await doc_svc.get_document_download(
            db=mock_db,
            user_id=user_id,
            document_id=doc_id,
            fallback_text=True,
        )
    )

    assert is_reconstructed is True
    assert filename == "annual_audit_recovered.txt"
    assert "text/plain" in content_type
    assert presigned_url is None

    recovered_text = recovered_bytes.decode("utf-8")
    assert "Cogniva Extracted Content Recovery" in recovered_text
    assert "Section 1: Enterprise audit completed" in recovered_text
    assert "Section 2: Security recommendations implemented" in recovered_text

    # 2. Download with fallback_text=False: raises 404
    with pytest.raises(HTTPException) as exc:
        await doc_svc.get_document_download(
            db=mock_db,
            user_id=user_id,
            document_id=doc_id,
            fallback_text=False,
        )
    assert exc.value.status_code == status.HTTP_404_NOT_FOUND
    assert "not available" in exc.value.detail.lower()


@pytest.mark.asyncio
async def test_download_cross_tenant_denial():
    """
    Verifies that tenant isolation is strictly enforced for downloads.
    An unauthorized user cannot download another user's document or reconstructed text.
    """
    doc_svc = DocumentService()
    owner_id = uuid.uuid4()
    attacker_id = uuid.uuid4()
    doc_id = uuid.uuid4()

    mock_db = AsyncMock()
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = None  # Not found for attacker
    mock_db.execute.return_value = mock_res

    with pytest.raises(HTTPException) as exc:
        await doc_svc.get_document_download(
            db=mock_db,
            user_id=attacker_id,
            document_id=doc_id,
        )
    assert exc.value.status_code == status.HTTP_404_NOT_FOUND


# ---------------------------------------------------------------------------
# 3. Extraction & Processing Resilience
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_process_document_resilience_when_binary_missing():
    """
    Verifies that when ephemeral container reboots:
    - If document already has chunks in PostgreSQL, process_document preserves
      the 'processed' status, chunks, and records missing_binary_on_ephemeral_disk=True.
    - It does NOT crash with FileNotFoundError or destroy the database record.
    """
    doc_svc = DocumentService()
    user_id = uuid.uuid4()
    doc_id = uuid.uuid4()

    mock_doc = MagicMock(spec=Document)
    mock_doc.id = doc_id
    mock_doc.user_id = user_id
    mock_doc.filename = f"{doc_id.hex}.pdf"
    mock_doc.original_filename = "important_contract.pdf"
    mock_doc.file_type = "pdf"
    mock_doc.status = "processed"
    mock_doc.storage_path = f"documents/{user_id}/missing_{doc_id.hex}.pdf"
    mock_doc.metadata_ = {"total_chunks": 3}

    mock_chunk = MagicMock(spec=DocumentChunk)
    mock_chunk.id = uuid.uuid4()
    mock_chunk.document_id = doc_id
    mock_chunk.chunk_index = 0
    mock_chunk.content = "Contract clause content"

    mock_db = AsyncMock()

    def db_execute_side_effect(stmt):
        mock_result = MagicMock()
        stmt_str = str(stmt)
        if "FROM documents" in stmt_str or "documents.id" in stmt_str:
            mock_result.scalar_one_or_none.return_value = mock_doc
        elif "FROM document_chunks" in stmt_str:
            mock_result.scalars.return_value.all.return_value = [mock_chunk]
        return mock_result

    mock_db.execute.side_effect = db_execute_side_effect

    processed_doc = await doc_svc.process_document(
        db=mock_db,
        user_id=user_id,
        document_id=doc_id,
    )

    assert processed_doc.status == "processed"
    assert mock_doc.metadata_["missing_binary_on_ephemeral_disk"] is True
    assert mock_doc.metadata_["recovered_from_chunks"] is True
    mock_db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_get_extracted_document_reconstructs_from_chunks_when_json_missing(tmp_path: Path):
    """
    Verifies get_extracted_document transparently reconstructs normalized units
    and re-caches to local disk when the ephemeral JSON file is absent.
    """
    doc_svc = DocumentService()
    user_id = uuid.uuid4()
    doc_id = uuid.uuid4()

    mock_doc = MagicMock(spec=Document)
    mock_doc.id = doc_id
    mock_doc.user_id = user_id
    mock_doc.file_type = "pdf"
    mock_doc.status = "processed"
    mock_doc.storage_path = f"documents/{user_id}/doc_{doc_id.hex}.pdf"
    mock_doc.metadata_ = {"extracted_path": f"documents/{user_id}/nonexistent_extracted.json"}
    mock_doc.created_at = datetime.now(timezone.utc)

    mock_chunk = MagicMock(spec=DocumentChunk)
    mock_chunk.id = uuid.uuid4()
    mock_chunk.document_id = doc_id
    mock_chunk.chunk_index = 0
    mock_chunk.content = "Paragraph 1 extracted text."
    mock_chunk.page_number = 1
    mock_chunk.metadata_ = {"unit_type": "paragraph"}

    mock_db = AsyncMock()

    def db_execute_side_effect(stmt):
        mock_result = MagicMock()
        stmt_str = str(stmt)
        if "FROM documents" in stmt_str:
            mock_result.scalar_one_or_none.return_value = mock_doc
        elif "FROM document_chunks" in stmt_str:
            mock_result.scalars.return_value.all.return_value = [mock_chunk]
        return mock_result

    mock_db.execute.side_effect = db_execute_side_effect

    extracted = await doc_svc.get_extracted_document(
        db=mock_db,
        user_id=user_id,
        document_id=doc_id,
    )

    assert extracted.document_id == doc_id
    assert extracted.total_units == 1
    assert "Paragraph 1 extracted text." in extracted.full_text
    assert extracted.units[0].page_number == 1


# ---------------------------------------------------------------------------
# 4. Retrieval Functions Even When Physical Binary is Missing
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_retrieval_functions_when_binary_missing():
    """
    Verifies that semantic vector retrieval operates entirely on PostgreSQL
    chunks and embeddings, requiring zero physical disk files.
    """
    retrieval_svc = RetrievalService()
    user_id = uuid.uuid4()
    doc_id = uuid.uuid4()

    mock_doc = MagicMock(spec=Document)
    mock_doc.id = doc_id
    mock_doc.user_id = user_id
    mock_doc.status = "processed"
    mock_doc.original_filename = "compliance_guide.pdf"

    mock_chunk = MagicMock(spec=DocumentChunk)
    mock_chunk.id = uuid.uuid4()
    mock_chunk.document_id = doc_id
    mock_chunk.chunk_index = 0
    mock_chunk.content = "Cogniva zero-budget storage leverages PostgreSQL for durable chunks."
    mock_chunk.page_number = 1
    mock_chunk.metadata_ = {"heading": "Overview"}
    mock_chunk.embedding = [0.1] * 1536

    from collections import namedtuple
    Row = namedtuple("Row", [
        "chunk_id", "document_id", "chunk_index", "content", "page_number",
        "metadata", "document_filename", "document_original_filename",
        "cosine_distance", "similarity_score"
    ])
    mock_row = Row(
        chunk_id=mock_chunk.id,
        document_id=doc_id,
        chunk_index=0,
        content=mock_chunk.content,
        page_number=1,
        metadata={"heading": "Overview"},
        document_filename="compliance_guide.pdf",
        document_original_filename="compliance_guide.pdf",
        cosine_distance=0.15,
        similarity_score=0.85,
    )

    mock_db = AsyncMock()

    def db_execute_side_effect(stmt):
        mock_result = MagicMock()
        stmt_str = str(stmt)
        if "FROM documents" in stmt_str and "documents.id" in stmt_str:
            mock_result.scalar_one_or_none.return_value = mock_doc
        else:
            mock_result.all.return_value = [mock_row]
        return mock_result

    mock_db.execute.side_effect = db_execute_side_effect

    res = await retrieval_svc.search(
        db=mock_db,
        user_id=user_id,
        query="PostgreSQL durable chunks",
        top_k=5,
        document_id=doc_id,
    )

    assert res.total == 1
    assert "PostgreSQL for durable chunks" in res.results[0].content
    assert res.results[0].document_filename == "compliance_guide.pdf"

    # Cross-tenant scoping denied
    attacker_id = uuid.uuid4()
    def attacker_db_side_effect(stmt):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        return mock_result
    mock_db.execute.side_effect = attacker_db_side_effect

    with pytest.raises(HTTPException) as exc:
        await retrieval_svc.search(
            db=mock_db,
            user_id=attacker_id,
            query="test",
            document_id=doc_id,
        )
    assert exc.value.status_code == status.HTTP_404_NOT_FOUND


# ---------------------------------------------------------------------------
# 5. Summaries Function Even When Physical Binary is Missing
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_summaries_function_when_binary_missing():
    """
    Verifies that document summarization reads chunks from PostgreSQL and
    synthesizes concise and comprehensive summaries without needing the original file on disk.
    """
    summary_svc = SummaryService()
    user_id = uuid.uuid4()
    doc_id = uuid.uuid4()

    mock_doc = MagicMock(spec=Document)
    mock_doc.id = doc_id
    mock_doc.user_id = user_id
    mock_doc.status = "processed"
    mock_doc.original_filename = "enterprise_strategy.docx"
    mock_doc.metadata_ = {}

    mock_chunk = MagicMock(spec=DocumentChunk)
    mock_chunk.id = uuid.uuid4()
    mock_chunk.document_id = doc_id
    mock_chunk.chunk_index = 0
    mock_chunk.content = "Enterprise Strategy: Migrate compute to containerized workloads with durable database state."
    mock_chunk.page_number = None

    mock_db = AsyncMock()

    def db_execute_side_effect(stmt):
        mock_result = MagicMock()
        stmt_str = str(stmt)
        if "FROM documents" in stmt_str:
            mock_result.scalar_one_or_none.return_value = mock_doc
        elif "FROM document_chunks" in stmt_str:
            mock_result.scalars.return_value.all.return_value = [mock_chunk]
        return mock_result

    mock_db.execute.side_effect = db_execute_side_effect

    summary_result = await summary_svc.get_document_summary(
        db=mock_db,
        user_id=user_id,
        document_id=doc_id,
        mode="concise",
    )

    assert summary_result["document_id"] == str(doc_id)
    assert summary_result["document_filename"] == "enterprise_strategy.docx"
    assert "summary" in summary_result
    assert len(summary_result["key_takeaways"]) >= 1

    # Cross-tenant denial
    attacker_id = uuid.uuid4()
    def attacker_side_effect(stmt):
        r = MagicMock()
        r.scalar_one_or_none.return_value = None
        return r
    mock_db.execute.side_effect = attacker_side_effect

    with pytest.raises(HTTPException) as exc:
        await summary_svc.get_document_summary(
            db=mock_db,
            user_id=attacker_id,
            document_id=doc_id,
        )
    assert exc.value.status_code == status.HTTP_404_NOT_FOUND


# ---------------------------------------------------------------------------
# 6. Reports and Structured Extraction Function When Binary is Missing
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_reports_and_extraction_function_when_binary_missing():
    """
    Verifies that ReportService and ExtractionService synthesize evidence-backed
    findings and structured entities purely from persisted PostgreSQL chunks.
    """
    report_svc = ReportService()
    extraction_svc = ExtractionService()
    user_id = uuid.uuid4()
    doc_id = uuid.uuid4()

    mock_doc = MagicMock(spec=Document)
    mock_doc.id = doc_id
    mock_doc.user_id = user_id
    mock_doc.status = "processed"
    mock_doc.original_filename = "technical_spec.pdf"
    mock_doc.metadata_ = {}

    mock_chunk = MagicMock(spec=DocumentChunk)
    mock_chunk.id = uuid.uuid4()
    mock_chunk.document_id = doc_id
    mock_chunk.chunk_index = 0
    mock_chunk.content = (
        "Technical Spec: ElderShield AI incorporates FastAPI backend, React frontend, "
        "and PostgreSQL storage to protect users from malicious phishing links and scams."
    )
    mock_chunk.page_number = 1

    mock_db = AsyncMock()

    def db_execute_side_effect(stmt):
        mock_result = MagicMock()
        stmt_str = str(stmt)
        if "FROM documents" in stmt_str:
            mock_result.scalar_one_or_none.return_value = mock_doc
            mock_result.scalars.return_value.all.return_value = [mock_doc]
        elif "FROM document_chunks" in stmt_str:
            mock_result.scalars.return_value.all.return_value = [mock_chunk]
        return mock_result

    mock_db.execute.side_effect = db_execute_side_effect

    # 1. Report Generation succeeds without disk binary
    report = await report_svc.generate_report(
        db=mock_db,
        user_id=user_id,
        topic="ElderShield AI Security Architecture",
        document_ids=[doc_id],
    )

    assert "report_id" in report
    assert report["documents_count"] == 1
    assert len(report["sources"]) == 1
    assert "technical_spec.pdf" in report["sources"][0]["document_filename"]
    assert report["content_markdown"]

    # 2. Structured Extraction succeeds without disk binary
    extracted_data = await extraction_svc.extract_structured_data(
        db=mock_db,
        user_id=user_id,
        document_id=doc_id,
    )

    assert "data" in extracted_data
    assert "entities" in extracted_data["data"]
    assert "risks" in extracted_data["data"]
    assert "action_items" in extracted_data["data"]

    # 3. Cross-tenant denial for reports
    attacker_id = uuid.uuid4()
    def attacker_side_effect(stmt):
        r = MagicMock()
        r.scalar_one_or_none.return_value = None
        r.scalars.return_value.all.return_value = []
        return r
    mock_db.execute.side_effect = attacker_side_effect

    with pytest.raises(HTTPException) as exc:
        await report_svc.generate_report(
            db=mock_db,
            user_id=attacker_id,
            topic="Security Architecture",
            document_ids=[doc_id],
        )
    assert exc.value.status_code == status.HTTP_404_NOT_FOUND
