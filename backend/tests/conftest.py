import pytest
from app.services.embeddings import embedding_service, MockEmbeddingProvider
from app.services.llm import llm_service, MockLLMProvider
from app.core.rate_limiter import auth_limiter, upload_limiter, llm_limiter
from app.main import app


@pytest.fixture(autouse=True)
def reset_rate_limiters():
    """
    Clears in-memory sliding-window rate limit history between test runs,
    preventing cross-test starvation and 429 Too Many Requests errors.
    """
    auth_limiter.reset()
    upload_limiter.reset()
    llm_limiter.reset()
    yield
    auth_limiter.reset()
    upload_limiter.reset()
    llm_limiter.reset()


# Install test-only middleware ensuring calls to /documents/{id}/process
# without an explicit background query param default to synchronous execution
# as expected by Phase 2-6 test suites.
if not getattr(app.state, "_test_sync_proc_installed", False):
    @app.middleware("http")
    async def _test_ensure_sync_process(request, call_next):
        if request.method == "POST" and b"/documents/" in request.scope.get("path", "").encode() and request.scope.get("path", "").endswith("/process"):
            qs = request.scope.get("query_string", b"")
            if b"background=" not in qs:
                request.scope["query_string"] = qs + (b"&" if qs else b"") + b"background=false"
        return await call_next(request)
    app.state._test_sync_proc_installed = True


@pytest.fixture(autouse=True)
def setup_mock_embedding_provider():
    """
    Autouse fixture to ensure all automated test runs use the deterministic
    MockEmbeddingProvider by default, preventing external API calls and
    guaranteeing reliable, fast 1536-dimensional vector generation.
    """
    mock_provider = MockEmbeddingProvider()
    embedding_service.set_provider(mock_provider)
    yield mock_provider
    embedding_service.reset_default_provider()


@pytest.fixture(autouse=True)
def setup_mock_llm_provider():
    """
    Autouse fixture to ensure all automated test runs use the deterministic
    MockLLMProvider by default, preventing external API calls and
    guaranteeing reliable, fast grounded answer synthesis.
    """
    mock_provider = MockLLMProvider()
    llm_service.set_provider(mock_provider)
    yield mock_provider
    llm_service.reset_default_provider()


def is_postgres_available() -> bool:
    """Checks if a PostgreSQL instance is reachable on localhost:5432."""
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.5)
        res = s.connect_ex(("localhost", 5432))
        s.close()
        return res == 0
    except Exception:
        return False


def pytest_collection_modifyitems(config, items):
    """
    Ensures developer and CI offline runs skip raw socket PostgreSQL integration
    tests gracefully when no local database daemon is active.
    """
    if not is_postgres_available():
        import inspect
        skip_pg = pytest.mark.skip(
            reason="Live PostgreSQL daemon is not reachable on localhost:5432. Active database service required for live integration tests."
        )
        live_db_test_files = {
            "test_auth.py",
            "test_conversations.py",
            "test_database.py",
            "test_documents.py",
            "test_rag.py",
            "test_retrieval.py",
        }

        exempt_files = {"test_migration_security.py", "test_security_hardening.py"}

        for item in items:
            filename = str(item.fspath.basename) if hasattr(item, "fspath") else ""
            if filename in exempt_files:
                continue
            if filename in live_db_test_files:
                item.add_marker(skip_pg)
                continue

            func = getattr(item, "obj", None)
            if func:
                try:
                    src = inspect.getsource(func)
                    if "ASGITransport" in src or "AsyncSessionLocal" in src or "async_engine" in src or "client.post(" in src or "client.get(" in src:
                        item.add_marker(skip_pg)
                except Exception:
                    pass





