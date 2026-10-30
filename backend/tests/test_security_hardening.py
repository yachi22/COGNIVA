import asyncio
import time
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import jwt
import pytest
from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from starlette.testclient import TestClient

from app.core.config import settings
from app.core.rate_limiter import SlidingWindowRateLimiter
from app.core.security import create_access_token, decode_access_token
from app.core.security_headers import SecurityHeadersMiddleware
from app.core.sanitizer import sanitize_error_detail
from app.models.document import Document
from app.models.user import User
from app.services.storage.service import StorageService
from app.services.report_service import ReportService
from app.services.research_service import ResearchService
from app.services.knowledge_graph_service import KnowledgeGraphService


# ---------------------------------------------------------------------------
# 1. Security Headers Middleware Tests
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_security_headers_injected_on_responses():
    """
    Verifies that SecurityHeadersMiddleware injects enterprise defense-in-depth headers
    including HSTS, CSP, X-Frame-Options, X-Content-Type-Options, and Referrer-Policy.
    """
    middleware = SecurityHeadersMiddleware(app=MagicMock())

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/v1/test",
        "headers": [],
    }
    req = Request(scope)

    async def mock_call_next(request: Request):
        return JSONResponse({"status": "ok"})

    resp = await middleware.dispatch(req, mock_call_next)

    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp.headers.get("X-Frame-Options") == "DENY"
    assert resp.headers.get("X-XSS-Protection") == "0"
    assert "Strict-Transport-Security" in resp.headers
    assert "max-age=31536000" in resp.headers.get("Strict-Transport-Security", "")
    assert resp.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert "Permissions-Policy" in resp.headers
    assert "Content-Security-Policy" in resp.headers
    assert "frame-ancestors 'none'" in resp.headers.get("Content-Security-Policy", "")


# ---------------------------------------------------------------------------
# 2. Sliding Window Rate Limiter Tests
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_rate_limiter_allows_under_limit_and_blocks_on_excess():
    """
    Verifies that the rate limiter allows requests up to the max threshold,
    and raises HTTP 429 with Retry-After header when threshold is breached.
    """
    limiter = SlidingWindowRateLimiter(max_requests=3, window_seconds=10, scope="test_auth")

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/v1/auth/login",
        "headers": [(b"x-forwarded-for", b"198.51.100.10")],
    }
    req = Request(scope)

    # First 3 requests must succeed
    await limiter.check(req)
    await limiter.check(req)
    await limiter.check(req)

    # 4th request must be rejected with HTTP 429
    with pytest.raises(HTTPException) as exc_info:
        await limiter.check(req)

    assert exc_info.value.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert "Rate limit exceeded" in exc_info.value.detail
    assert "Retry-After" in exc_info.value.headers
    assert int(exc_info.value.headers["Retry-After"]) >= 1


@pytest.mark.asyncio
async def test_rate_limiter_client_isolation():
    """
    Verifies that rate limits are isolated per client IP / identifier.
    """
    limiter = SlidingWindowRateLimiter(max_requests=2, window_seconds=10, scope="test_iso")

    req_ip1 = Request({"type": "http", "method": "POST", "path": "/test", "headers": [(b"x-forwarded-for", b"10.0.0.1")]})
    req_ip2 = Request({"type": "http", "method": "POST", "path": "/test", "headers": [(b"x-forwarded-for", b"10.0.0.2")]})

    # Exhaust IP 1
    await limiter.check(req_ip1)
    await limiter.check(req_ip1)
    with pytest.raises(HTTPException):
        await limiter.check(req_ip1)

    # IP 2 must still be allowed
    await limiter.check(req_ip2)
    await limiter.check(req_ip2)


# ---------------------------------------------------------------------------
# 3. Path Traversal & File Upload Validation Tests
# ---------------------------------------------------------------------------
def test_path_traversal_filename_sanitization():
    """
    Verifies that filename sanitization neutralizes directory traversal sequences,
    relative path prefixes, and special characters.
    """
    malicious_inputs = [
        "../../../../etc/passwd",
        "..\\..\\windows\\system32\\cmd.exe",
        "foo/bar/secret.pdf",
        "../../../app/core/config.py",
        "CON.pdf",
        "   ",
        'test"; rm -rf /; .pdf',
    ]

    for raw in malicious_inputs:
        clean = StorageService.sanitize_filename(raw)
        assert "/" not in clean
        assert "\\" not in clean
        assert ".." not in clean
        assert len(clean) > 0


def test_magic_bytes_validation_rejects_spoofed_file_contents():
    """
    Verifies that magic bytes inspection rejects executable, HTML, or corrupted files
    attempting to masquerade as PDFs or DOCX files.
    """
    storage = StorageService()

    # Executable MZ header spoofed as PDF
    with pytest.raises(HTTPException) as exc1:
        storage.validate_magic_bytes(header=b"MZ\x90\x00\x03\x00\x00\x00", file_type="pdf")
    assert exc1.value.status_code == status.HTTP_400_BAD_REQUEST

    # HTML script tag spoofed as DOCX
    with pytest.raises(HTTPException) as exc2:
        storage.validate_magic_bytes(header=b"<html><script>alert(1)</script></html>", file_type="docx")
    assert exc2.value.status_code == status.HTTP_400_BAD_REQUEST

    # Empty payload
    with pytest.raises(HTTPException) as exc3:
        storage.validate_magic_bytes(header=b"", file_type="pdf")
    assert exc3.value.status_code == status.HTTP_400_BAD_REQUEST


# ---------------------------------------------------------------------------
# 4. JWT Validation & Signature Hardening Tests
# ---------------------------------------------------------------------------
def test_jwt_tampered_signature_rejected():
    """
    Verifies that tokens with modified payloads or tampered signatures are rejected.
    """
    token = create_access_token(subject="user-12345")
    parts = token.split(".")
    # Tamper with the payload portion
    tampered_token = f"{parts[0]}.eyJhZG1pbiI6dHJ1ZX0.{parts[2]}"

    with pytest.raises(jwt.PyJWTError):
        decode_access_token(tampered_token)


def test_jwt_expired_token_rejected():
    """
    Verifies that expired JWT tokens are strictly rejected with ExpiredSignatureError.
    """
    past_delta = timedelta(seconds=-10)
    expired_token = create_access_token(subject="user-expired", expires_delta=past_delta)

    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(expired_token)


# ---------------------------------------------------------------------------
# 5. Cross-Tenant IDOR Denial Tests (Defense Verification)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_cross_tenant_report_generation_denial():
    """
    Verifies that ReportService strictly rejects report generation if any requested
    document_id does not belong to the authenticated user.
    """
    svc = ReportService()
    tenant_a = uuid.uuid4()
    doc_a = uuid.uuid4()
    doc_b_victim = uuid.uuid4()

    mock_db = AsyncMock()
    # Mock DB query: only doc_a is found because doc_b belongs to tenant_b
    mock_doc = MagicMock(spec=Document)
    mock_doc.id = doc_a
    mock_doc.user_id = tenant_a

    mock_res = MagicMock()
    mock_res.scalars.return_value.all.return_value = [mock_doc]
    mock_db.execute.return_value = mock_res

    with pytest.raises(HTTPException) as exc:
        await svc.generate_report(
            db=mock_db,
            user_id=tenant_a,
            topic="Quarterly Financial Audit",
            document_ids=[doc_a, doc_b_victim],
        )

    assert exc.value.status_code == status.HTTP_404_NOT_FOUND
    assert "access denied" in exc.value.detail.lower()


@pytest.mark.asyncio
async def test_cross_tenant_deep_research_denial():
    """
    Verifies that ResearchService rejects deep research requests scoped to another
    tenant's document upfront before invoking LLM synthesis.
    """
    svc = ResearchService()
    tenant_a = uuid.uuid4()
    doc_b_victim = uuid.uuid4()

    mock_db = AsyncMock()
    # Document lookup returns None (unauthorized or not found)
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_res

    with pytest.raises(HTTPException) as exc:
        await svc.execute_deep_research(
            db=mock_db,
            user_id=tenant_a,
            topic="Competitor Market Share",
            document_id=doc_b_victim,
        )

    assert exc.value.status_code == status.HTTP_404_NOT_FOUND
    assert "access denied" in exc.value.detail.lower()


@pytest.mark.asyncio
async def test_cross_tenant_knowledge_graph_denial():
    """
    Verifies that KnowledgeGraphService rejects knowledge graph requests scoped to
    another tenant's document upfront with 404.
    """
    svc = KnowledgeGraphService()
    tenant_a = uuid.uuid4()
    doc_b_victim = uuid.uuid4()

    mock_db = AsyncMock()
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_res

    with pytest.raises(HTTPException) as exc:
        await svc.get_tenant_knowledge_graph(
            db=mock_db,
            user_id=tenant_a,
            document_id=doc_b_victim,
        )

    assert exc.value.status_code == status.HTTP_404_NOT_FOUND
    assert "access denied" in exc.value.detail.lower()


# ---------------------------------------------------------------------------
# 6. Global Unhandled Exception Sanitization Tests
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_error_detail_sanitizer_prevents_credential_leakage():
    """
    Verifies that internal connection errors or tracebacks containing passwords
    or API keys are completely stripped before returning to clients.
    """
    raw_db_error = (
        "asyncpg.exceptions.InvalidPasswordError: password authentication failed "
        "for user 'postgres' password='SuperSecretDatabasePassword999!' at db.render.com:5432"
    )
    sanitized = sanitize_error_detail(raw_db_error)

    assert "SuperSecretDatabasePassword999!" not in sanitized
    assert "password=***" in sanitized or "[REDACTED]" in sanitized

