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
from app.models.document import Document
from app.services.embeddings import (
    embedding_service,
    MockEmbeddingProvider,
    OpenAIEmbeddingProvider,
    EmbeddingError,
)


def create_pdf_with_sections(pages_content: list[str]) -> bytes:
    """Helper to generate a real PDF in memory with distinct content per page."""
    doc = pymupdf.open()
    for text in pages_content:
        page = doc.new_page()
        page.insert_text(pymupdf.Point(50, 100), text, fontsize=12)
    pdf_bytes = doc.write()
    doc.close()
    return pdf_bytes


def create_docx_with_sections(headings_and_paras: list[tuple[str, str]]) -> bytes:
    """Helper to generate a real DOCX in memory with headings and paragraphs."""
    doc = docx.Document()
    for heading, para in headings_and_paras:
        doc.add_heading(heading, level=1)
        doc.add_paragraph(para)
    bio = io.BytesIO()
    doc.save(bio)
    return bio.getvalue()


# --------------------------------------------------------------------------
# 1. Query Embedding Unit Tests
# --------------------------------------------------------------------------

def test_query_embedding_generation_and_dimension():
    """Verify query embedding is generated with exact 1536 dimensions and empty query is rejected."""
    async def _test():
        query = "How does Cogniva perform vector retrieval in PostgreSQL?"
        vec = await embedding_service.embed_query(query)
        assert isinstance(vec, list)
        assert len(vec) == 1536
        assert all(isinstance(x, float) for x in vec)

        with pytest.raises(EmbeddingError):
            await embedding_service.embed_query("   ")

    asyncio.run(_test())


# --------------------------------------------------------------------------
# 2. Semantic Search Ranking, Top-K & Threshold Integration Tests
# --------------------------------------------------------------------------

def test_relevant_chunk_ranks_above_irrelevant_chunk():
    """Verify semantic vector retrieval ranks relevant content higher than unrelated content."""
    async def _test():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            email = f"rank_user_{uuid.uuid4().hex[:8]}@cogniva.ai"
            await client.post(
                "/api/v1/auth/register",
                json={"email": email, "password": "Password123!", "full_name": "Ranking Tester"},
            )
            login = await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123!"})
            headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

            # Document with 2 distinct sections
            p1 = "PostgreSQL pgvector extension enables scalable vector similarity indexing and cosine distance searches."
            p2 = "The classic recipe for chocolate chip cookies requires flour, softened butter, brown sugar, eggs, and baking soda."
            pdf_data = create_pdf_with_sections([p1, p2])

            upload = await client.post(
                "/api/v1/documents",
                headers=headers,
                files={"file": ("topics.pdf", io.BytesIO(pdf_data), "application/pdf")},
            )
            doc_id = upload.json()["id"]
            await client.post(f"/api/v1/documents/{doc_id}/process", headers=headers)

            # Query about pgvector databases
            search_resp = await client.post(
                "/api/v1/retrieval/search",
                headers=headers,
                json={"query": "PostgreSQL vector similarity indexing with pgvector", "top_k": 2},
            )
            assert search_resp.status_code == 200
            data = search_resp.json()
            assert data["total"] == 2
            results = data["results"]

            # Top result must be the pgvector chunk
            top_result = results[0]
            second_result = results[1]
            assert "pgvector extension" in top_result["content"]
            assert top_result["similarity_score"] > second_result["similarity_score"]
            assert top_result["cosine_distance"] < second_result["cosine_distance"]
            assert top_result["page_number"] == 1
            assert second_result["page_number"] == 2

    asyncio.run(_test())


def test_top_k_behavior_and_ordering():
    """Verify top_k bounds results correctly and ordering is strictly descending by similarity."""
    async def _test():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            email = f"topk_user_{uuid.uuid4().hex[:8]}@cogniva.ai"
            await client.post(
                "/api/v1/auth/register",
                json={"email": email, "password": "Password123!", "full_name": "TopK Tester"},
            )
            login = await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123!"})
            headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

            # 4 distinct pages
            pages = [
                "Machine Learning pipelines automate data preprocessing, model training, and continuous deployment.",
                "Deep Learning architectures utilize multilayer neural networks with backpropagation optimization.",
                "Database indexing improves query latency using B-trees, hash indexes, and generalized inverted indexes.",
                "Cloud infrastructure orchestration leverages containerization technologies such as Docker and Kubernetes.",
            ]
            pdf_data = create_pdf_with_sections(pages)
            upload = await client.post(
                "/api/v1/documents",
                headers=headers,
                files={"file": ("tech_manual.pdf", io.BytesIO(pdf_data), "application/pdf")},
            )
            doc_id = upload.json()["id"]
            await client.post(f"/api/v1/documents/{doc_id}/process", headers=headers)

            # Top K = 2
            resp_2 = await client.post(
                "/api/v1/retrieval/search",
                headers=headers,
                json={"query": "Neural networks and machine learning models", "top_k": 2},
            )
            assert resp_2.status_code == 200
            assert resp_2.json()["total"] == 2

            # Top K = 3
            resp_3 = await client.post(
                "/api/v1/retrieval/search",
                headers=headers,
                json={"query": "Neural networks and machine learning models", "top_k": 3},
            )
            assert resp_3.status_code == 200
            res3 = resp_3.json()["results"]
            assert len(res3) == 3

            # Verify strictly ordered descending by similarity_score
            for i in range(len(res3) - 1):
                assert res3[i]["similarity_score"] >= res3[i + 1]["similarity_score"]
                assert res3[i]["cosine_distance"] <= res3[i + 1]["cosine_distance"]

    asyncio.run(_test())


def test_empty_results_and_similarity_threshold():
    """Verify empty result when user has no documents or when threshold filters out all chunks."""
    async def _test():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            email = f"empty_user_{uuid.uuid4().hex[:8]}@cogniva.ai"
            await client.post(
                "/api/v1/auth/register",
                json={"email": email, "password": "Password123!", "full_name": "Empty Tester"},
            )
            login = await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123!"})
            headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

            # 1. No documents uploaded yet
            resp = await client.post(
                "/api/v1/retrieval/search",
                headers=headers,
                json={"query": "Where is the documentation?", "top_k": 5},
            )
            assert resp.status_code == 200
            assert resp.json() == {"query": "Where is the documentation?", "total": 0, "results": []}

            # 2. Upload and process a document
            pdf_data = create_pdf_with_sections(["Corporate security policy guidelines."])
            upload = await client.post(
                "/api/v1/documents",
                headers=headers,
                files={"file": ("sec.pdf", io.BytesIO(pdf_data), "application/pdf")},
            )
            doc_id = upload.json()["id"]
            await client.post(f"/api/v1/documents/{doc_id}/process", headers=headers)

            # 3. Request with an impossibly high min_similarity threshold
            resp_threshold = await client.post(
                "/api/v1/retrieval/search",
                headers=headers,
                json={"query": "Baking cookies and culinary recipes", "top_k": 5, "min_similarity": 0.999},
            )
            assert resp_threshold.status_code == 200
            assert resp_threshold.json()["total"] == 0
            assert resp_threshold.json()["results"] == []

    asyncio.run(_test())


# --------------------------------------------------------------------------
# 3. Document Scoping & Tenant Isolation Tests
# --------------------------------------------------------------------------

def test_document_scoping_and_isolation():
    """Verify search scoped to a specific document only returns chunks from that document."""
    async def _test():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            email = f"scope_user_{uuid.uuid4().hex[:8]}@cogniva.ai"
            await client.post(
                "/api/v1/auth/register",
                json={"email": email, "password": "Password123!", "full_name": "Scope Tester"},
            )
            login = await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123!"})
            headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

            # Upload Document A (Artificial Intelligence)
            pdf_a = create_pdf_with_sections(["Artificial intelligence transforms enterprise decision-making."])
            doc_a = (await client.post(
                "/api/v1/documents",
                headers=headers,
                files={"file": ("ai_doc.pdf", io.BytesIO(pdf_a), "application/pdf")},
            )).json()["id"]
            await client.post(f"/api/v1/documents/{doc_a}/process", headers=headers)

            # Upload Document B (Aerospace Propulsion)
            pdf_b = create_pdf_with_sections(["Aerospace propulsion systems utilize turbofan jet engines."])
            doc_b = (await client.post(
                "/api/v1/documents",
                headers=headers,
                files={"file": ("aero_doc.pdf", io.BytesIO(pdf_b), "application/pdf")},
            )).json()["id"]
            await client.post(f"/api/v1/documents/{doc_b}/process", headers=headers)

            # Search scoped to Doc A
            search_a = await client.post(
                "/api/v1/retrieval/search",
                headers=headers,
                json={"query": "engineering systems", "document_id": doc_a, "top_k": 5},
            )
            assert search_a.status_code == 200
            for item in search_a.json()["results"]:
                assert item["document_id"] == doc_a
                assert item["document_filename"].startswith("ai_doc") or "ai_doc" in item["document_original_filename"]

            # Search scoped to Doc B
            search_b = await client.post(
                "/api/v1/retrieval/search",
                headers=headers,
                json={"query": "engineering systems", "document_id": doc_b, "top_k": 5},
            )
            assert search_b.status_code == 200
            for item in search_b.json()["results"]:
                assert item["document_id"] == doc_b
                assert "aero_doc" in item["document_original_filename"]

    asyncio.run(_test())


def test_tenant_isolation_cross_user():
    """Verify User B cannot retrieve User A's chunks globally or by specifying User A's document_id."""
    async def _test():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            # User A
            email_a = f"tenant_a_{uuid.uuid4().hex[:8]}@cogniva.ai"
            await client.post("/api/v1/auth/register", json={"email": email_a, "password": "Password123!", "full_name": "Tenant A"})
            login_a = await client.post("/api/v1/auth/login", json={"email": email_a, "password": "Password123!"})
            headers_a = {"Authorization": f"Bearer {login_a.json()['access_token']}"}

            # User B
            email_b = f"tenant_b_{uuid.uuid4().hex[:8]}@cogniva.ai"
            await client.post("/api/v1/auth/register", json={"email": email_b, "password": "Password123!", "full_name": "Tenant B"})
            login_b = await client.post("/api/v1/auth/login", json={"email": email_b, "password": "Password123!"})
            headers_b = {"Authorization": f"Bearer {login_b.json()['access_token']}"}

            # User A uploads and processes private document
            pdf_a = create_pdf_with_sections(["Top Secret Financial Forecast for Q4 2026."])
            upload_a = await client.post(
                "/api/v1/documents",
                headers=headers_a,
                files={"file": ("secret_finances.pdf", io.BytesIO(pdf_a), "application/pdf")},
            )
            doc_id_a = upload_a.json()["id"]
            await client.post(f"/api/v1/documents/{doc_id_a}/process", headers=headers_a)

            # User A can retrieve it
            search_a = await client.post(
                "/api/v1/retrieval/search",
                headers=headers_a,
                json={"query": "Financial Forecast Q4", "top_k": 5},
            )
            assert search_a.status_code == 200
            assert search_a.json()["total"] == 1

            # User B attempts user-wide search -> 0 results
            search_b_global = await client.post(
                "/api/v1/retrieval/search",
                headers=headers_b,
                json={"query": "Financial Forecast Q4", "top_k": 5},
            )
            assert search_b_global.status_code == 200
            assert search_b_global.json()["total"] == 0

            # User B attempts scoped search with User A's document_id -> 404 Not Found (no leakage)
            search_b_targeted = await client.post(
                "/api/v1/retrieval/search",
                headers=headers_b,
                json={"query": "Financial Forecast Q4", "document_id": doc_id_a, "top_k": 5},
            )
            assert search_b_targeted.status_code == 404
            assert search_b_targeted.json()["detail"] == "Document not found."

    asyncio.run(_test())


# --------------------------------------------------------------------------
# 4. Validation and Error Handling Tests
# --------------------------------------------------------------------------

def test_request_validation_top_k_and_document_id():
    """Verify rejection of invalid top_k, empty queries, and malformed document IDs."""
    async def _test():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            email = f"valid_{uuid.uuid4().hex[:8]}@cogniva.ai"
            await client.post("/api/v1/auth/register", json={"email": email, "password": "Password123!", "full_name": "Valid Tester"})
            login = await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123!"})
            headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

            # 1. Empty query
            resp_empty = await client.post(
                "/api/v1/retrieval/search",
                headers=headers,
                json={"query": "", "top_k": 5},
            )
            assert resp_empty.status_code == 422

            # 2. top_k = 0 (below ge=1)
            resp_zero = await client.post(
                "/api/v1/retrieval/search",
                headers=headers,
                json={"query": "Test", "top_k": 0},
            )
            assert resp_zero.status_code == 422

            # 3. top_k > 20 (above le=20)
            resp_huge = await client.post(
                "/api/v1/retrieval/search",
                headers=headers,
                json={"query": "Test", "top_k": 25},
            )
            assert resp_huge.status_code == 422

            # 4. Malformed document_id string
            resp_bad_uuid = await client.post(
                "/api/v1/retrieval/search",
                headers=headers,
                json={"query": "Test", "document_id": "not-a-uuid"},
            )
            assert resp_bad_uuid.status_code == 422

            # 5. Non-existent UUID -> 404
            random_uuid = str(uuid.uuid4())
            resp_not_found = await client.post(
                "/api/v1/retrieval/search",
                headers=headers,
                json={"query": "Test", "document_id": random_uuid},
            )
            assert resp_not_found.status_code == 404

    asyncio.run(_test())


def test_embedding_provider_failure_returns_clean_application_error():
    """Verify that if embedding provider fails, API returns clean error response instead of crashing."""
    async def _test():
        # Inject unconfigured OpenAI provider
        unconfigured_provider = OpenAIEmbeddingProvider(api_key=None)
        embedding_service.set_provider(unconfigured_provider)

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            email = f"fail_ret_{uuid.uuid4().hex[:8]}@cogniva.ai"
            await client.post("/api/v1/auth/register", json={"email": email, "password": "Password123!", "full_name": "Fail Tester"})
            login = await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123!"})
            headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

            resp = await client.post(
                "/api/v1/retrieval/search",
                headers=headers,
                json={"query": "Search without api key", "top_k": 5},
            )
            assert resp.status_code == 503
            assert "OPENAI_API_KEY" in resp.json()["detail"]

    asyncio.run(_test())


def test_docx_provenance_page_number_is_none():
    """Verify DOCX document chunks preserve page_number=None during retrieval."""
    async def _test():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            email = f"docx_ret_{uuid.uuid4().hex[:8]}@cogniva.ai"
            await client.post("/api/v1/auth/register", json={"email": email, "password": "Password123!", "full_name": "DOCX Ret Tester"})
            login = await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123!"})
            headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

            docx_data = create_docx_with_sections([
                ("Human Resources Handbook", "All employee benefits are managed through the global corporate portal."),
            ])
            upload = await client.post(
                "/api/v1/documents",
                headers=headers,
                files={"file": ("hr_handbook.docx", io.BytesIO(docx_data), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
            )
            doc_id = upload.json()["id"]
            await client.post(f"/api/v1/documents/{doc_id}/process", headers=headers)

            search = await client.post(
                "/api/v1/retrieval/search",
                headers=headers,
                json={"query": "employee benefits handbook", "document_id": doc_id},
            )
            assert search.status_code == 200
            res = search.json()["results"]
            assert len(res) > 0
            # DOCX page_number must be None (no fabricated page numbers)
            assert res[0]["page_number"] is None
            assert res[0]["document_original_filename"] == "hr_handbook.docx"
            assert "embedding" not in res[0]

    asyncio.run(_test())
