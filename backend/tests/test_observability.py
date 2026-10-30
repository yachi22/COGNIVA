import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi import Response, status
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.config import settings
from app.core.logging_config import (
    CorrelationFilter,
    CorrelationIdMiddleware,
    get_correlation_id,
    set_correlation_id,
)
from app.core.sanitizer import (
    sanitize_dictionary,
    sanitize_error_detail,
    sanitize_log_message,
)
from app.models.job import DocumentJob
from app.services.job_service import DocumentJobService
from app.api.v1.health import get_health, get_readiness


# ---------------------------------------------------------------------------
# 1. Sanitizer & Credential Redaction Tests
# ---------------------------------------------------------------------------
def test_sanitizer_redacts_bearer_tokens_and_jwt():
    raw_message = "Request header Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.e30.fake_signature_content"
    sanitized = sanitize_log_message(raw_message)
    assert "[REDACTED]" in sanitized
    assert "fake_signature_content" not in sanitized


def test_sanitizer_redacts_openai_api_keys():
    raw_message = "Connecting with API key sk-proj-abcdef1234567890abcdef123456"
    sanitized = sanitize_log_message(raw_message)
    assert "sk-proj...[REDACTED]" in sanitized
    assert "abcdef123456" not in sanitized


def test_sanitizer_redacts_database_urls():
    raw_url = "postgresql+asyncpg://postgres:super_secret_password_123@ep-cool-db.us-east-2.render.com:5432/cogniva"
    sanitized = sanitize_log_message(raw_url)
    assert "super_secret_password_123" not in sanitized
    assert "://postgres:***@ep-cool-db" in sanitized


def test_sanitizer_bounds_string_length():
    huge_text = "A" * 5000
    sanitized = sanitize_log_message(huge_text, max_length=100)
    assert len(sanitized) < 150
    assert "[TRUNCATED]" in sanitized


def test_sanitizer_dictionary_redaction():
    payload = {
        "user": "alice",
        "api_key": "secret-api-key-value",
        "password": "my_db_password",
        "nested": {
            "access_token": "bearer-secret-token",
            "normal_field": "visible_info",
        },
        "tags": ["prod", "openai_api_key=sk-secretvalue1234567890"],
    }
    sanitized = sanitize_dictionary(payload)
    assert sanitized["user"] == "alice"
    assert sanitized["api_key"] == "[REDACTED]"
    assert sanitized["password"] == "[REDACTED]"
    assert sanitized["nested"]["access_token"] == "[REDACTED]"
    assert sanitized["nested"]["normal_field"] == "visible_info"


def test_sanitize_error_detail_bounds_multiline_exceptions():
    exc_text = "ConnectionError: Failed to connect to host\nTraceback (most recent call last):\nFile 'foo.py' line 10"
    detail = sanitize_error_detail(exc_text, max_length=80)
    assert "\n" not in detail
    assert detail.startswith("ConnectionError: Failed to connect to host")


# ---------------------------------------------------------------------------
# 2. Correlation ID Context & Logging Filter Tests
# ---------------------------------------------------------------------------
def test_correlation_id_context_management():
    test_id = "test-corr-abc-123"
    token = set_correlation_id(test_id)
    assert get_correlation_id() == test_id

    # Test correlation filter injects into record and sanitizes message
    filter_instance = CorrelationFilter()
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=1,
        msg="Executing task with Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.fake_token_data",
        args=(),
        exc_info=None,
    )
    result = filter_instance.filter(record)
    assert result is True
    assert getattr(record, "correlation_id", None) == test_id
    assert "[REDACTED]" in record.msg
    assert "fake_token_data" not in record.msg


# ---------------------------------------------------------------------------
# 3. Health & Readiness Distinction Tests
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_health_liveness_endpoint_returns_ok_independently():
    """
    Liveness endpoint (/health) must return 200 OK with app metadata
    and correlation ID without depending on PostgreSQL availability.
    """
    set_correlation_id("live-test-req-001")
    health = await get_health()
    assert health["status"] == "ok"
    assert health["app"] == settings.PROJECT_NAME
    assert health["version"] == settings.VERSION
    assert health["correlation_id"] == "live-test-req-001"


@pytest.mark.asyncio
async def test_health_readiness_endpoint_healthy_database():
    """
    Readiness endpoint (/health/ready) returns 200 OK when database is responsive.
    """
    set_correlation_id("ready-test-req-002")
    mock_db = AsyncMock()
    mock_db.execute.return_value = MagicMock()

    resp = Response()
    result = await get_readiness(response=resp, db=mock_db)

    assert resp.status_code == 200
    assert result["status"] == "ok"
    assert result["database"] == "connected"
    assert result["correlation_id"] == "ready-test-req-002"


@pytest.mark.asyncio
async def test_health_readiness_distinguishes_db_unavailability_with_503():
    """
    Readiness endpoint (/health/ready) returns HTTP 503 Service Unavailable
    when database is unreachable, clearly distinguishing app availability from DB health,
    and guarantees error detail is strictly sanitized.
    """
    set_correlation_id("ready-err-003")
    mock_db = AsyncMock()
    mock_db.execute.side_effect = ConnectionError("FATAL: password authentication failed for user 'postgres' password=secret_password_here")

    resp = Response()
    result = await get_readiness(response=resp, db=mock_db)

    # Must return 503 Service Unavailable
    assert resp.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert result["status"] == "unhealthy"
    assert result["database"] == "unavailable"
    assert "secret_password_here" not in str(result.get("detail", ""))
    assert result["correlation_id"] == "ready-err-003"


# ---------------------------------------------------------------------------
# 4. Job Operational Properties & Stuck/Failure Diagnostics
# ---------------------------------------------------------------------------
def test_job_duration_calculation_from_timestamps():
    start = datetime(2026, 10, 31, 10, 0, 0, tzinfo=timezone.utc)
    end = datetime(2026, 10, 31, 10, 0, 14, 500000, tzinfo=timezone.utc)

    job = DocumentJob(
        id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        status="completed",
        stage="completed",
        progress=100,
        current_stage=4,
        total_stages=4,
        retry_count=0,
        max_retries=3,
        started_at=start,
        completed_at=end,
        metadata_={},
    )
    assert job.duration_seconds == 14.5


def test_job_diagnose_detects_stuck_pipeline():
    """
    Jobs remaining in 'processing' longer than timeout_seconds must be flagged as is_stuck=True.
    """
    long_ago = datetime.now(timezone.utc) - timedelta(seconds=450)
    job = DocumentJob(
        id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        status="processing",
        stage="embedding",
        progress=60,
        current_stage=3,
        total_stages=4,
        retry_count=0,
        max_retries=3,
        started_at=long_ago,
        metadata_={},
    )

    diag = job.diagnose(timeout_seconds=300)
    assert diag["is_stuck"] is True
    assert diag["failure_category"] == "timeout_error"
    assert "stuck in stage 'embedding'" in diag["diagnosis"]
    assert job.is_stuck is True


def test_job_diagnose_detects_retry_exhaustion():
    """
    Jobs with status='failed' and retry_count >= max_retries must be diagnosed as retries_exhausted=True.
    """
    job = DocumentJob(
        id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        status="failed",
        stage="failed",
        progress=60,
        current_stage=3,
        total_stages=4,
        retry_count=3,
        max_retries=3,
        error_message="Embedding provider rate limited",
        metadata_={"failure_category": "retry_exhaustion"},
    )

    diag = job.diagnose()
    assert diag["retries_exhausted"] is True
    assert diag["failure_category"] == "retry_exhaustion"
    assert "exhausted all 3 retries" in diag["diagnosis"]
    assert job.retries_exhausted is True


# ---------------------------------------------------------------------------
# 5. DocumentJobService Tenant Diagnostics & Operational Metrics Tests
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_tenant_diagnostics_and_operational_metrics_scoping():
    """
    Verifies that get_tenant_diagnostics and get_tenant_operational_metrics correctly
    aggregate jobs, detect anomalies, and enforce tenant scoping.
    """
    svc = DocumentJobService()
    tenant_id = uuid.uuid4()
    doc_id = uuid.uuid4()

    # Create 3 test jobs: 1 completed, 1 stuck, 1 retry-exhausted
    now = datetime.now(timezone.utc)
    job_completed = DocumentJob(
        id=uuid.uuid4(),
        document_id=doc_id,
        user_id=tenant_id,
        status="completed",
        stage="completed",
        progress=100,
        current_stage=4,
        total_stages=4,
        retry_count=0,
        max_retries=3,
        started_at=now - timedelta(seconds=20),
        completed_at=now - timedelta(seconds=5),
        metadata_={"duration_seconds": 15.0},
    )

    job_stuck = DocumentJob(
        id=uuid.uuid4(),
        document_id=doc_id,
        user_id=tenant_id,
        status="processing",
        stage="embedding",
        progress=60,
        current_stage=3,
        total_stages=4,
        retry_count=1,
        max_retries=3,
        started_at=now - timedelta(seconds=500),
        metadata_={},
    )

    job_exhausted = DocumentJob(
        id=uuid.uuid4(),
        document_id=doc_id,
        user_id=tenant_id,
        status="failed",
        stage="failed",
        progress=60,
        current_stage=3,
        total_stages=4,
        retry_count=3,
        max_retries=3,
        error_message="Downstream timeout",
        metadata_={"failure_category": "retry_exhaustion"},
    )

    mock_db = AsyncMock()
    mock_res = MagicMock()
    mock_res.scalars.return_value.all.return_value = [job_completed, job_stuck, job_exhausted]
    mock_db.execute.return_value = mock_res

    # 1. Test get_tenant_diagnostics
    diag = await svc.get_tenant_diagnostics(db=mock_db, user_id=tenant_id)
    assert diag["total_jobs_evaluated"] == 3
    assert diag["active_jobs_count"] == 1
    assert diag["stuck_jobs_count"] == 1
    assert diag["retries_exhausted_count"] == 1
    assert len(diag["stuck_jobs"]) == 1
    assert len(diag["recent_failed_jobs"]) == 1
    assert len(diag["recommendations"]) >= 1

    # 2. Test get_tenant_operational_metrics
    metrics = await svc.get_tenant_operational_metrics(db=mock_db, user_id=tenant_id)
    assert metrics["total_jobs"] == 3
    assert metrics["completed_jobs"] == 1
    assert metrics["failed_jobs"] == 1
    assert metrics["active_jobs"] == 1
    assert metrics["stuck_jobs"] == 1
    assert metrics["retries_exhausted_jobs"] == 1
    assert metrics["avg_duration_seconds"] == 15.0
    assert metrics["success_rate_pct"] == 50.0  # 1 completed out of 2 finalized (1 completed + 1 failed)


# ---------------------------------------------------------------------------
# 6. Correlation ID Middleware Tests
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_correlation_id_middleware_generates_and_propagates():
    """
    Verifies CorrelationIdMiddleware generates a fresh UUID if none supplied,
    and echoes inbound X-Correlation-ID when provided.
    """
    middleware = CorrelationIdMiddleware(app=MagicMock())

    # Case A: Fresh request with no correlation header
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/v1/test",
        "headers": [],
    }
    req = Request(scope)

    async def mock_call_next(request: Request):
        cid = get_correlation_id()
        assert cid != ""
        return JSONResponse({"echo_id": cid})

    resp = await middleware.dispatch(req, mock_call_next)
    outbound_cid = resp.headers.get("X-Correlation-ID")
    assert outbound_cid is not None
    assert len(outbound_cid) >= 16
    assert resp.headers.get("X-Request-ID") == outbound_cid

    # Case B: Inbound request with custom correlation header
    custom_trace = "custom-trace-uuid-98765"
    scope_custom = {
        "type": "http",
        "method": "GET",
        "path": "/api/v1/test",
        "headers": [(b"x-correlation-id", custom_trace.encode("utf-8"))],
    }
    req_custom = Request(scope_custom)

    async def mock_call_next_custom(request: Request):
        assert get_correlation_id() == custom_trace
        return JSONResponse({"echo_id": custom_trace})

    resp_custom = await middleware.dispatch(req_custom, mock_call_next_custom)
    assert resp_custom.headers.get("X-Correlation-ID") == custom_trace
    assert resp_custom.headers.get("X-Request-ID") == custom_trace
