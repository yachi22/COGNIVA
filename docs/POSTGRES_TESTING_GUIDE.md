# Zero-Cost PostgreSQL + pgvector Local Integration Testing Guide

**Author:** Cogniva Platform Engineering  
**Version:** v0.1.6  
**Infrastructure Cost:** $0.00 (Zero-Additional-Cost)

---

## 1. Overview

In Phase 16, the backend test suite reported 57 skipped tests during offline local execution. These tests (`test_auth.py`, `test_conversations.py`, `test_database.py`, `test_documents.py`, `test_rag.py`, `test_retrieval.py`) require a live PostgreSQL daemon with the `pgvector` extension.

This guide provides an automated, zero-cost testing workflow using Docker Compose and `pgvector/pgvector:pg16` mounted on in-memory `tmpfs`.

---

## 2. Test Architecture & Isolation Guarantees

```
+---------------------------------------------------------------------------------------------------+
|                        LOCAL INTEGRATION TEST ISOLATION ARCHITECTURE                              |
+---------------------------------------------------------------------------------------------------+
| Host: Local Developer Workstation or GitHub Actions CI Runner                                    |
| Container: `cogniva-db-test` (Image: pgvector/pgvector:pg16)                                     |
| Database Name: `cogniva_test` (Strictly separated from development `cogniva` and production)      |
| Storage: `tmpfs: /var/lib/postgresql/data` (RAM-backed, ultra-fast, zero disk residual)          |
| Teardown: Automated post-test trap wipes container and temporary database volume                   |
+---------------------------------------------------------------------------------------------------+
```

### Key Guarantees:
1. **Zero Connection to Production:** Tests exclusively point to `localhost:5432/cogniva_test`. Production credentials or connection strings are never touched.
2. **Deterministic Seed State:** Each test suite execution starts with a clean, freshly migrated database schema via Alembic.
3. **Instant Cleanup:** Because the container uses `tmpfs`, all table data resides in RAM and is completely erased upon container exit.

---

## 3. Quick Start: One-Command Execution

### On Windows (PowerShell):
```powershell
.\scripts\run_integration_tests.ps1
```

### On Linux, macOS, or CI (Bash):
```bash
chmod +x ./scripts/run_integration_tests.sh
./scripts/run_integration_tests.sh
```

---

## 4. Manual Step-by-Step Execution

If you prefer to run the steps manually:

### Step 1: Start Isolated Test Container
```bash
docker compose -f docker-compose.test.yml up -d db_test
```

### Step 2: Set Test Environment Variables
**PowerShell:**
```powershell
$env:DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/cogniva_test"
$env:POSTGRES_DB = "cogniva_test"
$env:ENVIRONMENT = "test"
$env:EMBEDDING_PROVIDER = "mock"
$env:LLM_PROVIDER = "mock"
$env:SECRET_KEY = "test-secret-key-for-local-integration-tests"
```

**Bash:**
```bash
export DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/cogniva_test"
export POSTGRES_DB="cogniva_test"
export ENVIRONMENT="test"
export EMBEDDING_PROVIDER="mock"
export LLM_PROVIDER="mock"
export SECRET_KEY="test-secret-key-for-local-integration-tests"
```

### Step 3: Run Pytest Suite
```bash
cd backend
python -m pytest -v --durations=10
```

### Step 4: Teardown Test Container
```bash
docker compose -f docker-compose.test.yml down -v
```

---

## 5. CI/CD Integration (GitHub Actions)

Add this job snippet to `.github/workflows/backend-tests.yml`:

```yaml
jobs:
  integration-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Start PostgreSQL with pgvector
        run: docker compose -f docker-compose.test.yml up -d db_test

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: "poetry"

      - name: Run Test Suite
        env:
          DATABASE_URL: postgresql+asyncpg://postgres:postgres@localhost:5432/cogniva_test
          POSTGRES_DB: cogniva_test
          ENVIRONMENT: test
        run: |
          cd backend
          poetry run pytest -v --durations=10

      - name: Stop Test Container
        if: always()
        run: docker compose -f docker-compose.test.yml down -v
```
