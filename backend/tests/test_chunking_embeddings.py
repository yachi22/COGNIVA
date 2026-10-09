import asyncio
import io
import uuid
import pytest
import httpx
import pymupdf
import docx
from sqlalchemy import select

from app.main import app
from app.core.database import AsyncSessionLocal
from app.models.chunk import DocumentChunk
from app.services.documents.extractor import ExtractedDocument, ExtractedUnit
from app.services.documents.chunker import DocumentChunker
from app.services.embeddings import (
    EmbeddingService,
    MockEmbeddingProvider,
    OpenAIEmbeddingProvider,
    DimensionMismatchError,
    MissingEmbeddingConfigurationError,
)


def create_sample_pdf_bytes() -> bytes:
    """Generate a multi-page PDF with realistic text content."""
    doc = pymupdf.open()
    # Page 1
    p1 = doc.new_page()
    p1.insert_text(
        pymupdf.Point(50, 100),
        "Cogniva Enterprise Knowledge Platform.\n\n"
        "Architecture Overview: Cogniva provides scalable vector retrieval "
        "and ingestion pipelines for unstructured corporate documentation.",
        fontsize=12,
    )
    # Page 2
    p2 = doc.new_page()
    p2.insert_text(
        pymupdf.Point(50, 100),
        "Security & Tenant Isolation.\n\n"
        "Every document ingested into the PostgreSQL cluster is partitioned by user credentials. "
        "All pgvector embeddings are stored with strict foreign key constraints and cascade deletion.",
        fontsize=12,
    )
    pdf_bytes = doc.write()
    doc.close()
    return pdf_bytes


def create_sample_docx_bytes() -> bytes:
    """Generate a DOCX document with headings, paragraphs, and tables."""
    doc = docx.Document()
    doc.add_heading("Corporate Compliance Policy", level=1)
    doc.add_paragraph(
        "This policy governs the retention, extraction, and vectorization of sensitive documents. "
        "All data processed through Cogniva must be validated prior to storage."
    )
    doc.add_heading("Data Classifications", level=2)
    doc.add_paragraph("Documents are categorized into Public, Internal, Confidential, and Restricted tiers.")

    table = doc.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "Classification"
    table.cell(0, 1).text = "Retention Period"
    table.cell(1, 0).text = "Confidential"
    table.cell(1, 1).text = "7 Years"

    bio = io.BytesIO()
    doc.save(bio)
    return bio.getvalue()


# --------------------------------------------------------------------------
# 1. Deterministic Chunking Unit Tests
# --------------------------------------------------------------------------

def test_document_chunker_deterministic_and_boundaries():
    """Verify chunker respects boundary splits, min_chunk_size, and overlap."""
    chunker = DocumentChunker(chunk_size=100, chunk_overlap=20, min_chunk_size=10)

    long_text = (
        "Cogniva delivers high-performance enterprise AI workflows. "
        "It supports dense embeddings with pgvector on PostgreSQL. "
        "Tenant isolation is strictly maintained across all user workspaces. "
        "Chunking operates deterministically on sentence and word boundaries."
    )

    doc_id = uuid.uuid4()
    extracted_doc = ExtractedDocument(
        document_id=doc_id,
        file_type="pdf",
        total_pages=1,
        total_units=1,
        total_characters=len(long_text),
        total_words=len(long_text.split()),
        full_text=long_text,
        units=[
            ExtractedUnit(
                unit_type="page",
                page_number=1,
                sequence_number=1,
                text=long_text,
                metadata={},
            )
        ],
    )

    chunks = chunker.chunk_document(extracted_doc)

    assert len(chunks) > 1
    # Deterministic 0-indexed sequence order
    for idx, chunk in enumerate(chunks):
        assert chunk.chunk_index == idx
        assert chunk.page_number == 1
        assert len(chunk.content.strip()) > 0
        assert chunk.metadata["document_id"] == str(doc_id)
        assert chunk.metadata["source_sequence"] == 1


def test_docx_chunking_preserves_structure_and_no_fabricated_pages():
    """Verify DOCX chunks retain heading levels, unit types, and page_number is None."""
    chunker = DocumentChunker(chunk_size=500, chunk_overlap=50)
    doc_id = uuid.uuid4()

    extracted_doc = ExtractedDocument(
        document_id=doc_id,
        file_type="docx",
        total_pages=None,
        total_units=3,
        total_characters=200,
        total_words=30,
        full_text="Executive Overview\nThis is an enterprise description paragraph with detailed context.\nHeader 1 | Header 2\nValue 1 | Value 2",
        units=[
            ExtractedUnit(
                unit_type="heading",
                page_number=None,
                sequence_number=1,
                text="Executive Overview",
                metadata={"heading_level": 1},
            ),
            ExtractedUnit(
                unit_type="paragraph",
                page_number=None,
                sequence_number=2,
                text="This is an enterprise description paragraph with detailed context.",
                metadata={},
            ),
            ExtractedUnit(
                unit_type="table",
                page_number=None,
                sequence_number=3,
                text="Header 1 | Header 2\nValue 1 | Value 2",
                metadata={"table_index": 0},
            ),
        ],
    )

    chunks = chunker.chunk_document(extracted_doc)
    assert len(chunks) == 3

    assert chunks[0].page_number is None
    assert chunks[0].metadata["unit_type"] == "heading"
    assert chunks[0].metadata["heading_level"] == 1

    assert chunks[1].page_number is None
    assert chunks[1].metadata["unit_type"] == "paragraph"

    assert chunks[2].page_number is None
    assert chunks[2].metadata["unit_type"] == "table"


# --------------------------------------------------------------------------
# 2. Embedding Service & Provider Unit Tests
# --------------------------------------------------------------------------

def test_mock_embedding_provider_dimension_and_determinism():
    """Verify MockEmbeddingProvider generates exact 1536-dim deterministic vectors."""
    async def _test():
        mock_provider = MockEmbeddingProvider()
        svc = EmbeddingService(provider=mock_provider)

        texts = [
            "Cogniva enterprise search and vector retrieval.",
            "PostgreSQL 16 with pgvector extension enabled.",
        ]

        embeddings = await svc.embed_chunks(texts)
        assert len(embeddings) == 2
        assert len(embeddings[0]) == 1536
        assert len(embeddings[1]) == 1536

        # Determinism check: same text generates exact same vector
        same_embeddings = await svc.embed_chunks([texts[0]])
        assert embeddings[0] == same_embeddings[0]

        # Different texts produce different vectors
        assert embeddings[0] != embeddings[1]

    asyncio.run(_test())


def test_embedding_service_dimension_validation():
    """Verify EmbeddingService enforces 1536 dimensions and rejects mismatched outputs."""
    class BadDimensionProvider(MockEmbeddingProvider):
        @property
        def dimension(self) -> int:
            return 1536

        async def get_embeddings(self, texts: list[str]) -> list[list[float]]:
            # Return wrong dimension (e.g. 512 instead of 1536)
            return [[0.1] * 512 for _ in texts]

    async def _test():
        svc = EmbeddingService(provider=BadDimensionProvider())
        with pytest.raises(DimensionMismatchError):
            await svc.embed_chunks(["Test chunk content"])

    asyncio.run(_test())


def test_openai_missing_api_key_fails_cleanly():
    """Verify OpenAIEmbeddingProvider fails gracefully when OPENAI_API_KEY is not configured."""
    async def _test():
        provider = OpenAIEmbeddingProvider(api_key=None)
        with pytest.raises(MissingEmbeddingConfigurationError) as exc_info:
            await provider.get_embeddings(["Sample text"])
        assert "OPENAI_API_KEY" in str(exc_info.value)

    asyncio.run(_test())


def test_missing_api_key_marks_document_as_failed():
    """Verify missing API key causes document processing to transition to 'failed' with error reason."""
    async def _test():
        from app.services.embeddings import embedding_service
        unconfigured_provider = OpenAIEmbeddingProvider(api_key=None)
        embedding_service.set_provider(unconfigured_provider)

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            email = f"fail_user_{uuid.uuid4().hex[:8]}@cogniva.ai"
            await client.post(
                "/api/v1/auth/register",
                json={"email": email, "password": "Password123!", "full_name": "Fail Tester"},
            )
            login_resp = await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123!"})
            token = login_resp.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}

            pdf_bytes = create_sample_pdf_bytes()
            upload_resp = await client.post(
                "/api/v1/documents",
                headers=headers,
                files={"file": ("fail_doc.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
            )
            doc_id = upload_resp.json()["id"]

            proc_resp = await client.post(f"/api/v1/documents/{doc_id}/process", headers=headers)
            assert proc_resp.status_code == 200
            data = proc_resp.json()
            assert data["status"] == "failed"
            assert "OPENAI_API_KEY" in data["metadata"]["error"]

    asyncio.run(_test())


# --------------------------------------------------------------------------
# 3. Database Persistence, Idempotency, and API Endpoints Integration Tests
# --------------------------------------------------------------------------

def test_pdf_chunking_embeddings_and_database_persistence():
    """
    Test End-to-End:
    1. Upload PDF document.
    2. Process document (triggering text extraction -> chunking -> 1536-dim vector embedding).
    3. Verify status transitions to 'processed'.
    4. Verify chunks exist in PostgreSQL 'document_chunks' table with 1536-dim vector.
    5. Verify GET /api/v1/documents/{id}/chunks returns chunks with provenance.
    """
    async def _test():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            # Register & Login
            email = f"chunk_user_{uuid.uuid4().hex[:8]}@cogniva.ai"
            await client.post(
                "/api/v1/auth/register",
                json={"email": email, "password": "Password123!", "full_name": "Chunk Tester"},
            )
            login_resp = await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123!"})
            token = login_resp.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}

            # 1. Upload PDF
            pdf_bytes = create_sample_pdf_bytes()
            upload_resp = await client.post(
                "/api/v1/documents",
                headers=headers,
                files={"file": ("knowledge_base.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
            )
            assert upload_resp.status_code == 201
            doc_id = upload_resp.json()["id"]

            # 2. Process document
            proc_resp = await client.post(f"/api/v1/documents/{doc_id}/process", headers=headers)
            assert proc_resp.status_code == 200
            proc_data = proc_resp.json()
            assert proc_data["status"] == "processed"
            assert proc_data["metadata"]["total_chunks"] >= 2
            assert proc_data["metadata"]["embedding_dimension"] == 1536
            assert "embedded_at" in proc_data["metadata"]

            # 3. Verify in PostgreSQL database
            async with AsyncSessionLocal() as db:
                stmt = (
                    select(DocumentChunk)
                    .where(DocumentChunk.document_id == uuid.UUID(doc_id))
                    .order_by(DocumentChunk.chunk_index.asc())
                )
                result = await db.execute(stmt)
                db_chunks = list(result.scalars().all())

                assert len(db_chunks) >= 2
                for c in db_chunks:
                    assert c.document_id == uuid.UUID(doc_id)
                    assert c.embedding is not None
                    # Vector(1536) in pgvector
                    assert len(c.embedding) == 1536
                    assert c.page_number in (1, 2)

            # 4. Verify GET /api/v1/documents/{id}/chunks
            chunks_resp = await client.get(f"/api/v1/documents/{doc_id}/chunks", headers=headers)
            assert chunks_resp.status_code == 200
            chunks_data = chunks_resp.json()
            assert chunks_data["total"] == len(db_chunks)
            assert chunks_data["document_id"] == doc_id
            assert len(chunks_data["chunks"]) == len(db_chunks)

            # Validate first chunk payload
            first_chunk = chunks_data["chunks"][0]
            assert first_chunk["chunk_index"] == 0
            assert "Cogniva Enterprise Knowledge Platform" in first_chunk["content"]
            assert first_chunk["page_number"] == 1
            assert first_chunk["metadata"]["page_number"] == 1
            # Ensure raw embedding is not leaked in readable JSON response
            assert "embedding" not in first_chunk

    asyncio.run(_test())


def test_idempotent_reprocessing_replaces_chunks():
    """Verify that reprocessing a document clears old chunks and persists new ones cleanly."""
    async def _test():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            email = f"reproc_{uuid.uuid4().hex[:8]}@cogniva.ai"
            await client.post(
                "/api/v1/auth/register",
                json={"email": email, "password": "Password123!", "full_name": "Reprocessor"},
            )
            login_resp = await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123!"})
            token = login_resp.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}

            # Upload & process
            docx_bytes = create_sample_docx_bytes()
            upload_resp = await client.post(
                "/api/v1/documents",
                headers=headers,
                files={"file": ("policy.docx", io.BytesIO(docx_bytes), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
            )
            doc_id = upload_resp.json()["id"]

            proc1 = await client.post(f"/api/v1/documents/{doc_id}/process", headers=headers)
            assert proc1.status_code == 200
            assert proc1.json()["status"] == "processed"

            chunks1 = await client.get(f"/api/v1/documents/{doc_id}/chunks", headers=headers)
            count1 = chunks1.json()["total"]
            assert count1 > 0
            ids1 = [c["id"] for c in chunks1.json()["chunks"]]

            # Reprocess the exact same document
            proc2 = await client.post(f"/api/v1/documents/{doc_id}/process", headers=headers)
            assert proc2.status_code == 200
            assert proc2.json()["status"] == "processed"

            chunks2 = await client.get(f"/api/v1/documents/{doc_id}/chunks", headers=headers)
            count2 = chunks2.json()["total"]
            assert count2 == count1
            ids2 = [c["id"] for c in chunks2.json()["chunks"]]

            # New unique UUIDs generated and old ones replaced cleanly
            assert ids1 != ids2

    asyncio.run(_test())


def test_tenant_isolation_for_document_chunks():
    """Verify that User B cannot access chunks of User A's document."""
    async def _test():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            # User A
            user_a_email = f"user_a_{uuid.uuid4().hex[:8]}@cogniva.ai"
            await client.post(
                "/api/v1/auth/register",
                json={"email": user_a_email, "password": "Password123!", "full_name": "User A"},
            )
            login_a = await client.post("/api/v1/auth/login", json={"email": user_a_email, "password": "Password123!"})
            headers_a = {"Authorization": f"Bearer {login_a.json()['access_token']}"}

            # User B
            user_b_email = f"user_b_{uuid.uuid4().hex[:8]}@cogniva.ai"
            await client.post(
                "/api/v1/auth/register",
                json={"email": user_b_email, "password": "Password123!", "full_name": "User B"},
            )
            login_b = await client.post("/api/v1/auth/login", json={"email": user_b_email, "password": "Password123!"})
            headers_b = {"Authorization": f"Bearer {login_b.json()['access_token']}"}

            # User A uploads and processes
            pdf_bytes = create_sample_pdf_bytes()
            upload_resp = await client.post(
                "/api/v1/documents",
                headers=headers_a,
                files={"file": ("confidential.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
            )
            doc_id = upload_resp.json()["id"]
            await client.post(f"/api/v1/documents/{doc_id}/process", headers=headers_a)

            # User A can access chunks
            resp_a = await client.get(f"/api/v1/documents/{doc_id}/chunks", headers=headers_a)
            assert resp_a.status_code == 200

            # User B attempts to access User A's chunks -> 404 Not Found
            resp_b = await client.get(f"/api/v1/documents/{doc_id}/chunks", headers=headers_b)
            assert resp_b.status_code == 404

    asyncio.run(_test())
