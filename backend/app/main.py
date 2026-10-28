import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from app.core.config import settings
from app.api.v1 import api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager that ensures database migrations and all registered
    tables exist safely on application startup without dropping existing data.
    """
    try:
        from alembic.config import Config
        from alembic import command
        alembic_ini = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
        if os.path.exists(alembic_ini):
            alembic_cfg = Config(alembic_ini)
            command.upgrade(alembic_cfg, "head")
            print("Alembic upgrade head executed successfully.")
    except Exception as exc:
        print(f"Alembic auto-upgrade notice: {exc}")

    try:
        from app.core.database import Base, async_engine
        import app.models  # noqa: F401
        async with async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("Base.metadata.create_all verified.")
    except Exception as exc:
        print(f"Base.metadata.create_all notice: {exc}")

    try:
        from app.core.database import AsyncSessionLocal
        from app.services.job_service import document_job_service
        async with AsyncSessionLocal() as db:
            recovery_report = await document_job_service.recover_interrupted_jobs(db)
            print(f"Startup document job recovery completed: {recovery_report}")
    except Exception as exc:
        print(f"Startup document job recovery notice: {exc}")

    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    description=settings.DESCRIPTION,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs" if settings.DEBUG else None,
    redoc_url=f"{settings.API_V1_STR}/redoc" if settings.DEBUG else None,
    lifespan=lifespan,
)

# Configure CORS safely for frontend access
cors_origins = [origin.strip() for origin in settings.CORS_ORIGINS if origin.strip() and origin.strip() != "*"]
if not cors_origins and settings.ENVIRONMENT != "production":
    cors_origins = ["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API v1 routes
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/", tags=["root"])
async def root():
    """
    Root endpoint returning service identity and navigation links.
    """
    return {
        "project": settings.PROJECT_NAME,
        "tagline": "Understand. Retrieve. Analyze. Act.",
        "version": settings.VERSION,
        "docs": f"{settings.API_V1_STR}/docs" if settings.DEBUG else "Disabled in production",
        "health": f"{settings.API_V1_STR}/health",
    }


if __name__ == "__main__":
    port = int(os.getenv("PORT", settings.PORT))
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=port,
        reload=settings.DEBUG,
    )
