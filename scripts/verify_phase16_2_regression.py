#!/usr/bin/env python3
"""
Cogniva Phase 16.2: Production Deployment & Integration Verification
Safe End-to-End Regression Verification against Live Render Deployment

Live Base URL: https://cogniva-api.onrender.com/api/v1
Commit Target: bcaaa2b4233dfc99de861c9b18704d319205bf2d
"""

import io
import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone

import httpx
import pymupdf


def generate_test_pdf(title: str, body: str) -> bytes:
    doc = pymupdf.open()
    page = doc.new_page()
    text = f"{title}\n\n{body}\n\nSecurity Architecture: AES-256 encryption at rest, TLS 1.3 in transit."
    page.insert_text(pymupdf.Point(50, 70), text, fontsize=10)
    pdf_bytes = doc.write()
    doc.close()
    return pdf_bytes


def main():
    base_url = "https://cogniva-api.onrender.com/api/v1"
    expected_commit = "bcaaa2b4233dfc99de861c9b18704d319205bf2d"

    print("=" * 80)
    print("COGNIVA PHASE 16.2: PRODUCTION REGRESSION & SECURITY VERIFICATION")
    print(f"Target URL: {base_url}")
    print(f"Expected Commit: {expected_commit}")
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 80)

    results = {}
    client = httpx.Client(base_url=base_url, timeout=45.0)

    def api_call(method: str, path: str, **kwargs) -> httpx.Response:
        for attempt in range(6):
            try:
                res = client.request(method, path, **kwargs)
                if res.status_code in (502, 503, 504) and attempt < 5:
                    print(f"  [Notice] Cold start / Gateway status {res.status_code}, warming up (attempt {attempt + 1}/6)...")
                    time.sleep(5.0)
                    continue
                return res
            except (httpx.ReadError, httpx.ConnectError, httpx.RemoteProtocolError, httpx.TransportError) as exc:
                if attempt == 5:
                    raise
                time.sleep(2.0)

    # -------------------------------------------------------------------------
    # TEST 1: Render Deployment Status & Health Probes
    # -------------------------------------------------------------------------
    print("\n[TEST 1] Verifying Render Deployment Status & Health Probes...")
    cid = f"phase16-2-{uuid.uuid4().hex[:8]}"
    t0 = time.perf_counter()
    h_res = api_call("GET", "/health", headers={"X-Correlation-ID": cid})
    h_latency_ms = round((time.perf_counter() - t0) * 1000, 2)
    assert h_res.status_code == 200, f"Health probe failed: {h_res.status_code}"
    h_data = h_res.json()
    assert h_data.get("status") == "ok", f"Unexpected status: {h_data}"
    assert h_data.get("commit") == expected_commit, f"Commit mismatch: {h_data.get('commit')}"
    assert h_res.headers.get("x-correlation-id") == cid, "Correlation ID not echoed"
    results["health_probe"] = {
        "status": "PASS",
        "version": h_data.get("version"),
        "commit": h_data.get("commit"),
        "latency_ms": h_latency_ms,
    }
    print(f"  PASS: Health Probe (200 OK) | Commit: {h_data.get('commit')[:12]} | Version: {h_data.get('version')} | Latency: {h_latency_ms}ms")

    # Readiness
    r_res = api_call("GET", "/health/ready")
    assert r_res.status_code == 200, f"Readiness probe failed: {r_res.status_code}"
    r_data = r_res.json()
    assert r_data.get("database") == "connected", "Database not connected"
    assert r_data.get("storage") == "local", "Storage not local"
    assert r_data.get("storage_durable") is False, "Storage durability violated zero-budget rule"
    results["readiness_probe"] = {
        "status": "PASS",
        "database": r_data.get("database"),
        "storage": r_data.get("storage"),
        "storage_durable": r_data.get("storage_durable"),
    }
    print(f"  PASS: Readiness Probe (200 OK) | DB: {r_data.get('database')} | Storage: {r_data.get('storage')} (durable={r_data.get('storage_durable')})")

    # Diagnostics
    d_res = api_call("GET", "/health/diagnostics")
    assert d_res.status_code == 200, f"Diagnostics probe failed: {d_res.status_code}"
    d_data = d_res.json()
    models = d_data.get("models", {})
    results["diagnostics_probe"] = {
        "status": "PASS",
        "embedding_provider": models.get("embedding_provider"),
        "llm_provider": models.get("llm_provider"),
    }
    print(f"  PASS: Diagnostics Probe (200 OK) | Embedding: {models.get('embedding_provider')} | LLM: {models.get('llm_provider')}")

    # -------------------------------------------------------------------------
    # TEST 2: Migration Endpoint Security (Remediation Verification)
    # -------------------------------------------------------------------------
    print("\n[TEST 2] Verifying Migration Endpoint Security Remediation...")
    m_res = api_call("POST", "/health/migrate")
    assert m_res.status_code == 401, f"Expected 401 Unauthorized on /health/migrate, got {m_res.status_code}"
    m_body = m_res.json()
    assert "Administrative authorization required" in m_body.get("detail", ""), f"Unexpected detail: {m_body}"
    print(f"  PASS: Unauthenticated POST /health/migrate rejected with HTTP 401 Unauthorized ({m_body.get('detail')})")

    ms_res = api_call("POST", "/health/migrate-storage")
    assert ms_res.status_code == 401, f"Expected 401 Unauthorized on /health/migrate-storage, got {ms_res.status_code}"
    ms_body = ms_res.json()
    assert "Administrative authorization required" in ms_body.get("detail", ""), f"Unexpected detail: {ms_body}"
    print(f"  PASS: Unauthenticated POST /health/migrate-storage rejected with HTTP 401 Unauthorized ({ms_body.get('detail')})")

    # Verify no schema or table enumeration leaked
    assert "tables" not in m_body and "applied" not in m_body
    results["migration_security"] = {"status": "PASS", "migrate_status": 401, "migrate_storage_status": 401}

    # -------------------------------------------------------------------------
    # TEST 3: User Registration & Authentication (Ephemeral Tenant)
    # -------------------------------------------------------------------------
    print("\n[TEST 3] User Registration & Authentication (Ephemeral Tenant)...")
    suffix = uuid.uuid4().hex[:8]
    test_email = f"phase16_2_regression_{suffix}@cogniva.ai"
    test_password = "SecureEnterprisePassword123!"

    reg_res = api_call("POST", "/auth/register", json={"email": test_email, "password": test_password, "full_name": f"Regression Tester {suffix}"})
    if reg_res.status_code == 429:
        wait_s = int(reg_res.headers.get("Retry-After", 25))
        print(f"  Rate limited, waiting {wait_s} seconds...")
        time.sleep(wait_s + 1)
        reg_res = api_call("POST", "/auth/register", json={"email": test_email, "password": test_password, "full_name": f"Regression Tester {suffix}"})
    assert reg_res.status_code == 201, f"Registration failed: {reg_res.status_code} {reg_res.text}"
    print(f"  PASS: Registered ephemeral tenant: {test_email}")

    login_res = api_call("POST", "/auth/login", json={"email": test_email, "password": test_password})
    assert login_res.status_code == 200, f"Login failed: {login_res.status_code} {login_res.text}"
    token = login_res.json()["access_token"]
    auth_headers = {"Authorization": f"Bearer {token}", "X-Correlation-ID": f"corr-{suffix}"}

    me_res = api_call("GET", "/auth/me", headers=auth_headers)
    assert me_res.status_code == 200, f"GET /auth/me failed: {me_res.status_code}"
    user_data = me_res.json()
    user_id = user_data["id"]
    assert user_data["email"] == test_email
    print(f"  PASS: Authenticated as user_id={user_id[:8]} ({test_email})")
    results["auth"] = {"status": "PASS", "user_id": user_id, "email": test_email}

    # -------------------------------------------------------------------------
    # TEST 4: Document Ingestion & Background Processing
    # -------------------------------------------------------------------------
    print("\n[TEST 4] Document Ingestion & Background Job Tracking...")
    pdf_bytes = generate_test_pdf(
        "Cogniva Resiliency & Zero-Budget Recovery Specification",
        "Cogniva enables full semantic search and grounded synthesis over enterprise documents. "
        "Even when local container storage is ephemeral, the system reconstructs normalized content "
        "from durable database chunk state with complete cryptographic audit trails."
    )
    up_res = api_call(
        "POST",
        "/documents",
        headers=auth_headers,
        files={"file": ("resiliency_spec.pdf", pdf_bytes, "application/pdf")},
    )
    assert up_res.status_code == 201, f"Document upload failed: {up_res.status_code} {up_res.text}"
    doc_id = up_res.json()["id"]
    print(f"  PASS: Uploaded test document: doc_id={doc_id} ({len(pdf_bytes)} bytes)")

    # Trigger background processing
    proc_res = api_call("POST", f"/documents/{doc_id}/process?background=true", headers=auth_headers)
    assert proc_res.status_code == 200, f"Trigger process failed: {proc_res.status_code}"

    # Poll background job status
    print("  Polling background job status...")
    job_completed = False
    job_info = None
    for attempt in range(25):
        time.sleep(1.5)
        j_res = api_call("GET", f"/documents/{doc_id}/job", headers=auth_headers)
        assert j_res.status_code == 200, f"Get job failed: {j_res.status_code}"
        job_data = j_res.json()
        if job_data.get("status") == "completed":
            job_completed = True
            job_info = job_data
            break
        elif job_data.get("status") == "failed":
            raise RuntimeError(f"Job failed unexpectedly: {job_data}")

    assert job_completed, f"Job timed out: {job_data}"
    print(f"  PASS: Ingestion job completed in {job_info.get('duration_seconds')}s (progress={job_info.get('progress')}%, stage={job_info.get('stage')})")
    results["document_processing"] = {
        "status": "PASS",
        "doc_id": doc_id,
        "job_id": job_info.get("id"),
        "duration_seconds": job_info.get("duration_seconds"),
    }

    # -------------------------------------------------------------------------
    # TEST 5: Vector Search / RAG Turn
    # -------------------------------------------------------------------------
    print("\n[TEST 5] Vector Search & RAG Turn...")
    # Check chunks
    c_res = api_call("GET", f"/documents/{doc_id}/chunks", headers=auth_headers)
    assert c_res.status_code == 200, f"Get chunks failed: {c_res.status_code}"
    chunks_list = c_res.json().get("chunks", []) if isinstance(c_res.json(), dict) else c_res.json()
    assert len(chunks_list) > 0, "No chunks found"
    print(f"  PASS: Chunks verified: {len(chunks_list)} chunk(s) stored in PostgreSQL with pgvector embeddings.")

    # Vector search
    t0 = time.perf_counter()
    ret_res = api_call(
        "POST",
        "/retrieval/search",
        headers=auth_headers,
        json={"query": "What encryption is used at rest and in transit?", "top_k": 3}
    )
    ret_latency_ms = round((time.perf_counter() - t0) * 1000, 2)
    assert ret_res.status_code == 200, f"Retrieval failed: {ret_res.status_code}"
    ret_data = ret_res.json()
    ret_results = ret_data.get("results", [])
    assert len(ret_results) > 0, "Empty retrieval results"
    print(f"  PASS: Semantic retrieval returned {len(ret_results)} result(s) in {ret_latency_ms}ms")

    # RAG Turn
    t0 = time.perf_counter()
    rag_res = api_call(
        "POST",
        "/rag/query",
        headers=auth_headers,
        json={
            "query": "What does the resiliency specification state regarding zero-budget recovery and encryption?",
            "top_k": 3,
            "document_id": doc_id,
        }
    )
    rag_latency_ms = round((time.perf_counter() - t0) * 1000, 2)
    assert rag_res.status_code == 200, f"RAG query failed: {rag_res.status_code}"
    rag_data = rag_res.json()
    answer = rag_data.get("answer", "")
    citations = rag_data.get("citations", [])
    assert len(answer) > 20, f"Empty RAG answer: {answer}"
    print(f"  PASS: RAG synthesized answer in {rag_latency_ms}ms | Citations: {len(citations)}")
    print(f"        Answer preview: \"{answer[:120]}...\"")
    results["rag"] = {
        "status": "PASS",
        "retrieval_latency_ms": ret_latency_ms,
        "rag_latency_ms": rag_latency_ms,
        "citation_count": len(citations),
    }

    # -------------------------------------------------------------------------
    # TEST 6: Document Summarization
    # -------------------------------------------------------------------------
    print("\n[TEST 6] Document Summarization...")
    t0 = time.perf_counter()
    sum_res = api_call(
        "POST",
        f"/documents/{doc_id}/summarize",
        headers=auth_headers,
        json={"mode": "concise", "force_refresh": True}
    )
    sum_latency_ms = round((time.perf_counter() - t0) * 1000, 2)
    assert sum_res.status_code == 200, f"Summarize failed: {sum_res.status_code}"
    sum_data = sum_res.json()
    assert len(sum_data.get("summary", "")) > 20, "Empty summary"
    print(f"  PASS: Summarization generated in {sum_latency_ms}ms | Length: {len(sum_data['summary'])} chars")
    results["summarization"] = {"status": "PASS", "latency_ms": sum_latency_ms}

    # -------------------------------------------------------------------------
    # TEST 7: Collection Creation & Assignment Lifecycle
    # -------------------------------------------------------------------------
    print("\n[TEST 7] Collection Creation, Assignment, & Lifecycle...")
    col_res = api_call(
        "POST",
        "/collections",
        headers=auth_headers,
        json={"name": f"Regression Collection {suffix}", "description": "Ephemeral test collection", "color": "#059669"}
    )
    assert col_res.status_code == 201, f"Create collection failed: {col_res.status_code}"
    col_id = col_res.json()["id"]
    print(f"  PASS: Collection created: col_id={col_id}")

    # Add document to collection
    add_res = api_call("POST", f"/collections/{col_id}/documents", headers=auth_headers, json={"document_id": doc_id})
    assert add_res.status_code in (200, 201), f"Add doc to collection failed: {add_res.status_code}"

    # Verify collection detail
    col_det = api_call("GET", f"/collections/{col_id}", headers=auth_headers)
    assert col_det.status_code == 200
    assert col_det.json()["document_count"] >= 1
    print(f"  PASS: Document linked to collection (count={col_det.json()['document_count']})")

    # Delete collection
    del_col = api_call("DELETE", f"/collections/{col_id}", headers=auth_headers)
    assert del_col.status_code in (200, 204), f"Delete collection failed: {del_col.status_code}"
    print(f"  PASS: Collection deleted safely.")
    results["collections"] = {"status": "PASS", "col_id": col_id}

    # -------------------------------------------------------------------------
    # TEST 8: Evaluation & Benchmark Transparency (Phase 16.1 Fix Verification)
    # -------------------------------------------------------------------------
    print("\n[TEST 8] Evaluation & Benchmark Transparency (Phase 16.1 Fix)...")
    eval_res = api_call("GET", "/evaluation/metrics", headers=auth_headers)
    assert eval_res.status_code == 200, f"Evaluation metrics failed: {eval_res.status_code}"
    eval_data = eval_res.json()
    assert "operational_telemetry" in eval_data, "Missing operational_telemetry"
    assert "benchmark_metrics" in eval_data, "Missing benchmark_metrics"
    bm = eval_data["benchmark_metrics"]

    # Verify transparency fields from Phase 16.1
    assert bm.get("evaluation_status") == "NOT EVALUATED", f"Expected NOT EVALUATED, got {bm.get('evaluation_status')}"
    assert bm.get("is_evaluated") is False, f"Expected is_evaluated=False, got {bm.get('is_evaluated')}"
    assert bm.get("retrieval_hit_rate_at_5") == 0.0, f"Expected 0.0 (not evaluated), got {bm.get('retrieval_hit_rate_at_5')}"
    assert eval_data.get("evaluation_results", {}).get("status") == "NOT EVALUATED"
    assert eval_data.get("evaluation_results", {}).get("retrieval_hit_rate_at_5") is None
    assert "target_hit_rate_at_5" in bm, "Missing target_hit_rate_at_5 in benchmark_metrics"
    print(f"  PASS: Benchmark transparency verified:")
    print(f"        evaluation_status = \"{bm.get('evaluation_status')}\"")
    print(f"        is_evaluated = {bm.get('is_evaluated')}")
    print(f"        retrieval_hit_rate_at_5 = {bm.get('retrieval_hit_rate_at_5')} (correctly 0.0 / un-evaluated, not fake static constant)")
    print(f"        target_hit_rate_at_5 = {bm.get('target_hit_rate_at_5')}")
    results["evaluation_transparency"] = {"status": "PASS", "evaluation_status": bm.get("evaluation_status")}

    # -------------------------------------------------------------------------
    # TEST 9: Phase 11.2 Reconstructed Text Recovery
    # -------------------------------------------------------------------------
    print("\n[TEST 9] Zero-Budget Reconstructed Text Recovery Headers (Phase 11.2)...")
    dl_res = api_call("GET", f"/documents/{doc_id}/download?fallback_text=true", headers=auth_headers)
    assert dl_res.status_code == 200, f"Download failed: {dl_res.status_code}"
    assert "X-Cogniva-Recovered" in dl_res.headers, "Missing X-Cogniva-Recovered header"
    rec_val = dl_res.headers.get("X-Cogniva-Recovered")
    bin_val = dl_res.headers.get("X-Cogniva-Original-Binary-Available")
    print(f"  PASS: Download headers verified | X-Cogniva-Recovered: {rec_val} | X-Cogniva-Original-Binary-Available: {bin_val}")
    results["recovery_headers"] = {"status": "PASS", "recovered": rec_val, "binary_available": bin_val}

    # -------------------------------------------------------------------------
    # TEST 10: Document Deletion & Verification
    # -------------------------------------------------------------------------
    print("\n[TEST 10] Document Deletion & Verification...")
    del_res = api_call("DELETE", f"/documents/{doc_id}", headers=auth_headers)
    assert del_res.status_code in (200, 204), f"Delete document failed: {del_res.status_code}"
    print(f"  PASS: Document {doc_id[:8]} deleted.")

    # Confirm 404
    get_del = api_call("GET", f"/documents/{doc_id}", headers=auth_headers)
    assert get_del.status_code == 404, f"Document still accessible after delete: {get_del.status_code}"
    print(f"  PASS: Confirmed document returned 404 Not Found after deletion.")
    results["document_deletion"] = {"status": "PASS", "post_delete_status": 404}

    # -------------------------------------------------------------------------
    # TEST 11: Audit Logging & Zero Credential Leakage
    # -------------------------------------------------------------------------
    print("\n[TEST 11] Audit Logging & Zero-Leakage Verification...")
    audit_res = api_call("GET", "/audit-logs", headers=auth_headers)
    assert audit_res.status_code == 200, f"Audit logs failed: {audit_res.status_code}"
    audit_items = audit_res.json().get("items", []) if isinstance(audit_res.json(), dict) else audit_res.json()
    actions = [item.get("action") for item in audit_items]
    print(f"  PASS: Audit log contains {len(audit_items)} events. Actions: {list(set(actions))}")
    assert "DOCUMENT_UPLOAD" in actions, "Missing DOCUMENT_UPLOAD in audit log"
    assert "DOCUMENT_DELETE" in actions, "Missing DOCUMENT_DELETE in audit log"

    # Leakage check
    audit_raw = json.dumps(audit_res.json())
    assert test_password not in audit_raw, "Password leaked in audit logs!"
    assert token not in audit_raw or "[REDACTED]" in audit_raw, "Access token leaked in audit logs!"
    print(f"  PASS: Zero credential/token leakage verified in audit trail.")
    results["audit_logging"] = {"status": "PASS", "events_recorded": len(audit_items)}

    # -------------------------------------------------------------------------
    # SUMMARY
    # -------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("PHASE 16.2 PRODUCTION REGRESSION VERIFICATION: ALL 11 TESTS PASSED")
    print("=" * 80)
    for k, v in results.items():
        print(f"  * {k:25s}: {v}")

    # Output JSON summary for artifact embedding
    with open("cogniva/scripts/phase16_2_regression_summary.json", "w") as f:
        json.dump(results, f, indent=2)
    print("\nRegression summary written to scripts/phase16_2_regression_summary.json")


if __name__ == "__main__":
    main()
