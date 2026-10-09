from fastapi import APIRouter
from app.api.v1.health import router as health_router
from app.api.v1.auth import router as auth_router
from app.api.v1.documents import router as documents_router
from app.api.v1.retrieval import router as retrieval_router
from app.api.v1.rag import router as rag_router
from app.api.v1.chat import router as chat_router

api_router = APIRouter()

# Include v1 route modules
api_router.include_router(health_router, prefix="", tags=["health"])
api_router.include_router(auth_router)
api_router.include_router(documents_router)
api_router.include_router(retrieval_router)
api_router.include_router(rag_router)
api_router.include_router(chat_router)
