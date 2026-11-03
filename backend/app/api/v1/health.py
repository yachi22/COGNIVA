import logging
import os
from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_db, require_admin_access
from app.core.config import settings
from app.core.logging_config import get_correlation_id
from app.core.sanitizer import sanitize_error_detail
from app.services.storage_service import storage_service

router = APIRouter()
logger = logging.getLogger("cogniva.health")


@router.get("/health", tags=["health"])
async def get_health():
    """
    Liveness health check endpoint verifying application process availability.
    Returns HTTP 200 independent of database connectivity.
    """
    commit = os.environ.get("RENDER_GIT_COMMIT") or "latest"
    return {
        "status": "ok",
        "app": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "commit": commit,
        "correlation_id": get_correlation_id(),
    }


@router.get("/health/ready", tags=["health"])
async def get_readiness(response: Response, db: AsyncSession = Depends(get_db)):
    """
    Readiness health check verifying PostgreSQL database connectivity.
    Distinguishes application availability from database unavailability:
    - Returns HTTP 200 when database is responsive.
    - Returns HTTP 503 Service Unavailable when database connection fails.
    Error details are bounded and strictly sanitized to prevent credential leakage.
    """
    db_status = "connected"
    detail = None
    try:
        await db.execute(text("SELECT 1"))
    except Exception as exc:
        orig = getattr(exc, "orig", None)
        root_cause = orig if orig is not None else exc
        err_type = type(root_cause).__name__

        # Bounded and sanitized error message
        sanitized_msg = sanitize_error_detail(str(root_cause), max_length=200)

        # Extract target host safely without credentials for connection troubleshooting
        target_info = ""
        try:
            from sqlalchemy.engine.url import make_url
            u = make_url(settings.async_database_url)
            if u.host:
                target_info = f" (target: {u.host}:{u.port})"
        except Exception:
            pass

        detail = f"{err_type}: {sanitized_msg}{target_info}".strip(": ")
        logger.error("Database readiness check failed: %s", detail)
        db_status = "unavailable"
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    res_body = {
        "status": "ok" if db_status == "connected" else "unhealthy",
        "database": db_status,
        "storage": storage_service.provider.provider_name,
        "storage_durable": storage_service.provider.is_durable,
        "app": settings.PROJECT_NAME,
        "environment": settings.ENVIRONMENT,
        "correlation_id": get_correlation_id(),
    }
    if detail:
        res_body["detail"] = detail
    return res_body


@router.get("/health/diagnostics", tags=["health"])
async def get_health_diagnostics(db: AsyncSession = Depends(get_db)):
    """
    Safe operational diagnostics endpoint providing system overview without
    revealing credentials, API keys, or tenant data.
    """
    db_ok = False
    try:
        await db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    commit = os.environ.get("RENDER_GIT_COMMIT") or "latest"
    return {
        "status": "healthy" if db_ok else "degraded",
        "app": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "commit": commit,
        "environment": settings.ENVIRONMENT,
        "database": {
            "status": "connected" if db_ok else "unavailable",
            "dialect": "postgresql+asyncpg",
        },
        "storage": {
            "provider": storage_service.provider.provider_name,
            "durable": storage_service.provider.is_durable,
        },
        "models": {
            "embedding_provider": settings.EMBEDDING_PROVIDER,
            "embedding_model": settings.EMBEDDING_MODEL,
            "embedding_dimension": settings.EMBEDDING_DIMENSION,
            "llm_provider": settings.LLM_PROVIDER,
            "llm_model": settings.LLM_MODEL,
        },
        "processing_limits": {
            "timeout_seconds": settings.DOCUMENT_PROCESSING_TIMEOUT_SECONDS,
            "max_retries": settings.DOCUMENT_PROCESSING_MAX_RETRIES,
            "max_concurrency": settings.DOCUMENT_PROCESSING_MAX_CONCURRENCY,
        },
        "correlation_id": get_correlation_id(),
    }


@router.post(
    "/health/migrate",
    tags=["health"],
    dependencies=[Depends(require_admin_access)],
    summary="Trigger administrative database migrations",
    description="Ensures Alembic migrations and required schema tables exist. Strictly restricted to authorized administrators.",
)
async def run_db_migrations(db: AsyncSession = Depends(get_db)):
    """
    Ensures Alembic migrations and required schema tables are up to date.
    Strictly protected: requires valid administrative authorization (X-Admin-Key or Superuser).
    Schema details are never exposed to prevent information disclosure.
    """
    status_report = {}

    # 1. Alembic upgrade head
    try:
        from alembic.config import Config
        from alembic import command
        alembic_ini = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "alembic.ini"))
        if os.path.exists(alembic_ini):
            alembic_cfg = Config(alembic_ini)
            command.upgrade(alembic_cfg, "head")
            status_report["alembic"] = "success"
        else:
            status_report["alembic"] = "skipped"
    except Exception as exc:
        status_report["alembic"] = "error"
        logger.error(f"Administrative migration error: {sanitize_error_detail(str(exc))}")

    # 2. Base.metadata.create_all fallback
    try:
        from app.core.database import Base, async_engine
        import app.models  # noqa: F401
        async with async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        status_report["create_all"] = "success"
    except Exception as exc:
        status_report["create_all"] = "error"
        logger.error(f"Base.metadata.create_all error: {sanitize_error_detail(str(exc))}")

    # Clean, non-disclosing operational response without dumping database catalog
    return {
        "status": "completed",
        "alembic": status_report.get("alembic", "skipped"),
        "create_all": status_report.get("create_all", "skipped"),
    }


@router.post(
    "/health/migrate-storage",
    tags=["health"],
    dependencies=[Depends(require_admin_access)],
    summary="Trigger administrative storage migration",
    description="Migrates document binaries from ephemeral disk to durable object storage. Strictly restricted to authorized administrators.",
)
async def run_storage_migration(db: AsyncSession = Depends(get_db)):
    """
    Idempotent and resumable storage migration endpoint.
    Strictly protected: requires valid administrative authorization (X-Admin-Key or Superuser).
    Safely migrates documents from ephemeral disk to durable object storage (S3/R2)
    after verifying byte integrity, preserving all database chunks and vector indices.
    """
    from app.services.storage_service import storage_service
    from app.services.storage.migration import storage_migration_service

    if not storage_service.provider.is_durable:
        return {
            "status": "noop",
            "message": "Active storage provider is local ephemeral disk. Configure S3/R2 credentials and STORAGE_PROVIDER to migrate.",
            "current_provider": storage_service.provider.provider_name,
            "is_durable": False,
        }

    migration_report = await storage_migration_service.migrate_all_documents(
        db=db,
        target_provider=storage_service.provider,
        local_provider=storage_service.local_provider,
    )
    return {
        "status": "completed",
        "provider": storage_service.provider.provider_name,
        "is_durable": True,
        "report": migration_report,
    }

