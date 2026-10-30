import asyncio
import io
import json
import uuid
import httpx
import pymupdf
from datetime import datetime, timedelta, timezone
import jwt


def generate_test_pdf(title: str, body: str) -> bytes:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text(pymupdf.Point(50, 80), f"{title}\n\n{body}", fontsize=12)
    pdf_bytes = doc.write()
    doc.close()
    return pdf_bytes


async def run_phase14_production_verification():
    base_url = "https://cogniva-api.onrender.com/api/v1"
    print(f"[*] Starting Phase 14 Enterprise Security Hardening Verification against {base_url} ...\n")

    async with httpx.AsyncClient(base_url=base_url, timeout=45.0) as client:
        # -------------------------------------------------------------
        # Test 1: Deployment Health & Version 0.1.5 Verification
        # -------------------------------------------------------------
        custom_cid = f"sec-audit-{uuid.uuid4().hex[:12]}"
        h_res = await client.get("/health", headers={"X-Correlation-ID": custom_cid})
        assert h_res.status_code == 200, f"Health check failed: {h_res.status_code} {h_res.text}"
        h_data = h_res.json()
        assert h_data.get("version") == "0.1.5", f"Expected version 0.1.5, got: {h_data.get('version')}"
        assert h_res.headers.get("x-correlation-id") == custom_cid
        assert h_data.get("correlation_id") == custom_cid
        print(f"[PASS] Test 1: Live backend running version {h_data.get('version')} (commit {h_data.get('commit')})")
        print(f"       Correlation ID propagated successfully: {custom_cid}")

        # -------------------------------------------------------------
        # Test 2: Enterprise Security Headers Verification
        # -------------------------------------------------------------
        headers = h_res.headers
        assert headers.get("x-content-type-options") == "nosniff", "Missing or invalid X-Content-Type-Options"
        assert headers.get("x-frame-options") == "DENY", "Missing or invalid X-Frame-Options"
        assert headers.get("x-xss-protection") == "0", "Missing or invalid X-XSS-Protection"
        assert "max-age=31536000" in headers.get("strict-transport-security", ""), "Missing or invalid HSTS header"
        assert headers.get("referrer-policy") == "strict-origin-when-cross-origin", "Missing or invalid Referrer-Policy"
        assert "permissions-policy" in headers, "Missing Permissions-Policy header"
        assert "frame-ancestors 'none'" in headers.get("content-security-policy", ""), "Missing or invalid CSP frame-ancestors"
        print("[PASS] Test 2: Enterprise Security Headers fully verified (HSTS, CSP, nosniff, DENY, Referrer-Policy).")

        # -------------------------------------------------------------
        # Test 3: Tenant A & Tenant B Setup with Audit Trail
        # -------------------------------------------------------------
        suffix = uuid.uuid4().hex[:6]
        user_a_email = f"sec_tenant_a_{suffix}@cogniva.ai"
        user_b_email = f"sec_tenant_b_{suffix}@cogniva.ai"
        password = "EnterpriseSecurePass123!"

        reg_a = await client.post("/auth/register", json={"email": user_a_email, "password": password, "full_name": "Sec Tenant A"})
        assert reg_a.status_code == 201, f"Tenant A register failed: {reg_a.text}"
        login_a = await client.post("/auth/login", json={"email": user_a_email, "password": password})
        assert login_a.status_code == 200, f"Tenant A login failed: {login_a.text}"
        token_a = login_a.json()["access_token"]
        headers_a = {"Authorization": f"Bearer {token_a}", "X-Correlation-ID": f"tenant-a-{suffix}"}

        reg_b = await client.post("/auth/register", json={"email": user_b_email, "password": password, "full_name": "Sec Tenant B"})
        assert reg_b.status_code == 201, f"Tenant B register failed: {reg_b.text}"
        login_b = await client.post("/auth/login", json={"email": user_b_email, "password": password})
        assert login_b.status_code == 200, f"Tenant B login failed: {login_b.text}"
        token_b = login_b.json()["access_token"]
        headers_b = {"Authorization": f"Bearer {token_b}", "X-Correlation-ID": f"tenant-b-{suffix}"}

        # Verify audit logs record registration and login for Tenant A
        audit_res = await client.get("/audit-logs", headers=headers_a)
        assert audit_res.status_code == 200, f"Audit logs failed: {audit_res.status_code}"
        audit_events = [log["action"] for log in audit_res.json()]
        assert "AUTH_REGISTER" in audit_events or "AUTH_LOGIN_SUCCESS" in audit_events, f"Expected auth audit events, got: {audit_events}"
        print(f"[PASS] Test 3: Provisioned isolated Tenant A ({user_a_email}) and Tenant B ({user_b_email}) with audit records.")

        # -------------------------------------------------------------
        # Test 4: Tampered and Expired JWT Token Rejection
        # -------------------------------------------------------------
        # 4a: Tampered Token
        token_parts = token_a.split(".")
        tampered_token = f"{token_parts[0]}.eyJhZG1pbiI6dHJ1ZX0.{token_parts[2]}"
        tampered_res = await client.get("/documents", headers={"Authorization": f"Bearer {tampered_token}"})
        assert tampered_res.status_code in (401, 403), f"Tampered token not rejected: {tampered_res.status_code}"

        # 4b: Expired Token (simulate expired payload with arbitrary secret)
        expired_payload = {
            "sub": str(uuid.uuid4()),
            "exp": datetime.now(timezone.utc) - timedelta(minutes=10),
            "iat": datetime.now(timezone.utc) - timedelta(minutes=20),
        }
        expired_token = jwt.encode(expired_payload, "some-secret", algorithm="HS256")
        expired_res = await client.get("/documents", headers={"Authorization": f"Bearer {expired_token}"})
        assert expired_res.status_code in (401, 403), f"Expired token not rejected: {expired_res.status_code}"
        print("[PASS] Test 4: Tampered and expired JWT tokens rejected with HTTP 401/403.")

        # -------------------------------------------------------------
        # Test 5: In-Memory Sliding-Window Abuse Protection (Rate Limiting)
        # -------------------------------------------------------------
        # /auth/login is rate-limited to 15 req/min. Rapidly send requests to trigger HTTP 429.
        rate_limited = False
        rate_limit_resp = None
        for i in range(20):
            res = await client.post(
                "/auth/login",
                json={"email": f"bad_login_{i}@cogniva.ai", "password": "wrongpassword"},
                headers={"X-Forwarded-For": f"203.0.113.{suffix[:2]}"}
            )
            if res.status_code == 429:
                rate_limited = True
                rate_limit_resp = res
                break
            await asyncio.sleep(0.05)

        assert rate_limited, "Rate limiter did not trigger HTTP 429 within 20 rapid auth requests"
        assert "Retry-After" in rate_limit_resp.headers, f"Missing Retry-After header: {rate_limit_resp.headers}"
        print(f"[PASS] Test 5: Abuse protection rate limiter triggered HTTP 429 (Retry-After: {rate_limit_resp.headers.get('Retry-After')}s).")

        # -------------------------------------------------------------
        # Test 6: File Upload Input Validation (Magic Bytes & Path Traversal)
        # -------------------------------------------------------------
        # 6a: Executable disguised as PDF
        fake_pdf = b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff\x00\x00ThisIsAnExecutable"
        bad_upload = await client.post(
            "/documents",
            headers=headers_a,
            files={"file": ("fake_doc.pdf", fake_pdf, "application/pdf")}
        )
        assert bad_upload.status_code == 400, f"Expected 400 for spoofed executable magic bytes, got: {bad_upload.status_code}"
        print("[PASS] Test 6a: Spoofed executable magic bytes rejected with HTTP 400.")

        # 6b: Path traversal in filename
        valid_pdf = generate_test_pdf("Security Audit Doc", "Confidential tenant A test content for security verification.")
        traversal_upload = await client.post(
            "/documents",
            headers=headers_a,
            files={"file": ("../../../../etc/shadow.pdf", valid_pdf, "application/pdf")}
        )
        assert traversal_upload.status_code == 201, f"Valid PDF upload failed: {traversal_upload.status_code} {traversal_upload.text}"
        doc_a = traversal_upload.json()
        doc_a_id = doc_a["id"]
        # Confirm stored filename has no path traversal
        assert ".." not in doc_a["filename"]
        assert "/" not in doc_a["filename"]
        assert "\\" not in doc_a["filename"]
        print(f"[PASS] Test 6b: Filename traversal sanitized safely to: '{doc_a['filename']}' (doc_id={doc_a_id}).")

        # Process document
        proc_res = await client.post(f"/documents/{doc_a_id}/process?background=false", headers=headers_a)
        assert proc_res.status_code == 200, f"Processing failed: {proc_res.status_code}"

        # -------------------------------------------------------------
        # Test 7: Multi-Tenant IDOR Denial (Cross-Tenant Isolation)
        # -------------------------------------------------------------
        # 7a: Tenant B cannot view Tenant A's document
        cross_get = await client.get(f"/documents/{doc_a_id}", headers=headers_b)
        assert cross_get.status_code == 404, f"IDOR Vulnerability: Tenant B read Tenant A's document! Status: {cross_get.status_code}"

        # 7b: Tenant B cannot download Tenant A's document
        cross_dl = await client.get(f"/documents/{doc_a_id}/download", headers=headers_b)
        assert cross_dl.status_code == 404, f"IDOR Vulnerability: Tenant B downloaded Tenant A's document! Status: {cross_dl.status_code}"

        # 7c: Tenant B cannot generate a report referencing Tenant A's document
        cross_report = await client.post(
            "/reports/generate",
            headers=headers_b,
            json={"topic": "Security Assessment", "document_ids": [doc_a_id]}
        )
        assert cross_report.status_code == 404, f"IDOR Vulnerability: Tenant B generated report using Tenant A's doc! Status: {cross_report.status_code}"

        # 7d: Tenant B cannot delete Tenant A's document
        cross_del = await client.delete(f"/documents/{doc_a_id}", headers=headers_b)
        assert cross_del.status_code == 404, f"IDOR Vulnerability: Tenant B deleted Tenant A's document! Status: {cross_del.status_code}"
        print("[PASS] Test 7: Cross-tenant IDOR access strictly denied (404) across read, download, report, and delete.")

        # -------------------------------------------------------------
        # Test 8: Phase 11.2 Reconstructed Binary & Safe Recovery Preservation
        # -------------------------------------------------------------
        auth_dl = await client.get(f"/documents/{doc_a_id}/download?fallback_text=true", headers=headers_a)
        assert auth_dl.status_code == 200, f"Tenant A download failed: {auth_dl.status_code}"
        assert "X-Cogniva-Recovered" in auth_dl.headers, "Phase 11.2 recovery headers missing"
        print(f"[PASS] Test 8: Zero-budget download and recovery preserved (Recovered: {auth_dl.headers.get('X-Cogniva-Recovered')}).")

        # -------------------------------------------------------------
        # Test 9: Document Deletion and Audit Trail Verification
        # -------------------------------------------------------------
        del_res = await client.delete(f"/documents/{doc_a_id}", headers=headers_a)
        assert del_res.status_code in (200, 204), f"Document deletion failed: {del_res.status_code}"

        # Confirm audit log records DOCUMENT_DELETE
        audit_res2 = await client.get("/audit-logs", headers=headers_a)
        assert audit_res2.status_code == 200
        actions = [log["action"] for log in audit_res2.json()]
        assert "DOCUMENT_DELETE" in actions, f"Expected DOCUMENT_DELETE in audit logs, found: {actions}"

        # Verify no credentials leaked in audit logs
        raw_audit_str = json.dumps(audit_res2.json())
        assert password not in raw_audit_str, "Vulnerability: plain password leaked in audit log payload!"
        print("[PASS] Test 9: Document deleted cleanly. Audit trail verified with zero credential leakage.")

        print("\n=====================================================================")
        print(">>> ALL 9 ENTERPRISE SECURITY PRODUCTION CHECKS PASSED ON RENDER <<<")
        print("=====================================================================")


if __name__ == "__main__":
    asyncio.run(run_phase14_production_verification())
