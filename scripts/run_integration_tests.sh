#!/usr/bin/env bash
# ==============================================================================
# Cogniva Zero-Cost Local Integration Test Suite Runner (Bash / CI)
# ==============================================================================
set -euo pipefail

echo "=========================================================="
echo " Cogniva Zero-Cost Local Integration Test Suite Runner     "
echo "=========================================================="

# 1. Start isolated test container
echo "[1/4] Spawning isolated pgvector test container (tmpfs RAM)..."
docker compose -f docker-compose.test.yml up -d db_test

cleanup() {
    echo ""
    echo "Cleaning up test container and ephemeral storage..."
    docker compose -f docker-compose.test.yml down -v --remove-orphans || true
    echo "Clean teardown completed successfully."
}
trap cleanup EXIT

# 2. Wait for database readiness
echo "[2/4] Waiting for test database to become healthy..."
retries=20
until [ "$(docker inspect --format='{{.State.Health.Status}}' cogniva-db-test 2>/dev/null)" = "healthy" ]; do
    retries=$((retries - 1))
    if [ "$retries" -le 0 ]; then
        echo "Error: Test PostgreSQL container failed to report healthy within 20s."
        exit 1
    fi
    sleep 1
done
echo "Test database is healthy and ready on localhost:5432."

# 3. Configure test environment variables (strictly isolated to cogniva_test)
echo "[3/4] Configuring isolated test environment variables..."
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

# 4. Run Pytest Suite
echo "[4/4] Executing backend test suite (unit + live pgvector integration)..."
cd backend
if [ -d ".venv" ]; then
    .venv/bin/pytest -v --durations=10
else
    pytest -v --durations=10
fi
