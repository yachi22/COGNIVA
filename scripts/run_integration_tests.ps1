<#
.SYNOPSIS
  Zero-Cost Automated PostgreSQL + pgvector Test Runner for Windows (PowerShell)
.DESCRIPTION
  1. Spawns isolated ephemeral pgvector test container via docker-compose.test.yml
  2. Waits for PostgreSQL readiness
  3. Sets isolated test environment variables pointing to 'cogniva_test'
  4. Runs complete backend pytest suite with duration profiling
  5. Tears down test container and wipes tmpfs RAM database
#>

param(
    [switch]$KeepContainer = $false
)

$ErrorActionPreference = "Stop"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " Cogniva Zero-Cost Local Integration Test Suite Runner     " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Start isolated test container
Write-Host "`n[1/4] Spawning isolated pgvector test container (tmpfs RAM)..." -ForegroundColor Yellow
docker compose -f docker-compose.test.yml up -d db_test

try {
    # 2. Wait for database readiness
    Write-Host "[2/4] Waiting for test database to become healthy..." -ForegroundColor Yellow
    $retries = 20
    $healthy = $false
    while ($retries -gt 0) {
        $status = docker inspect --format="{{.State.Health.Status}}" cogniva-db-test 2>$null
        if ($status -eq "healthy") {
            $healthy = $true
            break
        }
        Start-Sleep -Seconds 1
        $retries--
    }

    if (-not $healthy) {
        throw "Test PostgreSQL container failed to report healthy within 20 seconds."
    }
    Write-Host "Test database is healthy and ready on localhost:5432." -ForegroundColor Green

    # 3. Configure test environment variables (strictly isolated to cogniva_test)
    Write-Host "[3/4] Configuring isolated test environment variables..." -ForegroundColor Yellow
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

    # 4. Run Pytest Suite
    Write-Host "[4/4] Executing backend test suite (unit + live pgvector integration)..." -ForegroundColor Yellow
    Push-Location backend
    try {
        .\.venv\Scripts\python.exe -m pytest -v --durations=10
    } finally {
        Pop-Location
    }
} finally {
    if (-not $KeepContainer) {
        Write-Host "`nCleaning up test container and ephemeral storage..." -ForegroundColor Yellow
        docker compose -f docker-compose.test.yml down -v --remove-orphans
        Write-Host "Clean teardown completed successfully." -ForegroundColor Green
    } else {
        Write-Host "`nContainer kept alive for debugging (cogniva-db-test)." -ForegroundColor Magenta
    }
}

