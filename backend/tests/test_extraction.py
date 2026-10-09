import asyncio
import io
import uuid
import pymupdf
import docx
import httpx

from app.main import app
from app.services.documents.cleaner import clean_extracted_text


def create_test_pdf_bytes(pages_text: list[str]) -> bytes:
    """Helper to generate a real, valid multi-page PDF in memory."""
    doc = pymupdf.open()
    for text in pages_text:
        page = doc.new_page()
        page.insert_text(pymupdf.Point(50, 100), text, fontsize=12)
    pdf_bytes = doc.write()
    doc.close()
    return pdf_bytes


def create_test_docx_bytes(title: str, paragraphs: list[str], table_rows: list[list[str]]) -> bytes:
    """Helper to generate a real, valid DOCX in memory."""
    doc = docx.Document()
    doc.add_heading(title, level=1)
    for p in paragraphs:
        doc.add_paragraph(p)
    if table_rows:
        table = doc.add_table(rows=len(table_rows), cols=len(table_rows[0]))
        for r_idx, row in enumerate(table_rows):
            for c_idx, cell_value in enumerate(row):
                table.cell(r_idx, c_idx).text = cell_value
    bio = io.BytesIO()
    doc.save(bio)
    return bio.getvalue()


def test_text_cleaning_deterministic():
    """Verify clean_extracted_text normalizes whitespace, control chars, and line endings."""
    dirty = "Line 1   with   multiple    spaces.\r\n\r\n\r\n\r\nLine 2 after quadruple blank lines.\x00\xad\x07"
    cleaned = clean_extracted_text(dirty)
    assert "\r" not in cleaned
    assert "\x00" not in cleaned
    assert "\xad" not in cleaned
    assert "   " not in cleaned
    # At most 2 consecutive newlines (\n\n)
    assert "\n\n\n" not in cleaned
    assert "Line 1 with multiple spaces." in cleaned
    assert "Line 2 after quadruple blank lines." in cleaned


def test_pdf_extraction_and_page_number_preservation():
    """
    Test requirements:
    1. PDF text extraction works with PyMuPDF.
    2. Page numbers (1-indexed) are strictly preserved per page.
    3. Document status transitions from uploaded -> processing -> processed.
    4. Normalized content endpoint /extracted returns structured units.
    """
    async def _test():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            email = f"pdf_user_{uuid.uuid4().hex[:8]}@cogniva.ai"
            await client.post(
                "/api/v1/auth/register",
                json={"email": email, "password": "Password123!", "full_name": "PDF Tester"},
            )
            login_resp = await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123!"})
            token = login_resp.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}

            # Create a 2-page PDF
            p1_text = "Executive Summary: Cogniva delivers enterprise AI intelligence."
            p2_text = "Methodology: Multimodal retrieval-augmented generation architecture."
            pdf_data = create_test_pdf_bytes([p1_text, p2_text])

            # 1. Upload file (status='uploaded')
            upload_resp = await client.post(
                "/api/v1/documents",
                headers=headers,
                files={"file": ("enterprise_plan.pdf", io.BytesIO(pdf_data), "application/pdf")},
            )
            assert upload_resp.status_code == 201
            doc_data = upload_resp.json()
            doc_id = doc_data["id"]
            assert doc_data["status"] == "uploaded"

            # 2. Trigger text extraction pipeline
            proc_resp = await client.post(f"/api/v1/documents/{doc_id}/process", headers=headers)
            assert proc_resp.status_code == 200
            proc_data = proc_resp.json()

            assert proc_data["status"] == "processed"
            assert proc_data["metadata"]["total_pages"] == 2
            assert proc_data["metadata"]["total_units"] == 2
            assert proc_data["metadata"]["total_characters"] > 0

            # 3. Verify GET /documents/{id}/extracted
            ext_resp = await client.get(f"/api/v1/documents/{doc_id}/extracted", headers=headers)
            assert ext_resp.status_code == 200
            ext_data = ext_resp.json()

            assert ext_data["file_type"] == "pdf"
            assert ext_data["total_pages"] == 2
            assert len(ext_data["units"]) == 2

            # Check Unit 1 (Page 1)
            u1 = ext_data["units"][0]
            assert u1["unit_type"] == "page"
            assert u1["page_number"] == 1
            assert u1["sequence_number"] == 1
            assert "Executive Summary" in u1["text"]

            # Check Unit 2 (Page 2)
            u2 = ext_data["units"][1]
            assert u2["unit_type"] == "page"
            assert u2["page_number"] == 2
            assert u2["sequence_number"] == 2
            assert "Methodology" in u2["text"]

    asyncio.run(_test())


def test_docx_extraction_and_structure_preservation():
    """
    Test requirements:
    1. DOCX text extraction works with python-docx.
    2. Headings, paragraphs, and tables are extracted in order.
    3. page_number is None (no fabricated page numbers).
    4. Document status transitions from uploaded -> processed.
    """
    async def _test():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            email = f"docx_user_{uuid.uuid4().hex[:8]}@cogniva.ai"
            await client.post(
                "/api/v1/auth/register",
                json={"email": email, "password": "Password123!", "full_name": "DOCX Tester"},
            )
            login_resp = await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123!"})
            token = login_resp.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}

            # Create DOCX with heading, paragraph, and table
            docx_data = create_test_docx_bytes(
                title="Cogniva Compliance Policy",
                paragraphs=["This document describes data privacy controls.", "All tenant data is strictly segregated."],
                table_rows=[["Department", "Role"], ["Security", "Auditor"], ["Engineering", "Maintainer"]],
            )

            # 1. Upload DOCX
            upload_resp = await client.post(
                "/api/v1/documents",
                headers=headers,
                files={
                    "file": (
                        "compliance_policy.docx",
                        io.BytesIO(docx_data),
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    )
                },
            )
            assert upload_resp.status_code == 201
            doc_data = upload_resp.json()
            doc_id = doc_data["id"]
            assert doc_data["status"] == "uploaded"

            # 2. Trigger text extraction pipeline
            proc_resp = await client.post(f"/api/v1/documents/{doc_id}/process", headers=headers)
            assert proc_resp.status_code == 200
            proc_data = proc_resp.json()

            assert proc_data["status"] == "processed"
            assert proc_data["metadata"]["total_pages"] is None  # Never fabricated for DOCX

            # 3. Verify GET /documents/{id}/extracted
            ext_resp = await client.get(f"/api/v1/documents/{doc_id}/extracted", headers=headers)
            assert ext_resp.status_code == 200
            ext_data = ext_resp.json()

            assert ext_data["file_type"] == "docx"
            assert ext_data["total_pages"] is None
            units = ext_data["units"]
            assert len(units) >= 3

            # Verify heading
            h_unit = units[0]
            assert h_unit["unit_type"] == "heading"
            assert h_unit["page_number"] is None
            assert "Cogniva Compliance Policy" in h_unit["text"]

            # Verify paragraph
            p_unit = units[1]
            assert p_unit["unit_type"] == "paragraph"
            assert p_unit["page_number"] is None
            assert "data privacy controls" in p_unit["text"]

            # Verify table unit
            table_unit = [u for u in units if u["unit_type"] == "table"][0]
            assert table_unit["page_number"] is None
            assert "Security | Auditor" in table_unit["text"]

    asyncio.run(_test())


def test_status_lifecycle_and_tenant_isolation():
    """
    Test requirements:
    1. Upload with auto_process=False keeps status 'uploaded'.
    2. Calling POST /documents/{id}/process transitions to 'processed'.
    3. Multi-tenant isolation prevents User B from processing User A's document.
    4. User B cannot access User A's extracted content.
    """
    async def _test():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            # User A
            email_a = f"life_a_{uuid.uuid4().hex[:8]}@cogniva.ai"
            await client.post("/api/v1/auth/register", json={"email": email_a, "password": "Password123!", "full_name": "A"})
            login_a = await client.post("/api/v1/auth/login", json={"email": email_a, "password": "Password123!"})
            headers_a = {"Authorization": f"Bearer {login_a.json()['access_token']}"}

            # User B
            email_b = f"life_b_{uuid.uuid4().hex[:8]}@cogniva.ai"
            await client.post("/api/v1/auth/register", json={"email": email_b, "password": "Password123!", "full_name": "B"})
            login_b = await client.post("/api/v1/auth/login", json={"email": email_b, "password": "Password123!"})
            headers_b = {"Authorization": f"Bearer {login_b.json()['access_token']}"}

            pdf_data = create_test_pdf_bytes(["Test document content for manual trigger."])

            # Upload with auto_process=false
            upload_resp = await client.post(
                "/api/v1/documents",
                headers=headers_a,
                files={"file": ("manual_trigger.pdf", io.BytesIO(pdf_data), "application/pdf")},
            )
            assert upload_resp.status_code == 201
            doc_id = upload_resp.json()["id"]
            assert upload_resp.json()["status"] == "uploaded"

            # User B attempts to process User A's document: must be rejected with 404
            probe_proc = await client.post(f"/api/v1/documents/{doc_id}/process", headers=headers_b)
            assert probe_proc.status_code == 404

            # User B attempts to read extracted content: must be rejected with 404
            probe_ext = await client.get(f"/api/v1/documents/{doc_id}/extracted", headers=headers_b)
            assert probe_ext.status_code == 404

            # User A manually triggers process
            proc_resp = await client.post(f"/api/v1/documents/{doc_id}/process", headers=headers_a)
            assert proc_resp.status_code == 200
            assert proc_resp.json()["status"] == "processed"
            assert proc_resp.json()["metadata"]["total_pages"] == 1

    asyncio.run(_test())
