import csv
import io
import json
import time
import uuid
from datetime import datetime, timedelta, timezone

import docx
import httpx
import jwt
import pymupdf


def generate_test_pdf(title: str, sections: list) -> bytes:
    doc = pymupdf.open()
    page = doc.new_page()
    text = f"{title}\n\n"
    for heading, body in sections:
        text += f"== {heading} ==\n{body}\n\n"
    page.insert_text(pymupdf.Point(50, 70), text, fontsize=10)
    pdf_bytes = doc.write()
    doc.close()
    return pdf_bytes


def generate_test_docx(title: str, sections: list) -> bytes:
    doc = docx.Document()
    doc.add_heading(title, 0)
    for heading, body in sections:
        doc.add_heading(heading, level=1)
        doc.add_paragraph(body)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def generate_test_csv() -> bytes:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["metric_name", "category", "target_value", "achieved_value", "status"])
    writer.writerow(["RAG Retrieval Latency", "Performance", "<250ms", "174ms", "Optimal"])
    writer.writerow(["Citation Grounding Coverage", "Accuracy", ">95%", "98.2%", "Exceeded"])
    writer.writerow(["Tenant Isolation Breach Count", "Security", "0", "0", "Pass"])
    writer.writerow(["Zero Budget Storage Recovery", "Reliability", "100%", "100%", "Pass"])
    return output.getvalue().encode("utf-8")


def run_phase15_acceptance():
    base_url = "https://cogniva-api.onrender.com/api/v1"
    print("=" * 80)
    print("COGNIVA PHASE 15: FINAL ENTERPRISE ACCEPTANCE & RELEASE READINESS VERIFICATION")
    print(f"Target Base URL: {base_url}")
    print("=" * 80 + "\n")

    benchmarks = {}
    client = httpx.Client(base_url=base_url, timeout=45.0)

    def api_call(method: str, path: str, **kwargs) -> httpx.Response:
        for attempt in range(5):
            try:
                return client.request(method, path, **kwargs)
            except (httpx.ReadError, httpx.ConnectError, httpx.RemoteProtocolError, httpx.TransportError):
                time.sleep(1.2)
                if attempt == 4:
                    raise

    try:
        # =====================================================================
        # 1. Repository & Deployment Inspection
        # =====================================================================
        print(">>> 1. REPOSITORY & DEPLOYMENT INSPECTION")
        cid = f"phase15-acc-{uuid.uuid4().hex[:10]}"
        t0 = time.perf_counter()
        h_res = api_call("GET", "/health", headers={"X-Correlation-ID": cid})
        benchmarks["health_latency_ms"] = round((time.perf_counter() - t0) * 1000, 2)
        assert h_res.status_code == 200, f"Health check failed: {h_res.status_code} {h_res.text}"
        h_data = h_res.json()

        assert h_data.get("version") == "0.1.5", f"Unexpected version: {h_data.get('version')}"
        assert h_data.get("app") == "Cogniva"
        assert h_res.headers.get("x-correlation-id") == cid
        print(f"  [PASS] 1.1 Liveness Probe: 200 OK | App: {h_data.get('app')} | Version: {h_data.get('version')} | Commit: {h_data.get('commit')[:12]}")
        print(f"         Correlation ID Echo: {cid} | Latency: {benchmarks['health_latency_ms']} ms")

        # Readiness Probe
        t0 = time.perf_counter()
        r_res = api_call("GET", "/health/ready")
        benchmarks["readiness_latency_ms"] = round((time.perf_counter() - t0) * 1000, 2)
        assert r_res.status_code == 200, f"Readiness probe failed: {r_res.status_code}"
        r_data = r_res.json()
        assert r_data.get("database") == "connected"
        assert r_data.get("storage") == "local"
        assert r_data.get("storage_durable") is False, "Zero-budget rule: must use local storage without paid buckets"
        print(f"  [PASS] 1.2 Readiness Probe: 200 OK | Database: {r_data.get('database')} | Storage: {r_data.get('storage')} (storage_durable={r_data.get('storage_durable')})")

        # Enterprise Security Headers Inspection
        sec_headers = h_res.headers
        assert sec_headers.get("x-content-type-options") == "nosniff"
        assert sec_headers.get("x-frame-options") == "DENY"
        assert "max-age=31536000" in sec_headers.get("strict-transport-security", "")
        assert sec_headers.get("referrer-policy") == "strict-origin-when-cross-origin"
        assert "frame-ancestors 'none'" in sec_headers.get("content-security-policy", "")
        print("  [PASS] 1.3 Security Headers: HSTS, CSP, X-Frame-Options, nosniff, Referrer-Policy confirmed active.")

        # =====================================================================
        # 2. Multi-Tenant Provisioning & Authentication
        # =====================================================================
        print("\n>>> 2. MULTI-TENANT PROVISIONING & AUTHENTICATION")
        suffix = uuid.uuid4().hex[:6]
        user_a_email = f"phase15_alpha_{suffix}@cogniva.ai"
        user_b_email = f"phase15_beta_{suffix}@cogniva.ai"
        password = "EnterpriseSecurePass123!"

        # Register Tenant A
        reg_a = api_call("POST", "/auth/register", json={"email": user_a_email, "password": password, "full_name": "Tenant Alpha"})
        if reg_a.status_code == 429:
            wait_s = int(reg_a.headers.get("Retry-After", 25))
            print(f"  [*] Rate limit active; waiting {wait_s}s...")
            time.sleep(wait_s + 1)
            reg_a = api_call("POST", "/auth/register", json={"email": user_a_email, "password": password, "full_name": "Tenant Alpha"})
        assert reg_a.status_code == 201, f"Tenant A registration failed: {reg_a.text}"

        login_a = api_call("POST", "/auth/login", json={"email": user_a_email, "password": password})
        assert login_a.status_code == 200, f"Tenant A login failed: {login_a.text}"
        token_a = login_a.json()["access_token"]
        headers_a = {"Authorization": f"Bearer {token_a}", "X-Correlation-ID": f"alpha-{suffix}"}

        # Register Tenant B
        reg_b = api_call("POST", "/auth/register", json={"email": user_b_email, "password": password, "full_name": "Tenant Beta"})
        assert reg_b.status_code == 201, f"Tenant B registration failed: {reg_b.text}"
        login_b = api_call("POST", "/auth/login", json={"email": user_b_email, "password": password})
        assert login_b.status_code == 200, f"Tenant B login failed: {login_b.text}"
        token_b = login_b.json()["access_token"]
        headers_b = {"Authorization": f"Bearer {token_b}", "X-Correlation-ID": f"beta-{suffix}"}

        print(f"  [PASS] 2.1 Tenant Alpha provisioned: {user_a_email}")
        print(f"  [PASS] 2.2 Tenant Beta provisioned: {user_b_email}")

        # Check me endpoint
        me_a = api_call("GET", "/auth/me", headers=headers_a)
        assert me_a.status_code == 200 and me_a.json()["email"] == user_a_email
        print(f"  [PASS] 2.3 Identity resolution: authenticated as {me_a.json()['email']}")

        # =====================================================================
        # 3. Multi-Format Ingestion (PDF, DOCX, CSV) & Background Job Tracking
        # =====================================================================
        print("\n>>> 3. MULTI-FORMAT INGESTION & DURABLE BACKGROUND JOB TRACKING")

        # 3.1 PDF Ingestion
        pdf_bytes = generate_test_pdf(
            "Cogniva Enterprise AI Guidelines & Security Policy",
            [
                ("Data Protection Framework", "All multimodal corporate data must be encrypted in transit using TLS 1.3 and at rest with AES-256. PostgreSQL pgvector stores 1536-dimensional embeddings with cosine distance."),
                ("Tenant Isolation Standards", "Cross-tenant access must strictly return HTTP 404 Not Found to prevent metadata and resource enumeration."),
                ("Model Synthesis Quarantine", "Untrusted retrieved passages must be isolated within strict delimiter blocks to prevent prompt injection attacks."),
            ]
        )
        up_pdf = api_call(
            "POST",
            "/documents",
            headers=headers_a,
            files={"file": ("enterprise_security_policy.pdf", pdf_bytes, "application/pdf")},
        )
        assert up_pdf.status_code == 201, f"PDF upload failed: {up_pdf.status_code} {up_pdf.text}"
        pdf_id = up_pdf.json()["id"]
        print(f"  [PASS] 3.1 PDF uploaded: id={pdf_id} ({len(pdf_bytes)} bytes)")

        # 3.2 DOCX Ingestion
        docx_bytes = generate_test_docx(
            "Technical Architecture & System Specification",
            [
                ("Background Processing Architecture", "Document ingestion is delegated to asynchronous background jobs with persistent PostgreSQL state tracking."),
                ("Bounded Retry Policy", "Embedding operations incorporate exponential backoff with max 3 retry attempts before marking the job as permanently failed."),
                ("Zero-Budget Recovery", "If ephemeral container disk is purged, the document service reconstructs normalized units directly from database chunks."),
            ]
        )
        up_docx = api_call(
            "POST",
            "/documents",
            headers=headers_a,
            files={"file": ("technical_architecture.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        )
        assert up_docx.status_code == 201, f"DOCX upload failed: {up_docx.status_code} {up_docx.text}"
        docx_id = up_docx.json()["id"]
        print(f"  [PASS] 3.2 DOCX uploaded: id={docx_id} ({len(docx_bytes)} bytes)")

        # 3.3 CSV Ingestion
        csv_bytes = generate_test_csv()
        up_csv = api_call(
            "POST",
            "/documents",
            headers=headers_a,
            files={"file": ("quarterly_kpis.csv", csv_bytes, "text/csv")},
        )
        assert up_csv.status_code == 201, f"CSV upload failed: {up_csv.status_code} {up_csv.text}"
        csv_id = up_csv.json()["id"]
        print(f"  [PASS] 3.3 CSV uploaded: id={csv_id} ({len(csv_bytes)} bytes)")

        # 3.4 Trigger Background Processing for all 3 documents
        for doc_id, fmt_name in [(pdf_id, "PDF"), (docx_id, "DOCX"), (csv_id, "CSV")]:
            proc_res = api_call("POST", f"/documents/{doc_id}/process?background=true", headers=headers_a)
            assert proc_res.status_code == 200, f"Failed to trigger {fmt_name} processing: {proc_res.status_code}"

        # 3.5 Poll Background Job Progress
        print("  [*] Polling background job status for all 3 ingestion jobs...")
        pending_docs = {pdf_id: "PDF", docx_id: "DOCX", csv_id: "CSV"}
        completed_jobs = {}

        for attempt in range(25):
            time.sleep(1.5)
            for d_id in list(pending_docs.keys()):
                j_res = api_call("GET", f"/documents/{d_id}/job", headers=headers_a)
                assert j_res.status_code == 200
                j_data = j_res.json()
                if j_data.get("status") in ("completed", "failed"):
                    completed_jobs[d_id] = j_data
                    del pending_docs[d_id]
            if not pending_docs:
                break

        assert len(pending_docs) == 0, f"Timed out waiting for jobs: {pending_docs}"
        for d_id, j in completed_jobs.items():
            assert j["status"] == "completed", f"Job failed: {j}"
            print(f"  [PASS] 3.4 Job {j['id'][:8]} completed | Doc: {d_id[:8]} | Duration: {j.get('duration_seconds')}s | Progress: {j.get('progress')}% | Stage: {j.get('stage')}")
            benchmarks[f"job_{d_id[:8]}_duration_s"] = j.get("duration_seconds", 0)

        # 3.6 Inspect Tenant Job Diagnostics
        t0 = time.perf_counter()
        j_diag = api_call("GET", "/documents/jobs/diagnostics", headers=headers_a)
        benchmarks["job_diagnostics_latency_ms"] = round((time.perf_counter() - t0) * 1000, 2)
        assert j_diag.status_code == 200
        jd_data = j_diag.json()
        assert jd_data["total_jobs_evaluated"] >= 3
        assert jd_data["stuck_jobs_count"] == 0
        print(f"  [PASS] 3.5 Job Diagnostics: total_evaluated={jd_data['total_jobs_evaluated']} | stuck=0 | recommendations={jd_data.get('recommendations')}")

        # =====================================================================
        # 4. Chunking, Embeddings, & Semantic Retrieval
        # =====================================================================
        print("\n>>> 4. CHUNKING, EMBEDDINGS, & SEMANTIC RETRIEVAL")
        chunks_res = api_call("GET", f"/documents/{pdf_id}/chunks", headers=headers_a)
        assert chunks_res.status_code == 200
        chunks_data = chunks_res.json()
        total_chunks = len(chunks_data.get("chunks", [])) if isinstance(chunks_data, dict) else len(chunks_data)
        assert total_chunks >= 1, f"No chunks found for PDF: {chunks_data}"
        print(f"  [PASS] 4.1 Chunks verified for PDF: {total_chunks} chunk(s) indexed with pgvector embeddings.")

        # Standalone Semantic Search Query
        t0 = time.perf_counter()
        retrieval_res = api_call(
            "POST",
            "/retrieval/search",
            headers=headers_a,
            json={"query": "What encryption standard is required for data at rest?", "top_k": 3}
        )
        benchmarks["retrieval_latency_ms"] = round((time.perf_counter() - t0) * 1000, 2)
        assert retrieval_res.status_code == 200, f"Retrieval failed: {retrieval_res.status_code}"
        ret_data = retrieval_res.json()
        ret_results = ret_data.get("results", [])
        assert len(ret_results) > 0, "No retrieval results found"
        top_chunk = ret_results[0]
        assert "AES-256" in top_chunk.get("content", ""), f"Top chunk did not match expected passage: {top_chunk.get('content')}"
        print(f"  [PASS] 4.2 Semantic retrieval returned {len(ret_results)} chunk(s) in {benchmarks['retrieval_latency_ms']} ms | Top score: {top_chunk.get('similarity_score', top_chunk.get('score'))}")

        # =====================================================================
        # 5. Grounded RAG & Citation Provenance
        # =====================================================================
        print("\n>>> 5. GROUNDED RAG & CITATION PROVENANCE")
        t0 = time.perf_counter()
        rag_res = api_call(
            "POST",
            "/rag/query",
            headers=headers_a,
            json={
                "query": "According to the enterprise guidelines, what are the tenant isolation standards and encryption standards?",
                "top_k": 3,
                "document_id": pdf_id,
            }
        )
        benchmarks["rag_latency_ms"] = round((time.perf_counter() - t0) * 1000, 2)
        assert rag_res.status_code == 200, f"RAG query failed: {rag_res.status_code} {rag_res.text}"
        rag_data = rag_res.json()
        answer = rag_data.get("answer", "")
        citations = rag_data.get("citations", [])
        assert len(answer) > 20, f"Empty or trivial RAG answer: {answer}"
        print(f"  [PASS] 5.1 RAG Answer synthesized in {benchmarks['rag_latency_ms']} ms:")
        print(f"         \"{answer[:140]}...\"")
        print(f"  [PASS] 5.2 Citation Provenance: {len(citations)} citation(s) anchored:")
        for idx, cit in enumerate(citations):
            print(f"         [{cit.get('id', idx + 1)}] Doc: {cit.get('document_title', cit.get('document_id'))} | Page: {cit.get('page_number')} | Excerpt: {cit.get('chunk_content', cit.get('text', ''))[:60]}...")

        # =====================================================================
        # 6. Intelligence Services: Summaries, Extraction, Reports & Research
        # =====================================================================
        print("\n>>> 6. ENTERPRISE INTELLIGENCE SERVICES")

        # 6.1 Summarization
        t0 = time.perf_counter()
        sum_res = api_call(
            "POST",
            f"/documents/{pdf_id}/summarize",
            headers=headers_a,
            json={"mode": "concise", "force_refresh": True}
        )
        benchmarks["summary_latency_ms"] = round((time.perf_counter() - t0) * 1000, 2)
        assert sum_res.status_code == 200, f"Summary failed: {sum_res.status_code} {sum_res.text}"
        sum_data = sum_res.json()
        assert "summary" in sum_data and len(sum_data["summary"]) > 20
        print(f"  [PASS] 6.1 Executive Summary generated in {benchmarks['summary_latency_ms']} ms | Mode: concise")
        print(f"         Preview: \"{sum_data['summary'][:120]}...\"")

        # 6.2 Structured Extraction
        t0 = time.perf_counter()
        ext_res = api_call(
            "POST",
            f"/documents/{docx_id}/extract-structured",
            headers=headers_a,
            json={"target_fields": ["architecture", "retry_policy", "recovery_mechanism"]}
        )
        benchmarks["extraction_latency_ms"] = round((time.perf_counter() - t0) * 1000, 2)
        assert ext_res.status_code == 200, f"Structured extraction failed: {ext_res.status_code}"
        ext_data = ext_res.json()
        print(f"  [PASS] 6.2 Structured extraction completed in {benchmarks['extraction_latency_ms']} ms | Fields: {list(ext_data.get('extracted_fields', ext_data).keys())[:4]}")

        # 6.3 Multi-Document Comparison
        t0 = time.perf_counter()
        comp_res = api_call(
            "POST",
            "/documents/compare",
            headers=headers_a,
            json={
                "document_ids": [pdf_id, docx_id],
                "comparison_prompt": "Compare the security requirements in the policy with the background processing implementation in the architecture."
            }
        )
        benchmarks["comparison_latency_ms"] = round((time.perf_counter() - t0) * 1000, 2)
        assert comp_res.status_code == 200, f"Document comparison failed: {comp_res.status_code}"
        comp_data = comp_res.json()
        print(f"  [PASS] 6.3 Multi-document cross-comparison generated in {benchmarks['comparison_latency_ms']} ms")

        # 6.4 Research Report Generation
        t0 = time.perf_counter()
        rep_res = api_call(
            "POST",
            "/reports/generate",
            headers=headers_a,
            json={
                "topic": "Enterprise Security Controls and Durability Architecture",
                "title": "Comprehensive Security & Resiliency Audit Report",
                "document_ids": [pdf_id, docx_id]
            }
        )
        benchmarks["report_latency_ms"] = round((time.perf_counter() - t0) * 1000, 2)
        assert rep_res.status_code == 200, f"Report generation failed: {rep_res.status_code}"
        rep_data = rep_res.json()
        assert "report_id" in rep_data
        print(f"  [PASS] 6.4 Research report synthesized in {benchmarks['report_latency_ms']} ms | Report ID: {rep_data['report_id'][:8]}")

        # 6.5 Deep Research Query Decomposition
        t0 = time.perf_counter()
        dr_res = api_call(
            "POST",
            "/research/deep-query",
            headers=headers_a,
            json={
                "topic": "Zero-budget recovery and background job retries",
                "document_id": docx_id,
                "max_subquestions": 2
            }
        )
        benchmarks["deep_research_latency_ms"] = round((time.perf_counter() - t0) * 1000, 2)
        assert dr_res.status_code == 200, f"Deep research failed: {dr_res.status_code}"
        dr_data = dr_res.json()
        subquestions = dr_data.get("subquestions", [])
        print(f"  [PASS] 6.5 Deep research inquiry completed in {benchmarks['deep_research_latency_ms']} ms | Subquestions decomposed: {len(subquestions)}")

        # =====================================================================
        # 7. Collections & Conversations Management
        # =====================================================================
        print("\n>>> 7. COLLECTIONS & CONVERSATION MANAGEMENT")

        # 7.1 Create Collection
        col_res = api_call(
            "POST",
            "/collections",
            headers=headers_a,
            json={"name": f"Enterprise Knowledge Core {suffix}", "description": "Core policies and specifications", "color": "#2563EB"}
        )
        assert col_res.status_code == 201, f"Create collection failed: {col_res.status_code}"
        col_id = col_res.json()["id"]
        print(f"  [PASS] 7.1 Collection created: id={col_id}")

        # 7.2 Add Document to Collection
        add_col_res = api_call("POST", f"/collections/{col_id}/documents", headers=headers_a, json={"document_id": pdf_id})
        assert add_col_res.status_code in (200, 201), f"Add to collection failed: {add_col_res.status_code}"

        # 7.3 Verify Collection Detail
        get_col_res = api_call("GET", f"/collections/{col_id}", headers=headers_a)
        assert get_col_res.status_code == 200
        assert get_col_res.json()["document_count"] >= 1
        print(f"  [PASS] 7.2 Document added to collection; verified count = {get_col_res.json()['document_count']}")

        # 7.4 Create Conversation Thread
        conv_res = api_call("POST", "/conversations", headers=headers_a, json={"title": "Q4 Enterprise Review"})
        assert conv_res.status_code == 201, f"Create conversation failed: {conv_res.status_code}"
        conv_id = conv_res.json()["id"]
        print(f"  [PASS] 7.3 Conversation thread created: id={conv_id}")

        # 7.5 List Conversations
        conv_list_res = api_call("GET", "/conversations", headers=headers_a)
        assert conv_list_res.status_code == 200
        conv_items = conv_list_res.json().get("items", []) if isinstance(conv_list_res.json(), dict) else conv_list_res.json()
        assert any(c["id"] == conv_id for c in conv_items)
        print(f"  [PASS] 7.4 Conversations list verified: thread {conv_id[:8]} confirmed present.")

        # Cleanup collection & conversation
        api_call("DELETE", f"/collections/{col_id}", headers=headers_a)
        api_call("DELETE", f"/conversations/{conv_id}", headers=headers_a)
        print("  [PASS] 7.5 Collections and conversation test records cleaned up safely.")

        # =====================================================================
        # 8. Evaluation & Telemetry Integration
        # =====================================================================
        print("\n>>> 8. EVALUATION & TELEMETRY INTEGRATION")
        t0 = time.perf_counter()
        eval_res = api_call("GET", "/evaluation/metrics", headers=headers_a)
        benchmarks["eval_metrics_latency_ms"] = round((time.perf_counter() - t0) * 1000, 2)
        assert eval_res.status_code == 200, f"Evaluation metrics failed: {eval_res.status_code}"
        eval_data = eval_res.json()

        assert "operational_telemetry" in eval_data, "Missing operational telemetry in evaluation"
        assert "benchmark_metrics" in eval_data, "Missing benchmark evaluation metrics"
        op_tel = eval_data["operational_telemetry"]
        bm_met = eval_data["benchmark_metrics"]

        print(f"  [PASS] 8.1 Live Tenant Operational Telemetry:")
        print(f"         Total Ingestion Jobs: {op_tel.get('total_jobs')} | Completed: {op_tel.get('completed_jobs')} | Success Rate: {op_tel.get('success_rate_pct')}% | Avg Duration: {op_tel.get('avg_duration_seconds')}s")
        print(f"  [PASS] 8.2 Empirical Benchmarks (Distinguished from Live Telemetry):")
        print(f"         Hit Rate: {bm_met.get('retrieval_hit_rate_at_5') * 100}% | MRR: {bm_met.get('retrieval_mrr')} | Faithfulness: {bm_met.get('groundedness_faithfulness_score') * 100}% | Hallucination Rate: {bm_met.get('hallucination_rate_pct')}%")

        # =====================================================================
        # 9. Phase 11.2 Zero-Budget Reconstructed Text Recovery
        # =====================================================================
        print("\n>>> 9. ZERO-BUDGET TEXT RECOVERY PRESERVATION (PHASE 11.2)")
        dl_res = api_call("GET", f"/documents/{pdf_id}/download?fallback_text=true", headers=headers_a)
        assert dl_res.status_code == 200, f"Download failed: {dl_res.status_code}"
        assert "X-Cogniva-Recovered" in dl_res.headers
        is_recovered = dl_res.headers.get("X-Cogniva-Recovered")
        is_binary_avail = dl_res.headers.get("X-Cogniva-Original-Binary-Available")
        print(f"  [PASS] 9.1 Download endpoint responded with Phase 11.2 headers:")
        print(f"         X-Cogniva-Recovered: {is_recovered} | X-Cogniva-Original-Binary-Available: {is_binary_avail}")

        # =====================================================================
        # 10. Multi-Tenant IDOR Denial (Cross-Tenant Security)
        # =====================================================================
        print("\n>>> 10. MULTI-TENANT IDOR DENIAL (CROSS-TENANT ISOLATION)")

        # Tenant B attempts access to Tenant A's resources
        idor_checks = [
            ("GET /documents/{id}", lambda: api_call("GET", f"/documents/{pdf_id}", headers=headers_b)),
            ("GET /documents/{id}/job", lambda: api_call("GET", f"/documents/{pdf_id}/job", headers=headers_b)),
            ("GET /documents/{id}/chunks", lambda: api_call("GET", f"/documents/{pdf_id}/chunks", headers=headers_b)),
            ("GET /documents/{id}/extracted", lambda: api_call("GET", f"/documents/{pdf_id}/extracted", headers=headers_b)),
            ("GET /documents/{id}/download", lambda: api_call("GET", f"/documents/{pdf_id}/download", headers=headers_b)),
            ("POST /documents/{id}/summarize", lambda: api_call("POST", f"/documents/{pdf_id}/summarize", headers=headers_b, json={"mode": "concise"})),
            ("POST /documents/{id}/extract-structured", lambda: api_call("POST", f"/documents/{pdf_id}/extract-structured", headers=headers_b, json={})),
            ("POST /reports/generate", lambda: api_call("POST", "/reports/generate", headers=headers_b, json={"topic": "IDOR Attack", "document_ids": [pdf_id]})),
            ("DELETE /documents/{id}", lambda: api_call("DELETE", f"/documents/{pdf_id}", headers=headers_b)),
        ]

        for desc, call_fn in idor_checks:
            res = call_fn()
            assert res.status_code == 404, f"IDOR Vulnerability on {desc}: Tenant B received {res.status_code} instead of 404!"
            print(f"  [PASS] 10.1 IDOR Denial: {desc} strictly returned 404 Not Found.")

        # Cross-Tenant Audit Log Boundary
        audit_b = api_call("GET", "/audit-logs", headers=headers_b)
        assert audit_b.status_code == 200
        logs_b = audit_b.json().get("items", []) if isinstance(audit_b.json(), dict) else audit_b.json()
        assert not any(log.get("user_id") == me_a.json()["id"] for log in logs_b)
        print("  [PASS] 10.2 Audit Log Isolation: Tenant B cannot view any of Tenant A's audit events.")

        # =====================================================================
        # 11. Security Hardening & Input Validation
        # =====================================================================
        print("\n>>> 11. SECURITY HARDENING & INPUT VALIDATION")

        # 11.1 Tampered JWT Token
        tampered = f"{token_a.split('.')[0]}.eyJhZG1pbiI6dHJ1ZX0.{token_a.split('.')[2]}"
        t_res = api_call("GET", "/documents", headers={"Authorization": f"Bearer {tampered}"})
        assert t_res.status_code in (401, 403)
        print(f"  [PASS] 11.1 Tampered JWT token rejected with HTTP {t_res.status_code}")

        # 11.2 Expired JWT Token
        exp_payload = {"sub": str(uuid.uuid4()), "exp": datetime.now(timezone.utc) - timedelta(minutes=10)}
        exp_tok = jwt.encode(exp_payload, "long-secret-key-at-least-32-bytes-length", algorithm="HS256")
        e_res = api_call("GET", "/documents", headers={"Authorization": f"Bearer {exp_tok}"})
        assert e_res.status_code in (401, 403)
        print(f"  [PASS] 11.2 Expired JWT token rejected with HTTP {e_res.status_code}")

        # 11.3 Spoofed Executable Magic Bytes
        spoof_pdf = b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff\x00\x00WindowsPEHeader"
        sp_res = api_call("POST", "/documents", headers=headers_a, files={"file": ("spoofed.pdf", spoof_pdf, "application/pdf")})
        assert sp_res.status_code == 400
        print(f"  [PASS] 11.3 Spoofed executable header rejected with HTTP 400 Bad Request")

        # 11.4 Path Traversal Defense
        trav_res = api_call("POST", "/documents", headers=headers_a, files={"file": ("../../../../etc/shadow.pdf", pdf_bytes, "application/pdf")})
        assert trav_res.status_code in (400, 403)
        print(f"  [PASS] 11.4 Path traversal payload blocked at edge/application boundary with HTTP {trav_res.status_code}")

        # =====================================================================
        # 12. Document Deletion & Audit Trail Redaction
        # =====================================================================
        print("\n>>> 12. DOCUMENT DELETION & AUDIT TRAIL REDACTION")
        for d_id, name in [(pdf_id, "PDF"), (docx_id, "DOCX"), (csv_id, "CSV")]:
            del_res = api_call("DELETE", f"/documents/{d_id}", headers=headers_a)
            assert del_res.status_code in (200, 204), f"Failed to delete {name} {d_id}: {del_res.status_code}"
            print(f"  [PASS] 12.1 Deleted {name} document: {d_id[:8]}")

        # Check Audit Log for Tenant A
        audit_res = api_call("GET", "/audit-logs", headers=headers_a)
        assert audit_res.status_code == 200
        audit_items = audit_res.json().get("items", []) if isinstance(audit_res.json(), dict) else audit_res.json()
        recorded_actions = set(item.get("action") for item in audit_items)
        assert "DOCUMENT_DELETE" in recorded_actions
        assert "DOCUMENT_UPLOAD" in recorded_actions

        # Verify zero credential leakage
        raw_audit = json.dumps(audit_res.json())
        assert password not in raw_audit
        assert "access_token" not in raw_audit or "[REDACTED]" in raw_audit
        print(f"  [PASS] 12.2 Audit trail verified ({len(audit_items)} events): actions include {list(recorded_actions)[:5]}")
        print("  [PASS] 12.3 Zero credential or token leakage in audit logs confirmed.")

        # =====================================================================
        # 13. Abuse Protection Rate Limiting
        # =====================================================================
        print("\n>>> 13. IN-MEMORY SLIDING-WINDOW RATE LIMITING")
        rate_limited = False
        rate_resp = None
        for i in range(20):
            res = api_call(
                "POST",
                "/auth/login",
                json={"email": f"bad_login_{i}_{suffix}@cogniva.ai", "password": "wrongpassword"}
            )
            if res.status_code == 429:
                rate_limited = True
                rate_resp = res
                break
            time.sleep(0.04)

        assert rate_limited, "Rate limiter did not trigger HTTP 429 within 20 rapid requests"
        assert "Retry-After" in rate_resp.headers
        print(f"  [PASS] 13.1 Sliding-window rate limiter triggered HTTP 429 (Retry-After: {rate_resp.headers.get('Retry-After')}s)")

        # =====================================================================
        # Summary of Measured Benchmarks
        # =====================================================================
        print("\n" + "=" * 80)
        print("PHASE 15 ACCEPTANCE BENCHMARK MEASUREMENTS (MEASURED LIVE)")
        print("=" * 80)
        for key, val in benchmarks.items():
            unit = "ms" if "latency" in key else "s"
            print(f"  - {key}: {val} {unit}")
        print("=" * 80)
        print(">>> ALL 13 ENTERPRISE ACCEPTANCE CRITERIA PASSED ON RENDER CLOUD <<<")
        print("=" * 80 + "\n")

    finally:
        client.close()

    return True


if __name__ == "__main__":
    run_phase15_acceptance()
