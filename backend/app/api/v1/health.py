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
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        db_status = "unavailable"

    return {
        "status": "ok" if db_status == "connected" else "degraded",
        "database": db_status,
        "app": settings.PROJECT_NAME,
        "environment": settings.ENVIRONMENT,
    }
