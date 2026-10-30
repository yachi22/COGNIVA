import asyncio
import io
import json
import uuid
import httpx
import pymupdf


def generate_test_pdf(title: str, body: str) -> bytes:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text(pymupdf.Point(50, 80), f"{title}\n\n{body}", fontsize=12)
    pdf_bytes = doc.write()
    doc.close()
    return pdf_bytes


async def run_phase13_production_verification():
    base_url = "https://cogniva-api.onrender.com/api/v1"
    print(f"[*] Starting Phase 13 Live Production Verification against {base_url} ...\n")

    async with httpx.AsyncClient(base_url=base_url, timeout=45.0) as client:
        # -------------------------------------------------------------
        # Test 1: Liveness and Custom Correlation ID Echoing
        # -------------------------------------------------------------
        custom_cid = f"cogniva-audit-{uuid.uuid4().hex[:12]}"
        h_res = await client.get("/health", headers={"X-Correlation-ID": custom_cid})
        assert h_res.status_code == 200, f"Health check failed: {h_res.status_code} {h_res.text}"
        h_data = h_res.json()
        assert h_res.headers.get("x-correlation-id") == custom_cid, f"Correlation ID header mismatch: {h_res.headers}"
        assert h_res.headers.get("x-request-id") == custom_cid, f"Request ID header mismatch: {h_res.headers}"
        assert h_data.get("correlation_id") == custom_cid, f"Correlation ID body mismatch: {h_data}"
        print(f"[PASS] Test 1: Liveness 200 OK with custom correlation ID echoing: {custom_cid}")
        print(f"       App: {h_data.get('app')}, Version: {h_data.get('version')}, Commit: {h_data.get('commit')}")

        # -------------------------------------------------------------
        # Test 2: Database Readiness Check & Storage Verification
        # -------------------------------------------------------------
        r_res = await client.get("/health/ready")
        assert r_res.status_code == 200, f"Readiness failed: {r_res.status_code} {r_res.text}"
        r_data = r_res.json()
        assert r_data["status"] == "ok"
        assert r_data["database"] == "connected"
        assert r_data["storage"] == "local"
        assert r_data["storage_durable"] is False, "Zero-budget requirement: must remain local without paid services"
        print(f"[PASS] Test 2: Readiness 200 OK. Database: connected, Storage: local (storage_durable=False)")

        # -------------------------------------------------------------
        # Test 3: Operational Diagnostics Endpoint
        # -------------------------------------------------------------
        d_res = await client.get("/health/diagnostics")
        assert d_res.status_code == 200, f"Health diagnostics failed: {d_res.status_code}"
        d_data = d_res.json()
        assert d_data["status"] == "healthy"
        assert d_data["version"] == "0.1.4"
        assert "password" not in json.dumps(d_data).lower()
        assert "secret" not in json.dumps(d_data).lower()
        print(f"[PASS] Test 3: Health diagnostics 200 OK (sanitized, zero credentials leaked)")

        # -------------------------------------------------------------
        # Test 4: Tenant A & Tenant B Setup
        # -------------------------------------------------------------
        user_a_email = f"phase13_tenant_a_{uuid.uuid4().hex[:6]}@cogniva.ai"
        user_b_email = f"phase13_tenant_b_{uuid.uuid4().hex[:6]}@cogniva.ai"
        password = "SecurePassword123!"

        reg_a = await client.post("/auth/register", json={"email": user_a_email, "password": password, "full_name": "Tenant A User"})
        assert reg_a.status_code == 201, f"Tenant A register failed: {reg_a.text}"
        login_a = await client.post("/auth/login", json={"email": user_a_email, "password": password})
        token_a = login_a.json()["access_token"]
        headers_a = {"Authorization": f"Bearer {token_a}", "X-Correlation-ID": f"tenant-a-{uuid.uuid4().hex[:8]}"}

        reg_b = await client.post("/auth/register", json={"email": user_b_email, "password": password, "full_name": "Tenant B User"})
        assert reg_b.status_code == 201, f"Tenant B register failed: {reg_b.text}"
        login_b = await client.post("/auth/login", json={"email": user_b_email, "password": password})
        token_b = login_b.json()["access_token"]
        headers_b = {"Authorization": f"Bearer {token_b}", "X-Correlation-ID": f"tenant-b-{uuid.uuid4().hex[:8]}"}
        print(f"[PASS] Test 4: Registered and authenticated Tenant A ({user_a_email}) and Tenant B ({user_b_email})")

        # -------------------------------------------------------------
        # Test 5: Document Upload & Asynchronous Ingestion Job
        # -------------------------------------------------------------
        pdf_bytes = generate_test_pdf(
            "Phase 13 Observability Specification",
            "This document tests telemetry duration tracking, correlation ID propagation, and job diagnosis."
        )
        upload_res = await client.post(
            "/documents",
            headers=headers_a,
            files={"file": ("phase13_observability_spec.pdf", pdf_bytes, "application/pdf")},
        )
        assert upload_res.status_code == 201, f"Upload failed: {upload_res.status_code} {upload_res.text}"
        doc_a_id = upload_res.json()["id"]
        print(f"[PASS] Test 5: Document uploaded by Tenant A: doc_id={doc_a_id}")

        # Trigger background processing
        proc_res = await client.post(f"/documents/{doc_a_id}/process?background=true", headers=headers_a)
        assert proc_res.status_code == 200, f"Process trigger failed: {proc_res.status_code}"

        # Poll job status
        final_job = None
        for poll_attempt in range(15):
            await asyncio.sleep(1.5)
            job_res = await client.get(f"/documents/{doc_a_id}/job", headers=headers_a)
            assert job_res.status_code == 200
            final_job = job_res.json()
            if final_job["status"] in ("completed", "failed"):
                break

        assert final_job is not None, "Job was not returned"
        assert final_job["status"] == "completed", f"Job failed: {final_job}"
        print(f"[PASS] Test 6: Job {final_job['id']} completed successfully!")
        print(f"       Duration: {final_job.get('duration_seconds')}s, Stage: {final_job.get('stage')}, Progress: {final_job.get('progress')}%")
        print(f"       Diagnosis: {final_job.get('diagnosis')}")
        assert "duration_seconds" in final_job
        assert final_job.get("is_stuck") is False
        assert final_job.get("retries_exhausted") is False

        # -------------------------------------------------------------
        # Test 7: Tenant-Scoped Job Diagnostics
        # -------------------------------------------------------------
        diag_res = await client.get("/documents/jobs/diagnostics", headers=headers_a)
        assert diag_res.status_code == 200, f"Jobs diagnostics failed: {diag_res.status_code}"
        diag_data = diag_res.json()
        assert diag_data["total_jobs_evaluated"] >= 1
        assert diag_data["active_jobs_count"] == 0
        assert diag_data["stuck_jobs_count"] == 0
        assert "recommendations" in diag_data
        print(f"[PASS] Test 7: Tenant-scoped jobs diagnostics returned successfully:")
        print(f"       Scope: {diag_data.get('tenant_scope')}, Total Evaluated: {diag_data.get('total_jobs_evaluated')}")
        print(f"       Recommendations: {diag_data.get('recommendations')}")

        # -------------------------------------------------------------
        # Test 8: Evaluation & Telemetry Operational Metrics Integration
        # -------------------------------------------------------------
        eval_res = await client.get("/evaluation/metrics", headers=headers_a)
        assert eval_res.status_code == 200, f"Evaluation metrics failed: {eval_res.status_code}"
        eval_data = eval_res.json()
        assert "operational_telemetry" in eval_data, f"operational_telemetry missing in evaluation: {eval_data.keys()}"
        op_telemetry = eval_data["operational_telemetry"]
        assert op_telemetry["total_jobs"] >= 1
        assert op_telemetry["completed_jobs"] >= 1
        assert op_telemetry["success_rate_pct"] == 100.0
        print(f"[PASS] Test 8: Evaluation & Telemetry dashboard includes operational telemetry:")
        print(f"       Completed: {op_telemetry.get('completed_jobs')}, Success Rate: {op_telemetry.get('success_rate_pct')}%, Avg Duration: {op_telemetry.get('avg_duration_seconds')}s")

        # -------------------------------------------------------------
        # Test 9: Multi-Tenant Scoping & Cross-Tenant Denial (404)
        # -------------------------------------------------------------
        cross_doc_res = await client.get(f"/documents/{doc_a_id}", headers=headers_b)
        assert cross_doc_res.status_code == 404, f"Security Violation: Tenant B retrieved Tenant A's document! Status={cross_doc_res.status_code}"

        cross_job_res = await client.get(f"/documents/{doc_a_id}/job", headers=headers_b)
        assert cross_job_res.status_code == 404, f"Security Violation: Tenant B retrieved Tenant A's job! Status={cross_job_res.status_code}"

        diag_b_res = await client.get("/documents/jobs/diagnostics", headers=headers_b)
        assert diag_b_res.status_code == 200
        diag_b_data = diag_b_res.json()
        assert diag_b_data["total_jobs_evaluated"] == 0, f"Tenant B saw jobs belonging to another tenant! {diag_b_data}"
        print(f"[PASS] Test 9: Cross-tenant denial verified: Tenant B receives 404 for Tenant A's doc & job, and sees 0 jobs in diagnostics.")

        # -------------------------------------------------------------
        # Test 10: Phase 11.2 Reconstructed Binary Download & Recovery Headers
        # -------------------------------------------------------------
        dl_res = await client.get(f"/documents/{doc_a_id}/download?fallback_text=true", headers=headers_a)
        assert dl_res.status_code == 200, f"Download failed: {dl_res.status_code}"
        assert "X-Cogniva-Recovered" in dl_res.headers
        print(f"[PASS] Test 10: Document download preserves Phase 11.2 recovery headers:")
        print(f"       X-Cogniva-Recovered: {dl_res.headers.get('X-Cogniva-Recovered')}")
        print(f"       X-Cogniva-Original-Binary-Available: {dl_res.headers.get('X-Cogniva-Original-Binary-Available')}")

        print("\n=====================================================================")
        print(">>> ALL 10 PRODUCTION VERIFICATION CHECKS PASSED ON RENDER CLOUD <<<")
        print("=====================================================================")


if __name__ == "__main__":
    asyncio.run(run_phase13_production_verification())
