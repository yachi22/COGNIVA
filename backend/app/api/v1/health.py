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
        # Extract target host safely without credentials to help diagnose DNS/host resolution issues
        target_info = ""
        try:
            from sqlalchemy.engine.url import make_url
            u = make_url(settings.async_database_url)
            if u.host:
                target_info = f" (target: {u.host}:{u.port})"
        except Exception:
            pass

        detail = f"{err_type}: {sanitized_msg}{target_info}".strip(": ")

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


@router.post("/health/migrate", tags=["health"])
async def run_db_migrations(db: AsyncSession = Depends(get_db)):
    """
    Ensures Alembic migrations and required schema tables are up to date.
    Safe and idempotent.
    """
    import os
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
            status_report["alembic"] = f"ini_not_found at {alembic_ini}"
    except Exception as exc:
        status_report["alembic_error"] = str(exc)

    # 2. Base.metadata.create_all fallback
    try:
        from app.core.database import Base, async_engine
        import app.models  # noqa: F401
        async with async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        status_report["create_all"] = "success"
    except Exception as exc:
        status_report["create_all_error"] = str(exc)

    # 3. Check existing tables in public schema
    try:
        res = await db.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name"))
        status_report["tables"] = [row[0] for row in res.fetchall()]
    except Exception as exc:
        status_report["table_check_error"] = str(exc)

    # 4. Safe read-only inspection of ElderShield documents & evaluation chunks
    try:
        doc_res = await db.execute(text("SELECT id, filename, original_filename, status, user_id FROM documents WHERE original_filename ILIKE '%ElderShield%' OR filename ILIKE '%ElderShield%'"))
        docs_data = []
        for d in doc_res.fetchall():
            doc_id, fn, ofn, st, uid = d
            chunk_res = await db.execute(text(f"SELECT id, chunk_index, page_number, content FROM document_chunks WHERE document_id = '{doc_id}' ORDER BY chunk_index ASC"))
            all_chunks = chunk_res.fetchall()
            matching_chunks = []
            for c in all_chunks:
                cid, cidx, pnum, content = c
                lower_c = content.lower()
                if any(k in lower_c for k in ("evaluat", "precision", "recall", "assessed", "simple language", "representative")):
                    matching_chunks.append({
                        "id": str(cid),
                        "chunk_index": cidx,
                        "page_number": pnum,
                        "content_snippet": content[:300],
                        "has_evaluation_passage": "precision" in lower_c and "recall" in lower_c,
                        "has_simple_language": "simple language" in lower_c,
                    })
            docs_data.append({
                "document_id": str(doc_id),
                "filename": fn,
                "original_filename": ofn,
                "status": st,
                "user_id": str(uid),
                "total_chunks": len(all_chunks),
                "matching_chunks": matching_chunks,
            })
        status_report["eldershield_docs"] = docs_data
    except Exception as exc:
        status_report["eldershield_doc_error"] = str(exc)

    return status_report

