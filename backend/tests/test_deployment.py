import asyncio
import os
import pytest
import httpx
from pydantic import ValidationError

from app.main import app
from app.core.config import Settings


def test_cors_origins_parsing():
    """Verify that CORS_ORIGINS parser supports comma-separated strings and JSON arrays."""
    # Comma-separated string
    s1 = Settings(CORS_ORIGINS="https://app.vercel.app, http://localhost:5173")
    assert "https://app.vercel.app" in s1.CORS_ORIGINS
    assert "http://localhost:5173" in s1.CORS_ORIGINS

    # JSON array string
    s2 = Settings(CORS_ORIGINS='["https://cogniva.ai", "https://app.cogniva.ai"]')
    assert s2.CORS_ORIGINS == ["https://cogniva.ai", "https://app.cogniva.ai"]


def test_database_url_normalization():
    """Verify that cloud database URLs (postgres://, postgresql://, sslmode=require) are properly normalized for asyncpg and sync psycopg."""
    # Test postgres:// with sslmode=require (typical Render / Supabase output)
    cloud_url = "postgres://user:pass@ep-cool-db.us-east-2.aws.neon.tech/neondb?sslmode=require"
    s = Settings(DATABASE_URL=cloud_url)

    # asyncpg requires postgresql+asyncpg:// and ssl=require
    async_url = s.async_database_url
    assert async_url.startswith("postgresql+asyncpg://")
    assert "ssl=require" in async_url
    assert "sslmode=" not in async_url

    # sync psycopg requires postgresql+psycopg://
    sync_url = s.sync_database_url
    assert sync_url.startswith("postgresql+psycopg://")


def test_production_security_validation_rejects_default_secret():
    """Verify that production environment strictly rejects default development SECRET_KEY and forces DEBUG=False."""
    with pytest.raises(ValueError) as excinfo:
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="cogniva-super-secret-key-for-development-change-in-production",
        )
    assert "CRITICAL SECURITY ERROR" in str(excinfo.value)

    # Strong custom secret passes and forces DEBUG=False
    valid_prod = Settings(
        ENVIRONMENT="production",
        SECRET_KEY="c4f87a9b0123456789abcdef0123456789abcdef0123456789abcdef01234567",
        DEBUG=True,  # Should be overridden to False
    )
    assert valid_prod.DEBUG is False


def test_health_and_readiness_endpoints():
    """Verify /health liveness and /health/ready database readiness endpoints."""
    async def _test():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            # Liveness
            res = await client.get("/api/v1/health")
            assert res.status_code == 200
            data = res.json()
            assert data["status"] == "ok"
            assert data["app"] == "Cogniva"
            assert "database_url" not in data
            assert "secret_key" not in data

            # Readiness
            ready_res = await client.get("/api/v1/health/ready")
            assert ready_res.status_code == 200
            ready_data = ready_res.json()
            assert ready_data["status"] == "ok"
            assert ready_data["database"] == "connected"

            # Root endpoint
            root_res = await client.get("/")
            assert root_res.status_code == 200
            assert root_res.json()["project"] == "Cogniva"

    asyncio.run(_test())


def test_no_credentials_leaked_in_error_or_root():
    """Verify that API root and health checks never leak storage paths or database passwords."""
    async def _test():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            for endpoint in ["/", "/api/v1/health", "/api/v1/health/ready"]:
                res = await client.get(endpoint)
                body = res.text
                assert "postgres:" not in body
                assert "password" not in body.lower() or "secret" not in body.lower()
                assert "storage/documents" not in body

    asyncio.run(_test())
