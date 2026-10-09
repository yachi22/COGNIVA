#!/bin/sh
set -e

echo "=== Cogniva Production Backend Startup ==="

# Execute database migrations if DATABASE_URL is set
if [ -n "$DATABASE_URL" ]; then
    echo "Applying Alembic database migrations..."
    alembic upgrade head || {
        echo "CRITICAL: Alembic database migration failed. Halting application startup."
        exit 1
    }
fi

PORT="${PORT:-8000}"
echo "Starting Uvicorn on 0.0.0.0:$PORT..."
exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
