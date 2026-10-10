from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_db
from app.core.config import settings

router = APIRouter()


@router.get("/health", tags=["health"])
async def get_health():
    """
    Liveness health check endpoint to verify backend service availability.
    Returns status: ok as required by specification.
    """
    return {
        "status": "ok",
        "app": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
    }


@router.get("/health/ready", tags=["health"])
async def get_readiness(db: AsyncSession = Depends(get_db)):
    """
    Readiness health check verifying PostgreSQL connectivity.
    Executes SELECT 1 without exposing internal connection strings or credentials.
    """
    db_status = "connected"
    detail = None
    try:
        await db.execute(text("SELECT 1"))
    except Exception as exc:
        import logging
        import re

        orig = getattr(exc, "orig", None)
        root_cause = orig if orig is not None else exc
        err_type = type(root_cause).__name__
        raw_msg = str(root_cause)

        # Sanitize error message to prevent credential or URL leakage
        sanitized_msg = re.sub(r"://[^@]+@", "://***@", raw_msg)
        sanitized_msg = re.sub(r"password=[^\s&]+", "password=***", sanitized_msg, flags=re.IGNORECASE)
        sanitized_msg = sanitized_msg.splitlines()[0] if sanitized_msg else ""
        detail = f"{err_type}: {sanitized_msg}".strip(": ")

        # Log to uvicorn.error so Render console logs capture the exact failure
        logging.getLogger("uvicorn.error").error(
            "Database readiness check failed: %s",
            detail,
        )
        db_status = "unavailable"

    response = {
        "status": "ok" if db_status == "connected" else "degraded",
        "database": db_status,
        "app": settings.PROJECT_NAME,
        "environment": settings.ENVIRONMENT,
    }
    if detail:
        response["detail"] = detail
    return response
