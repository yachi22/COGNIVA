import asyncio
import io
import uuid
import httpx
import pymupdf


def generate_sample_pdf() -> bytes:
    doc = pymupdf.open()
    # Page 1: Cogniva Architecture & Vector Search
    p1 = doc.new_page()
    p1.insert_text(
        pymupdf.Point(50, 100),
        "Cogniva Architecture & Semantic Vector Retrieval.\n\n"
        "Cogniva implements dense vector retrieval directly inside PostgreSQL utilizing the pgvector extension. "
        "Cosine similarity search is computed natively in SQL with strict tenant isolation.",
        fontsize=12,
    )
    # Page 2: Baking & Culinary Arts
    p2 = doc.new_page()
    p2.insert_text(
        pymupdf.Point(50, 100),
        "Culinary Pastry Techniques.\n\n"
        "Baking authentic French croissants requires laminating dough with high-fat unsalted butter, "
        "creating alternating layers of dough and butter through precise folds and refrigeration.",
        fontsize=12,
    )
    b = doc.write()
    doc.close()
    return b


async def run_live_e2e_verification():
    vite_base_url = "http://127.0.0.1:5173/api/v1"
    print(f"[*] Starting live E2E retrieval verification through Vite proxy: {vite_base_url}")

    async with httpx.AsyncClient(base_url=vite_base_url, timeout=30.0) as client:
        # Step 1 & 2: Register & Login User A
        user_a_email = f"live_user_a_{uuid.uuid4().hex[:6]}@cogniva.ai"
        pwd = "Password123!"
        reg_a = await client.post("/auth/register", json={"email": user_a_email, "password": pwd, "full_name": "Live User A"})
        assert reg_a.status_code == 201, f"User A registration failed: {reg_a.text}"
        print(f"[+] User A registered: {user_a_email}")

        login_a = await client.post("/auth/login", json={"email": user_a_email, "password": pwd})
        assert login_a.status_code == 200, f"User A login failed: {login_a.text}"
        token_a = login_a.json()["access_token"]
        headers_a = {"Authorization": f"Bearer {token_a}"}
        print("[+] User A logged in, JWT obtained.")

        # Step 3: Upload a real PDF document
        pdf_bytes = generate_sample_pdf()
        upload_resp = await client.post(
            "/documents",
            headers=headers_a,
            files={"file": ("cogniva_whitepaper.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        )
        assert upload_resp.status_code == 201, f"Upload failed: {upload_resp.text}"
        doc_a = upload_resp.json()
        doc_id_a = doc_a["id"]
        print(f"[+] Document uploaded successfully: ID={doc_id_a}, status={doc_a['status']}")

        # Step 4: Process document (Extraction -> Chunking -> Vector Embedding)
        proc_resp = await client.post(f"/documents/{doc_id_a}/process", headers=headers_a)
        assert proc_resp.status_code == 200, f"Processing failed: {proc_resp.text}"
        proc_data = proc_resp.json()
        assert proc_data["status"] == "processed", f"Document status is {proc_data['status']}"
        print(f"[+] Document processed: total_chunks={proc_data['metadata']['total_chunks']}, embedding_dimension={proc_data['metadata']['embedding_dimension']}")

        # Step 5: Confirm chunks and embeddings exist
        chunks_resp = await client.get(f"/documents/{doc_id_a}/chunks", headers=headers_a)
        assert chunks_resp.status_code == 200, f"Chunks retrieval failed: {chunks_resp.text}"
        chunks_data = chunks_resp.json()
        assert chunks_data["total"] >= 2
        print(f"[+] Confirmed {chunks_data['total']} chunks exist in document_chunks table.")

        # Step 6: Send semantic search query
        query_text = "How does pgvector compute cosine similarity in PostgreSQL?"
        search_resp = await client.post(
            "/retrieval/search",
            headers=headers_a,
            json={"query": query_text, "top_k": 5},
        )
        assert search_resp.status_code == 200, f"Retrieval search failed: {search_resp.text}"
        search_data = search_resp.json()
        print(f"[+] Retrieval search returned {search_data['total']} results.")

        # Step 7, 8, 9: Verify ranking, scores, and page provenance
        assert search_data["total"] >= 2
        top_result = search_data["results"][0]
        second_result = search_data["results"][1]

        print(f"    #1 Result: score={top_result['similarity_score']:.4f}, distance={top_result['cosine_distance']:.4f}, page={top_result['page_number']}")
        print(f"       Preview: {top_result['content'][:80]}...")
        print(f"    #2 Result: score={second_result['similarity_score']:.4f}, distance={second_result['cosine_distance']:.4f}, page={second_result['page_number']}")
        print(f"       Preview: {second_result['content'][:80]}...")

        # Assert relevant chunk (pgvector architecture) ranks #1
        assert "pgvector" in top_result["content"]
        assert top_result["similarity_score"] > second_result["similarity_score"]
        assert top_result["cosine_distance"] < second_result["cosine_distance"]
        assert top_result["page_number"] == 1
        assert top_result["document_filename"].startswith("cogniva_whitepaper") or "cogniva_whitepaper" in top_result["document_original_filename"]
        assert "embedding" not in top_result, "Raw embedding must not be exposed!"

        # Step 10: Register & Login User B
        user_b_email = f"live_user_b_{uuid.uuid4().hex[:6]}@cogniva.ai"
        reg_b = await client.post("/auth/register", json={"email": user_b_email, "password": pwd, "full_name": "Live User B"})
        assert reg_b.status_code == 201
        login_b = await client.post("/auth/login", json={"email": user_b_email, "password": pwd})
        assert login_b.status_code == 200
        token_b = login_b.json()["access_token"]
        headers_b = {"Authorization": f"Bearer {token_b}"}
        print(f"[+] User B registered and logged in: {user_b_email}")

        # Step 11 & 12: User B attempt retrieval
        # Global search -> 0 results
        search_b_global = await client.post(
            "/retrieval/search",
            headers=headers_b,
            json={"query": query_text, "top_k": 5},
        )
        assert search_b_global.status_code == 200
        assert search_b_global.json()["total"] == 0
        print("[+] User B global search returned 0 results (Tenant isolation verified).")

        # Scoped search using User A's document_id -> 404 Not Found
        search_b_scoped = await client.post(
            "/retrieval/search",
            headers=headers_b,
            json={"query": query_text, "document_id": doc_id_a, "top_k": 5},
        )
        assert search_b_scoped.status_code == 404
        assert search_b_scoped.json()["detail"] == "Document not found."
        print("[+] User B scoped search with User A's document_id returned 404 Not Found (Zero leakage verified).")

    print("\n[SUCCESS] All 12 live E2E verification steps PASSED through Vite proxy!")


if __name__ == "__main__":
    asyncio.run(run_live_e2e_verification())
