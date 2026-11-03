import pytest
from starlette.testclient import TestClient
from app.main import app
from app.core.config import settings


@pytest.fixture
def client():
    return TestClient(app)


def test_unauthenticated_post_health_migrate_returns_401(client):
    """
    Verifies that unauthenticated requests cannot execute migrations.
    Must return HTTP 401 Unauthorized.
    """
    response = client.post("/api/v1/health/migrate")
    assert response.status_code == 401
    assert "Administrative authorization required" in response.json().get("detail", "")


def test_unauthenticated_post_health_migrate_storage_returns_401(client):
    """
    Verifies that unauthenticated requests cannot execute storage migration.
    Must return HTTP 401 Unauthorized.
    """
    response = client.post("/api/v1/health/migrate-storage")
    assert response.status_code == 401
    assert "Administrative authorization required" in response.json().get("detail", "")


def test_invalid_admin_key_returns_403(client, monkeypatch):
    """
    Verifies that requests with an invalid X-Admin-Key header receive HTTP 403 Forbidden.
    """
    monkeypatch.setattr(settings, "ADMIN_SECRET_KEY", "correct-super-secret-admin-key")
    response = client.post(
        "/api/v1/health/migrate",
        headers={"X-Admin-Key": "wrong-secret-key"},
    )
    assert response.status_code == 403
    assert "Invalid administrative secret key" in response.json().get("detail", "")


def test_unconfigured_admin_key_returns_403(client, monkeypatch):
    """
    Verifies that if ADMIN_SECRET_KEY is None, X-Admin-Key requests are rejected with 403.
    """
    monkeypatch.setattr(settings, "ADMIN_SECRET_KEY", None)
    response = client.post(
        "/api/v1/health/migrate",
        headers={"X-Admin-Key": "some-key"},
    )
    assert response.status_code == 403
    assert "Administrative key authorization is not configured" in response.json().get("detail", "")


def test_invalid_bearer_token_returns_401(client):
    """
    Verifies that requests with an invalid Bearer token receive HTTP 401 Unauthorized.
    """
    response = client.post(
        "/api/v1/health/migrate",
        headers={"Authorization": "Bearer invalid.token.value"},
    )
    assert response.status_code == 401
    assert "Could not validate credentials" in response.json().get("detail", "")


def test_health_endpoints_remain_public_and_healthy(client):
    """
    Verifies that normal GET health, readiness, and diagnostics endpoints remain
    fully accessible without credentials.
    """
    resp_health = client.get("/api/v1/health")
    assert resp_health.status_code == 200
    assert resp_health.json()["status"] == "ok"
    assert resp_health.json()["app"] == "Cogniva"

    resp_diag = client.get("/api/v1/health/diagnostics")
    assert resp_diag.status_code == 200
    diag_data = resp_diag.json()
    assert "models" in diag_data
    assert "database" in diag_data

    # Ensure no internal database table list is exposed in health responses
    assert "tables" not in resp_health.json()
    assert "tables" not in resp_diag.json()


def test_valid_admin_key_does_not_expose_schema_tables(client, monkeypatch):
    """
    Verifies that authorized migration execution never dumps database catalog/table list.
    """
    monkeypatch.setattr(settings, "ADMIN_SECRET_KEY", "valid-test-admin-key")
    from unittest.mock import MagicMock
    from alembic import command
    monkeypatch.setattr(command, "upgrade", MagicMock())

    from app.core.database import Base
    monkeypatch.setattr(Base.metadata, "create_all", MagicMock())

    response = client.post(
        "/api/v1/health/migrate",
        headers={"X-Admin-Key": "valid-test-admin-key"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "tables" not in data
    assert data["status"] == "completed"
