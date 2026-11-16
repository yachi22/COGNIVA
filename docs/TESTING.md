# Cogniva Automated Testing & Quality Assurance Guide

**Author:** Cogniva Platform Engineering  
**Version:** v1.0.0  
**Status:** 100% Pass Rate (Phase 16.3 Verification)  

---

## 1. Executive Summary & Test Evidence

Cogniva enforces strict automated quality gates across backend logic, database persistence, vector similarity retrieval, RAG answer synthesis, security boundaries, and frontend type safety.

In Phase 16.3, the entire backend automated test suite was executed against an isolated ephemeral PostgreSQL instance with the `pgvector` extension:

```
===================================================================================================
                                PHASE 16.3 TEST EXECUTION EVIDENCE
===================================================================================================
Total Tests Discovered:        160
Tests Passed:                  160 (100%)
Tests Failed:                  0
Tests Skipped:                 0 (All 57 previously skipped DB tests executed and passed)
Errors:                        0
Total Execution Duration:      194.94 seconds (3 minutes, 14 seconds)
Frontend TypeScript Check:     0 errors (Clean tsc --noEmit)
Frontend Production Build:     Pass (Vite built 1,695 modules in 50.49s)
Ephemeral Storage Teardown:    Verified clean (tmpfs RAM database wiped instantly)
===================================================================================================
```

---

## 2. Test Architecture: Local Integration vs. Production Smoke Testing

Cogniva strictly distinguishes **Local Integration Testing** from **Production Smoke Testing** to guarantee that development and CI testing cannot impact or contaminate live production systems.

```
+---------------------------------------------------------------------------------------------------+
|                                  TESTING ARCHITECTURE COMPARISON                                  |
+---------------------------------------------------------------------------------------------------+
| Feature / Characteristic      | Local Integration Suite           | Production Smoke Suite        |
+---------------------------------------------------------------------------------------------------+
| Target Environment            | Localhost / Docker (RAM tmpfs)    | Cloud Deployment (Render)     |
| Target Database               | cogniva_test (Ephemeral pgvector) | Cloud PostgreSQL (Supabase)   |
| Database Storage              | tmpfs (RAM, zero disk residue)    | Cloud Managed Persistent Disk |
| LLM / Embedding Providers     | Deterministic Mock Providers      | OpenAI / Mock Production      |
| Cloud Infrastructure Cost     | $0.00 (Zero-Additional-Cost)      | $0.00 (Free Tier Monitoring)  |
| Destructive Operations        | Permitted (Isolated Test DB)      | STRICTLY FORBIDDEN            |
| Schema Migrations             | Fresh Alembic upgrade head        | Pre-deployed production state |
| Test Runner Command           | .\scripts\run_integration_tests   | python verify_phase15_accept  |
+---------------------------------------------------------------------------------------------------+
```

### 2.1 Local Integration Testing
- **Goal:** Exercise 100% of the backend codebase—including raw SQL queries, pgvector cosine distance operations, multi-table joins, background job scheduling, rate limiting, and HTTP middleware pipelines.
- **Isolation:** Spawns an ephemeral `pgvector/pgvector:pg16` Docker container (`cogniva-db-test`) with storage mounted exclusively on `tmpfs` (RAM). All data resides in volatile memory and is instantly erased upon container exit.
- **Zero Cost:** Requires no paid cloud accounts, no API credits, and no third-party services. Uses deterministic `MockEmbeddingProvider` and `MockLLMProvider`.

### 2.2 Production Smoke & Acceptance Testing
- **Goal:** Verify that deployed cloud services (Render API gateway, Cloudflare WAF, production database) are online, healthy, and correctly configured.
- **Safety Invariants:**
  - Never drops, migrates, or truncates production tables.
  - Test accounts use ephemeral random email addresses and are audited.
  - Checks health probes (`/health`, `/health/ready`), CORS headers, HSTS enforcement, and migration endpoint lockdown (`HTTP 401 Unauthorized`).

---

## 3. Test Suite Breakdown by Module

The 160 backend integration tests are distributed across 17 specialized test modules:

| Test Module | Tests | Focus Area & Verified Capabilities |
| :--- | :---: | :--- |
| `tests/test_database.py` | 4 | PostgreSQL connection, `vector` extension (v0.8.7) registration, ORM model CRUD, and `/health` database check. |
| `tests/test_auth.py` | 4 | User registration, 12-round bcrypt password hashing, duplicate email rejection, JWT login, and bearer token resolution. |
| `tests/test_documents.py` | 3 | Multi-part document upload, synchronous and asynchronous processing, document metadata listing, and cascade deletion. |
| `tests/test_extraction.py` | 4 | Format extraction engines: PyMuPDF for PDF page tokens, python-docx for DOCX paragraphs, and CSV row serialization. |
| `tests/test_chunking_embeddings.py` | 9 | Token-aware sliding-window chunking, overlap preservation, vector dimension validation (1536-dim), chunk persistence, and idempotent reprocessing. |
| `tests/test_retrieval.py` | 9 | PostgreSQL pgvector cosine distance retrieval (`<=>`), top-k ranking, similarity score thresholding, document scoping, and cross-tenant isolation. |
| `tests/test_rag.py` | 14 | Grounded answer synthesis, anti-prompt-injection boundary delimiters, insufficient evidence fallbacks, context budget truncation, and LLM error recovery. |
| `tests/test_citations.py` | 8 | Deterministic citation badge numbering (`[S1]`, `[S2]`), hallucinated citation ID rejection, source inspection endpoint, and tenant isolation. |
| `tests/test_conversations.py` | 9 | Persistent multi-turn chat threads, bounded conversation history in prompts, historical citation preservation, and conversation CRUD. |
| `tests/test_background_jobs.py` | 8 | In-process background worker, `document_jobs` state machine, bounded retries with exponential backoff, and startup recovery of interrupted jobs. |
| `tests/test_zero_budget_storage.py` | 9 | Local ephemeral disk storage, text reconstruction fallback from database chunks (`X-Cogniva-Recovered`), and cross-tenant download prevention. |
| `tests/test_durable_storage.py` | 5 | Storage abstraction layer, local vs. cloud storage provider configuration, and binary availability detection. |
| `tests/test_enterprise_features.py` | 27 | Document collections (folders), cross-document comparison, structured entity extraction, multi-section research reports, and deep query decomposition. |
| `tests/test_observability.py` | 20 | Correlation ID propagation (`X-Correlation-ID`), health/readiness probes, job duration metrics, tenant operational telemetry, and job diagnostics. |
| `tests/test_security_hardening.py` | 11 | Enterprise security headers (HSTS, CSP, nosniff, DENY), in-memory sliding-window rate limiters, magic bytes validation, path traversal neutralization, and credential scrubbing. |
| `tests/test_migration_security.py` | 13 | Administrative lockdown of database migration endpoints (`HTTP 401 Unauthorized`), schema introspection prevention, and authentication validation. |
| `tests/test_deployment.py` | 5 | Configuration normalization (CORS parsing, `postgresql+asyncpg://` protocol normalization, production secret key validation, and credential leak prevention). |
| **TOTAL** | **160** | **All 160 tests passing with 0 failures and 0 skips.** |

---

## 4. How to Run the Automated Tests

### 4.1 Running the Automated Test Runner (Recommended)

The test runner script automatically starts the isolated `cogniva-db-test` Docker container on `tmpfs`, waits for health readiness, runs Alembic migrations, executes all 160 tests with duration profiling, and cleanly tears down the container and ephemeral storage.

**On Windows (PowerShell):**
```powershell
.\scripts\run_integration_tests.ps1
```

**On Linux, macOS, or CI (Bash):**
```bash
chmod +x ./scripts/run_integration_tests.sh
./scripts/run_integration_tests.sh
```

### 4.2 Running Tests Manually

If you prefer to control container lifecycle and environment variables manually:

#### Step 1: Start Isolated pgvector Test Container
```bash
docker compose -f docker-compose.test.yml up -d db_test
```

#### Step 2: Configure Isolated Test Environment Variables
**PowerShell:**
```powershell
$env:DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/cogniva_test"
$env:POSTGRES_DB = "cogniva_test"
$env:POSTGRES_HOST = "localhost"
$env:POSTGRES_PORT = "5432"
$env:POSTGRES_USER = "postgres"
$env:POSTGRES_PASSWORD = "postgres"
$env:ENVIRONMENT = "test"
$env:STORAGE_PROVIDER = "local"
$env:EMBEDDING_PROVIDER = "mock"
$env:LLM_PROVIDER = "mock"
$env:SECRET_KEY = "test-secret-key-for-local-integration-tests"
```

**Bash:**
```bash
export DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/cogniva_test"
export POSTGRES_DB="cogniva_test"
export POSTGRES_HOST="localhost"
export POSTGRES_PORT="5432"
export POSTGRES_USER="postgres"
export POSTGRES_PASSWORD="postgres"
export ENVIRONMENT="test"
export STORAGE_PROVIDER="local"
export EMBEDDING_PROVIDER="mock"
export LLM_PROVIDER="mock"
export SECRET_KEY="test-secret-key-for-local-integration-tests"
```

#### Step 3: Run Database Schema Migrations
```bash
cd backend
python -m alembic upgrade head
```

#### Step 4: Execute Pytest
```bash
python -m pytest -v --durations=10
```

#### Step 5: Clean Teardown
```bash
cd ..
docker compose -f docker-compose.test.yml down -v --remove-orphans
```

---

## 5. Test Fixtures & Infrastructure Safeguards

The test environment includes several fixtures in `backend/tests/conftest.py` designed to ensure reliability, speed, and production safety:

1. **`reset_rate_limiters` Fixture (Autouse):**
   - Automatically invokes `.reset()` on `auth_limiter`, `upload_limiter`, and `llm_limiter` before and after each test.
   - Prevents cascading HTTP 429 errors from accumulating across hundreds of sequential test requests while keeping production rate limiting fully intact.

2. **`setup_mock_embedding_provider` & `setup_mock_llm_provider` Fixtures (Autouse):**
   - Injects `MockEmbeddingProvider` and `MockLLMProvider` for all automated test runs.
   - Prevents unexpected network requests or OpenAI API billing while guaranteeing deterministic 1536-dimensional vector generation.

3. **`_test_ensure_sync_process` Test Middleware:**
   - Defaults `POST /documents/{id}/process` requests without an explicit `background` query parameter to `background=false` during test sessions, ensuring tests that immediately query chunks execute synchronously without changing production's asynchronous default.

---

## 6. Frontend Quality Gates

The frontend application (`frontend/`) enforces strict static analysis and production bundling:

### 1. Static Type Checking
```bash
cd frontend
node .\node_modules\typescript\bin\tsc --noEmit
```
- **Result:** Zero TypeScript errors. All API client payloads, component props, and state models are strictly typed.

### 2. Production Bundle Compilation
```bash
cd frontend
node .\node_modules\vite\bin\vite.js build
```
- **Result:** Clean production distribution generated in `frontend/dist/` (1,695 modules transformed, gzipped JS ~118 kB, CSS ~6.8 kB).

