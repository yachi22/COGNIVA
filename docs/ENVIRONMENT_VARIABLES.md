# Cogniva Environment Variable Reference

This document provides a reference of all configuration options for Cogniva. **Never commit actual production secrets to source control.**

---

## 1. Core Server Settings

| Variable | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `PROJECT_NAME` | string | `Cogniva` | Project title displayed in API responses and docs. |
| `VERSION` | string | `0.1.5` | Application semantic version. |
| `API_V1_STR` | string | `/api/v1` | URL prefix for v1 endpoints. |
| `HOST` | string | `0.0.0.0` | Host IP for ASGI server binding. |
| `PORT` | integer | `8000` | Port for ASGI server binding (Render injects `$PORT`). |
| `ENVIRONMENT` | string | `development` | Deployment environment: `development`, `testing`, `production`. |
| `DEBUG` | boolean | `True` | Enables Swagger UI and verbose logs. Auto-disabled in production. |
| `CORS_ORIGINS` | string / list | `http://localhost:5173,...` | Allowed CORS origins (e.g. `https://cogniva-gules.vercel.app`). |

---

## 2. Database & Vector Storage (PostgreSQL + pgvector)

| Variable | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `DATABASE_URL` | string | `None` | PostgreSQL connection URL (`postgresql+asyncpg://user:pass@host:5432/db`). |
| `POSTGRES_HOST` | string | `localhost` | Fallback host when `DATABASE_URL` is omitted. |
| `POSTGRES_PORT` | integer | `5432` | Fallback port. |
| `POSTGRES_DB` | string | `cogniva` | Fallback database name. |
| `POSTGRES_USER` | string | `postgres` | Fallback user. |
| `POSTGRES_PASSWORD`| string | `postgres` | Fallback password. |

---

## 3. Authentication & Security (JWT)

| Variable | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `SECRET_KEY` | string | `cogniva-super-secret...` | 64-char hex key for signing HS256 JWT tokens. Must be changed in production. |
| `ALGORITHM` | string | `HS256` | JWT signing algorithm. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | integer | `1440` | JWT expiration duration in minutes (24 hours). |

---

## 4. Storage & Uploads (Zero-Budget Local vs. Cloud S3/R2)

| Variable | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `STORAGE_PROVIDER` | string | `local` | `local` for zero-budget local disk, or `s3` / `r2` for cloud object storage. |
| `STORAGE_DIR` | string | `storage` | Local directory for cached files. |
| `MAX_UPLOAD_SIZE_MB`| integer | `50` | Maximum file upload size in megabytes. |
| `ALLOWED_EXTENSIONS`| list | `["pdf", "docx", "csv"]`| Permitted file extensions. |
| `S3_BUCKET_NAME` | string | `None` | Optional S3/R2 bucket name. When omitted, defaults to zero-budget local storage. |
| `S3_ENDPOINT_URL` | string | `None` | Optional custom endpoint URL for Cloudflare R2 / MinIO. |
| `S3_REGION_NAME` | string | `us-east-1` | S3 region identifier. |
| `S3_ACCESS_KEY_ID` | string | `None` | Cloud storage access key ID. |
| `S3_SECRET_ACCESS_KEY` | string | `None` | Cloud storage secret key. |
| `S3_SIGNED_URL_EXPIRATION_SECONDS` | integer | `900` | Expiration duration for presigned URLs (15 minutes). |

---

## 5. Embeddings & Semantic Retrieval

| Variable | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `EMBEDDING_PROVIDER` | string | `openai` | Embedding provider: `openai` or `mock`. |
| `EMBEDDING_MODEL` | string | `text-embedding-3-small` | Model identifier for vector generation. |
| `EMBEDDING_DIMENSION`| integer | `1536` | Vector embedding dimension for pgvector index. |
| `EMBEDDING_BATCH_SIZE`| integer | `64` | Maximum chunk batch size per embedding request. |
| `OPENAI_API_KEY` | string | `None` | API key for OpenAI services. |
| `OPENAI_BASE_URL` | string | `None` | Optional OpenAI custom base URL. |
| `DEFAULT_RETRIEVAL_TOP_K` | integer | `5` | Default number of top semantic chunks returned. |
| `MAX_RETRIEVAL_TOP_K` | integer | `20` | Hard upper limit on retrieval chunk count. |

---

## 6. LLM & Grounded RAG Synthesis

| Variable | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `LLM_PROVIDER` | string | `openai` | LLM generation provider: `openai` or `mock`. |
| `LLM_MODEL` | string | `gpt-4o-mini` | Generation model identifier. |
| `LLM_TEMPERATURE` | float | `0.0` | Sampling temperature (0.0 for deterministic factual grounding). |
| `LLM_MAX_TOKENS` | integer | `1000` | Maximum output generation token limit. |
| `MAX_CONTEXT_CHARS`| integer | `8000` | Context character budget limit to prevent prompt overflows. |

---

## 7. Background Job Processing (Phase 12 Zero-Budget)

| Variable | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `DOCUMENT_PROCESSING_TIMEOUT_SECONDS` | integer | `300` | Hard deadline before marking stalled jobs as timed out. |
| `DOCUMENT_PROCESSING_MAX_RETRIES` | integer | `3` | Maximum retry attempts on transient failures. |
| `DOCUMENT_PROCESSING_BASE_BACKOFF_SECONDS` | float | `1.5` | Exponential backoff multiplier base. |
