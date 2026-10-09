import asyncio
import io
import uuid
import pytest
import httpx
import pymupdf

from app.main import app
from app.services.llm import (
    llm_service,
    MockLLMProvider,
    OpenAILLMProvider,
    INSUFFICIENT_EVIDENCE_RESPONSE,
)
from app.services.conversation_service import generate_deterministic_title


def create_pdf(pages: list[str]) -> bytes:
    doc = pymupdf.open()
    for text in pages:
        page = doc.new_page()
        page.insert_textbox(pymupdf.Rect(50, 50, 550, 750), text, fontsize=12)
    b = doc.write()
    doc.close()
    return b


def test_deterministic_title_generation():
    """Verify deterministic title generation extracts concise phrases without LLM calls."""
    assert generate_deterministic_title("What is the leave policy for interns?") == "Leave policy for interns"
    assert generate_deterministic_title("How do I request remote work approval?") == "Request remote work approval"
    assert generate_deterministic_title("   can you tell me about the 401k match?   ") == "401k match"
    assert generate_deterministic_title("Short query") == "Short query"
    assert generate_deterministic_title("") == "New Conversation"


def test_conversation_crud_and_ordering():
    """Verify conversation creation, listing, retrieval with chronological messages, and deletion."""
    async def _test():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            email = f"conv_user_{uuid.uuid4().hex[:8]}@cogniva.ai"
            await client.post("/api/v1/auth/register", json={"email": email, "password": "Password123!", "full_name": "Conv User"})
            login = await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123!"})
            headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

            # 1. Create conversation
            res = await client.post("/api/v1/conversations", headers=headers, json={"title": "Custom Title"})
            assert res.status_code == 201
            data = res.json()
            conv_id = data["id"]
            assert data["title"] == "Custom Title"
            assert "created_at" in data
            assert "updated_at" in data

            # 2. List conversations
            list_res = await client.post("/api/v1/conversations", headers=headers, json={"title": "Second Conv"})
            assert list_res.status_code == 201

            get_all = await client.get("/api/v1/conversations", headers=headers)
            assert get_all.status_code == 200
            items = get_all.json()["items"]
            assert len(items) >= 2
            # Verify ordering: most recently updated first
            assert items[0]["title"] == "Second Conv"

            # 3. Get detail
            detail_res = await client.get(f"/api/v1/conversations/{conv_id}", headers=headers)
            assert detail_res.status_code == 200
            detail = detail_res.json()
            assert detail["id"] == conv_id
            assert detail["messages"] == []

            # 4. Delete conversation
            del_res = await client.delete(f"/api/v1/conversations/{conv_id}", headers=headers)
            assert del_res.status_code == 204

            # Verify 404 after deletion
            after_del = await client.get(f"/api/v1/conversations/{conv_id}", headers=headers)
            assert after_del.status_code == 404

    asyncio.run(_test())


def test_conversation_tenant_isolation():
    """Verify strict tenant isolation: User B cannot list, view, append, or delete User A conversations."""
    async def _test():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            # User A
            email_a = f"user_a_{uuid.uuid4().hex[:8]}@cogniva.ai"
            await client.post("/api/v1/auth/register", json={"email": email_a, "password": "Password123!", "full_name": "User A"})
            login_a = await client.post("/api/v1/auth/login", json={"email": email_a, "password": "Password123!"})
            headers_a = {"Authorization": f"Bearer {login_a.json()['access_token']}"}

            conv_a = await client.post("/api/v1/conversations", headers=headers_a, json={"title": "User A Private Chat"})
            conv_a_id = conv_a.json()["id"]

            # User B
            email_b = f"user_b_{uuid.uuid4().hex[:8]}@cogniva.ai"
            await client.post("/api/v1/auth/register", json={"email": email_b, "password": "Password123!", "full_name": "User B"})
            login_b = await client.post("/api/v1/auth/login", json={"email": email_b, "password": "Password123!"})
            headers_b = {"Authorization": f"Bearer {login_b.json()['access_token']}"}

            # User B lists conversations -> should NOT include User A's
            list_b = await client.get("/api/v1/conversations", headers=headers_b)
            assert list_b.status_code == 200
            b_ids = [item["id"] for item in list_b.json()["items"]]
            assert conv_a_id not in b_ids

            # User B tries to view User A's conversation -> 404
            get_b = await client.get(f"/api/v1/conversations/{conv_a_id}", headers=headers_b)
            assert get_b.status_code == 404

            # User B tries to delete User A's conversation -> 404
            del_b = await client.delete(f"/api/v1/conversations/{conv_a_id}", headers=headers_b)
            assert del_b.status_code == 404

            # User B tries to query RAG with User A's conversation_id -> 404
            rag_b = await client.post(
                "/api/v1/rag/query",
                headers=headers_b,
                json={"query": "Can I access this?", "conversation_id": conv_a_id},
            )
            assert rag_b.status_code == 404
            assert "not found" in rag_b.json()["detail"].lower()

    asyncio.run(_test())


def test_unauthenticated_conversations_api_rejected():
    """Verify unauthenticated requests are rejected with 401."""
    async def _test():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            random_id = str(uuid.uuid4())
            assert (await client.post("/api/v1/conversations", json={})).status_code == 401
            assert (await client.get("/api/v1/conversations")).status_code == 401
            assert (await client.get(f"/api/v1/conversations/{random_id}")).status_code == 401
            assert (await client.delete(f"/api/v1/conversations/{random_id}")).status_code == 401

    asyncio.run(_test())


def test_rag_query_creates_and_links_conversation():
    """Verify RAG query without conversation_id automatically creates conversation and records turn."""
    async def _test():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            email = f"rag_conv_{uuid.uuid4().hex[:8]}@cogniva.ai"
            await client.post("/api/v1/auth/register", json={"email": email, "password": "Password123!", "full_name": "RAG Conv"})
            login = await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123!"})
            headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

            # Upload document
            pdf_bytes = create_pdf([
                "Cogniva Security Architecture 2026. Data at rest is encrypted using AES-256-GCM. Data in transit uses TLS 1.3.",
            ])
            upload = await client.post(
                "/api/v1/documents",
                headers=headers,
                files={"file": ("security_arch.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
            )
            doc_id = upload.json()["id"]
            await client.post(f"/api/v1/documents/{doc_id}/process", headers=headers)

            # Query without conversation_id
            rag_res = await client.post(
                "/api/v1/rag/query",
                headers=headers,
                json={"query": "What is the data encryption standard at rest?"},
            )
            assert rag_res.status_code == 200
            data = rag_res.json()
            conv_id = data["conversation_id"]
            assert conv_id is not None
            assert data["user_message_id"] is not None
            assert data["assistant_message_id"] is not None
            assert len(data["citations"]) >= 1

            # Fetch conversation detail
            conv_res = await client.get(f"/api/v1/conversations/{conv_id}", headers=headers)
            assert conv_res.status_code == 200
            conv_detail = conv_res.json()
            assert conv_detail["title"] != "New Conversation"
            assert "encryption" in conv_detail["title"].lower() or "data" in conv_detail["title"].lower()
            assert len(conv_detail["messages"]) == 2

            user_msg = conv_detail["messages"][0]
            asst_msg = conv_detail["messages"][1]
            assert user_msg["role"] == "user"
            assert user_msg["content"] == "What is the data encryption standard at rest?"

            assert asst_msg["role"] == "assistant"
            assert asst_msg["metadata"]["citations"] != []
            assert asst_msg["metadata"]["citations"][0]["citation_id"] == "S1"

    asyncio.run(_test())


def test_rag_query_followup_and_bounded_history():
    """Verify follow-up queries append to conversation and maintain chronological order."""
    async def _test():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            email = f"rag_followup_{uuid.uuid4().hex[:8]}@cogniva.ai"
            await client.post("/api/v1/auth/register", json={"email": email, "password": "Password123!", "full_name": "Followup Tester"})
            login = await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123!"})
            headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

            # Upload document
            pdf_bytes = create_pdf([
                "Cogniva Employee Handbook.\nSection 4.1: Maternity leave is 16 weeks fully paid.\nSection 4.2: Paternity leave is 6 weeks fully paid.",
            ])
            upload = await client.post(
                "/api/v1/documents",
                headers=headers,
                files={"file": ("handbook.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
            )
            doc_id = upload.json()["id"]
            await client.post(f"/api/v1/documents/{doc_id}/process", headers=headers)

            # Turn 1
            res1 = await client.post(
                "/api/v1/rag/query",
                headers=headers,
                json={"query": "How many weeks of maternity leave do employees get?"},
            )
            assert res1.status_code == 200
            conv_id = res1.json()["conversation_id"]

            # Turn 2: Follow-up in same conversation
            res2 = await client.post(
                "/api/v1/rag/query",
                headers=headers,
                json={
                    "query": "What about paternity leave?",
                    "conversation_id": conv_id,
                },
            )
            assert res2.status_code == 200
            assert res2.json()["conversation_id"] == conv_id

            # Verify conversation contains 4 messages in chronological order
            detail = await client.get(f"/api/v1/conversations/{conv_id}", headers=headers)
            messages = detail.json()["messages"]
            assert len(messages) == 4
            assert [m["role"] for m in messages] == ["user", "assistant", "user", "assistant"]
            assert messages[0]["content"] == "How many weeks of maternity leave do employees get?"
            assert messages[2]["content"] == "What about paternity leave?"

    asyncio.run(_test())


def test_historical_citations_preserved_and_inspectable():
    """Verify that reopening a past conversation preserves citation provenance and allows source inspection."""
    async def _test():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            email = f"hist_cite_{uuid.uuid4().hex[:8]}@cogniva.ai"
            await client.post("/api/v1/auth/register", json={"email": email, "password": "Password123!", "full_name": "Hist Cite"})
            login = await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123!"})
            headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

            pdf_bytes = create_pdf([
                "Cogniva AI Policy. All production model weights must be cryptographically hashed with SHA-256.",
            ])
            upload = await client.post(
                "/api/v1/documents",
                headers=headers,
                files={"file": ("ai_policy.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
            )
            doc_id = upload.json()["id"]
            await client.post(f"/api/v1/documents/{doc_id}/process", headers=headers)

            # Query
            rag = await client.post(
                "/api/v1/rag/query",
                headers=headers,
                json={"query": "What hash algorithm is required for model weights?"},
            )
            conv_id = rag.json()["conversation_id"]
            orig_citations = rag.json()["citations"]
            assert len(orig_citations) >= 1
            target_chunk_id = orig_citations[0]["chunk_id"]

            # Reopen conversation later
            detail = await client.get(f"/api/v1/conversations/{conv_id}", headers=headers)
            asst_msg = detail.json()["messages"][1]
            stored_citations = asst_msg["metadata"]["citations"]
            assert len(stored_citations) == len(orig_citations)
            assert stored_citations[0]["citation_id"] == "S1"
            assert stored_citations[0]["chunk_id"] == target_chunk_id

            # Verify chunk inspection using the stored citation's chunk_id
            chunk_res = await client.get(
                f"/api/v1/documents/{doc_id}/chunks/{target_chunk_id}",
                headers=headers,
            )
            assert chunk_res.status_code == 200
            assert "SHA-256" in chunk_res.json()["content"]

    asyncio.run(_test())


def test_unconfigured_llm_does_not_persist_fake_assistant_answer():
    """Verify that when LLM provider fails (e.g. 503 missing key), no fake assistant message is persisted."""
    async def _test():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            email = f"fail_llm_{uuid.uuid4().hex[:8]}@cogniva.ai"
            await client.post("/api/v1/auth/register", json={"email": email, "password": "Password123!", "full_name": "Fail LLM"})
            login = await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123!"})
            headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

            pdf_bytes = create_pdf(["Cogniva Testing Document"])
            upload = await client.post(
                "/api/v1/documents",
                headers=headers,
                files={"file": ("test_doc.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
            )
            doc_id = upload.json()["id"]
            await client.post(f"/api/v1/documents/{doc_id}/process", headers=headers)

            # Create an explicit conversation
            conv = await client.post("/api/v1/conversations", headers=headers, json={"title": "Error Test"})
            conv_id = conv.json()["id"]

            # Temporarily configure unconfigured OpenAI provider to trigger 503
            llm_service.set_provider(OpenAILLMProvider(api_key=""))
            try:
                rag_res = await client.post(
                    "/api/v1/rag/query",
                    headers=headers,
                    json={"query": "What is in test doc?", "conversation_id": conv_id},
                )
                assert rag_res.status_code == 503
                assert "OPENAI_API_KEY is not configured" in rag_res.json()["detail"]
            finally:
                llm_service.reset_default_provider()

            # Check that conversation has NO messages persisted (no fake assistant answer)
            detail = await client.get(f"/api/v1/conversations/{conv_id}", headers=headers)
            assert detail.json()["messages"] == []

    asyncio.run(_test())


def test_insufficient_evidence_turn_persisted():
    """Verify that insufficient evidence query records turn with insufficient_evidence=True and 0 citations."""
    async def _test():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            email = f"no_evid_{uuid.uuid4().hex[:8]}@cogniva.ai"
            await client.post("/api/v1/auth/register", json={"email": email, "password": "Password123!", "full_name": "No Evid"})
            login = await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123!"})
            headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

            # Query with zero documents in user account
            rag_res = await client.post(
                "/api/v1/rag/query",
                headers=headers,
                json={"query": "What is the secret recipe?"},
            )
            assert rag_res.status_code == 200
            data = rag_res.json()
            assert data["insufficient_evidence"] is True
            assert data["citations"] == []
            conv_id = data["conversation_id"]

            # Verify conversation contains this turn
            detail = await client.get(f"/api/v1/conversations/{conv_id}", headers=headers)
            messages = detail.json()["messages"]
            assert len(messages) == 2
            assert messages[0]["content"] == "What is the secret recipe?"
            assert messages[1]["metadata"]["insufficient_evidence"] is True
            assert messages[1]["metadata"]["citations"] == []

    asyncio.run(_test())
