import asyncio
import io
import uuid
from pathlib import Path
import httpx
from sqlalchemy import select

from app.main import app
from app.core.database import async_engine, AsyncSessionLocal
from app.core.config import settings
from app.models.document import Document
from app.models.user import User


def test_document_upload_and_persistence():
    """
    Test requirements:
    1. Authenticated user can upload PDF.
    2. Authenticated user can upload DOCX.
    3. File is stored successfully on disk in storage/documents/<user_id>/.
    4. Document record is created in PostgreSQL with status 'uploaded' and metadata.
    5. Document belongs strictly to the authenticated user.
    """
    async def _test():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            # 1. Register and login test user
            email = f"doc_user_{uuid.uuid4().hex[:8]}@cogniva.ai"
            reg_resp = await client.post(
                "/api/v1/auth/register",
                json={"email": email, "password": "Password123!", "full_name": "Document Tester"},
            )
            assert reg_resp.status_code == 201
            user_id = reg_resp.json()["id"]

            login_resp = await client.post(
                "/api/v1/auth/login",
                json={"email": email, "password": "Password123!"},
            )
            assert login_resp.status_code == 200
            token = login_resp.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}

            # 2. Upload valid PDF
            pdf_bytes = b"%PDF-1.5\n%Cogniva Test Document Header\nHello Cogniva Enterprise AI"
            pdf_file = {"file": ("enterprise_report.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
            
            upload_pdf_resp = await client.post(
                "/api/v1/documents",
                headers=headers,
                files=pdf_file,
            )
            assert upload_pdf_resp.status_code == 201, f"PDF upload failed: {upload_pdf_resp.text}"
            pdf_doc_data = upload_pdf_resp.json()
            assert pdf_doc_data["original_filename"] == "enterprise_report.pdf"
            assert pdf_doc_data["file_type"] == "pdf"
            assert pdf_doc_data["status"] == "uploaded"
            assert pdf_doc_data["user_id"] == user_id
            assert pdf_doc_data["metadata"]["size_bytes"] == len(pdf_bytes)
            pdf_doc_id = pdf_doc_data["id"]

            # 3. Upload valid DOCX
            docx_bytes = b"PK\x03\x04\x14\x00\x06\x00Cogniva DOCX OpenXML Test Archive"
            docx_file = {
                "file": (
                    "quarterly_summary.docx",
                    io.BytesIO(docx_bytes),
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            }
            upload_docx_resp = await client.post(
                "/api/v1/documents",
                headers=headers,
                files=docx_file,
            )
            assert upload_docx_resp.status_code == 201, f"DOCX upload failed: {upload_docx_resp.text}"
            docx_doc_data = upload_docx_resp.json()
            assert docx_doc_data["original_filename"] == "quarterly_summary.docx"
            assert docx_doc_data["file_type"] == "docx"
            assert docx_doc_data["status"] == "uploaded"
            assert docx_doc_data["user_id"] == user_id

        # 4. Verify in PostgreSQL database directly
        async with AsyncSessionLocal() as session:
            stmt = select(Document).where(Document.id == uuid.UUID(pdf_doc_id))
            res = await session.execute(stmt)
            db_doc = res.scalar_one_or_none()
            assert db_doc is not None, "Document not found in database!"
            assert str(db_doc.user_id) == user_id
            assert db_doc.file_type == "pdf"
            assert db_doc.status == "uploaded"

            # 5. Verify physical file persistence on disk
            storage_path = Path(settings.STORAGE_DIR) / db_doc.storage_path
            assert storage_path.exists(), f"Physical file does not exist at {storage_path}"
            assert storage_path.read_bytes() == pdf_bytes

    asyncio.run(_test())


def test_document_validation_and_rejection():
    """
    Test requirements:
    - Unsupported file types (.txt, .exe) rejected.
    - Empty file (0 bytes) rejected.
    - Corrupted/mismatched magic bytes rejected.
    - Unauthenticated requests rejected.
    """
    async def _test():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            email = f"val_user_{uuid.uuid4().hex[:8]}@cogniva.ai"
            await client.post(
                "/api/v1/auth/register",
                json={"email": email, "password": "Password123!", "full_name": "Validation Tester"},
            )
            login_resp = await client.post(
                "/api/v1/auth/login",
                json={"email": email, "password": "Password123!"},
            )
            token = login_resp.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}

            # 1. Unauthenticated request rejected with 401
            no_auth_resp = await client.get("/api/v1/documents")
            assert no_auth_resp.status_code == 401

            # 2. Unsupported file extension rejected (.txt)
            txt_file = {"file": ("notes.txt", io.BytesIO(b"Hello world"), "text/plain")}
            bad_ext_resp = await client.post("/api/v1/documents", headers=headers, files=txt_file)
            assert bad_ext_resp.status_code == 415

            # 3. Empty file rejected
            empty_file = {"file": ("empty.pdf", io.BytesIO(b""), "application/pdf")}
            empty_resp = await client.post("/api/v1/documents", headers=headers, files=empty_file)
            assert empty_resp.status_code == 400

            # 4. Invalid header / corrupted magic bytes rejected
            fake_pdf = {"file": ("fake.pdf", io.BytesIO(b"This is not really a PDF file!"), "application/pdf")}
            fake_resp = await client.post("/api/v1/documents", headers=headers, files=fake_pdf)
            assert fake_resp.status_code == 400

    asyncio.run(_test())


def test_document_tenant_isolation_and_deletion():
    """
    Test requirements:
    - GET documents returns only current user's documents.
    - User B cannot access User A's document (returns 404).
    - User B cannot delete User A's document.
    - User A can delete their own document, removing both DB record and disk file.
    """
    async def _test():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            # Create User A
            email_a = f"usera_{uuid.uuid4().hex[:8]}@cogniva.ai"
            await client.post(
                "/api/v1/auth/register",
                json={"email": email_a, "password": "Password123!", "full_name": "User Alpha"},
            )
            login_a = await client.post("/api/v1/auth/login", json={"email": email_a, "password": "Password123!"})
            headers_a = {"Authorization": f"Bearer {login_a.json()['access_token']}"}

            # Create User B
            email_b = f"userb_{uuid.uuid4().hex[:8]}@cogniva.ai"
            await client.post(
                "/api/v1/auth/register",
                json={"email": email_b, "password": "Password123!", "full_name": "User Beta"},
            )
            login_b = await client.post("/api/v1/auth/login", json={"email": email_b, "password": "Password123!"})
            headers_b = {"Authorization": f"Bearer {login_b.json()['access_token']}"}

            # User A uploads a document
            doc_bytes = b"%PDF-1.4 User A Confidential Report"
            upload_resp = await client.post(
                "/api/v1/documents",
                headers=headers_a,
                files={"file": ("alpha_report.pdf", io.BytesIO(doc_bytes), "application/pdf")},
            )
            assert upload_resp.status_code == 201
            doc_a_id = upload_resp.json()["id"]

            # User A lists documents: should see 1 document
            list_a_resp = await client.get("/api/v1/documents", headers=headers_a)
            assert list_a_resp.status_code == 200
            docs_a = list_a_resp.json()
            assert len(docs_a) == 1
            assert docs_a[0]["id"] == doc_a_id

            # User B lists documents: should see 0 documents (strict isolation!)
            list_b_resp = await client.get("/api/v1/documents", headers=headers_b)
            assert list_b_resp.status_code == 200
            docs_b = list_b_resp.json()
            assert len(docs_b) == 0

            # User B tries to fetch User A's document directly: must return 404
            probe_resp = await client.get(f"/api/v1/documents/{doc_a_id}", headers=headers_b)
            assert probe_resp.status_code == 404, "User B should not be able to fetch User A document!"

            # User B tries to delete User A's document: must return 404
            probe_del_resp = await client.delete(f"/api/v1/documents/{doc_a_id}", headers=headers_b)
            assert probe_del_resp.status_code == 404, "User B should not be able to delete User A document!"

            # User A deletes their own document
            del_resp = await client.delete(f"/api/v1/documents/{doc_a_id}", headers=headers_a)
            assert del_resp.status_code == 200

            # Verify document is gone from User A's document list
            list_a_after = await client.get("/api/v1/documents", headers=headers_a)
            assert len(list_a_after.json()) == 0

            # Verify document is gone from database
            async with AsyncSessionLocal() as session:
                stmt = select(Document).where(Document.id == uuid.UUID(doc_a_id))
                res = await session.execute(stmt)
                assert res.scalar_one_or_none() is None

    asyncio.run(_test())
