# Cogniva API Specification (v1)

Base URL: `https://cogniva-api.onrender.com/api/v1`

---

## 1. Authentication (`/auth`)

### `POST /auth/register`
Creates a new tenant user account.
- **Request Body**:
  ```json
  {
    "email": "user@example.com",
    "password": "StrongPassword123!",
    "full_name": "Jane Doe"
  }
  ```
- **Responses**:
  - `201 Created`: User created successfully.
  - `400 Bad Request`: Email already registered.
  - `429 Too Many Requests`: Rate limit exceeded (15 req/min).

### `POST /auth/login`
Authenticates credentials and returns a signed HS256 JWT bearer token.
- **Request Body**:
  ```json
  {
    "email": "user@example.com",
    "password": "StrongPassword123!"
  }
  ```
- **Responses**:
  - `200 OK`: `{"access_token": "...", "token_type": "bearer", "expires_in": 86400}`
  - `401 Unauthorized`: Invalid credentials.
  - `429 Too Many Requests`: Rate limit exceeded (15 req/min).

### `GET /auth/me`
Resolves authenticated user profile.
- **Headers**: `Authorization: Bearer <token>`
- **Responses**: `200 OK`: `{"id": "...", "email": "...", "full_name": "..."}`

---

## 2. Documents & Background Processing (`/documents`)

### `POST /documents`
Uploads a document (PDF, DOCX, CSV). Validates magic bytes and sanitizes filenames.
- **Form Data**: `file` (multipart file)
- **Query Params**: `auto_process` (boolean, default false)
- **Responses**: `201 Created`: `{"id": "...", "filename": "...", "file_type": "pdf", "status": "uploaded"}`

### `POST /documents/{id}/process?background=true`
Triggers asynchronous document chunking and vector embedding ingestion.
- **Responses**: `200 OK`: `{"status": "queued", "job_id": "..."}`

### `GET /documents/{id}/job`
Retrieves background processing progress, duration, and diagnosis.
- **Responses**:
  - `200 OK`:
    ```json
    {
      "id": "...",
      "document_id": "...",
      "status": "completed",
      "progress": 100,
      "stage": "completed",
      "duration_seconds": 6.81,
      "diagnosis": "Job completed normally in 6.81 seconds with 0 retries."
    }
    ```

### `GET /documents/jobs/diagnostics`
Tenant-scoped operational diagnostics across all background processing jobs.
- **Responses**: `200 OK`: `{"total_jobs_evaluated": 3, "stuck_jobs_count": 0, "recommendations": [...]}`

### `GET /documents/{id}/download?fallback_text=true`
Downloads authentic file binary or reconstructed text if the local ephemeral container disk reset.
- **Response Headers**:
  - `X-Cogniva-Recovered`: `true` or `false`
  - `X-Cogniva-Original-Binary-Available`: `true` or `false`

### `DELETE /documents/{id}`
Deletes document, chunks, and storage records permanently.
- **Responses**: `204 No Content`

---

## 3. Retrieval & Grounded RAG (`/retrieval`, `/rag`)

### `POST /retrieval/search`
Executes pgvector cosine similarity search over processed chunks.
- **Request Body**:
  ```json
  {
    "query": "What are the security requirements?",
    "top_k": 3,
    "document_id": null
  }
  ```
- **Responses**: `200 OK`: `{"results": [{"chunk_id": "...", "content": "...", "similarity_score": 0.88}]}`

### `POST /rag/query`
Executes grounded RAG question answering with anti-prompt-injection isolation and citation badges.
- **Request Body**:
  ```json
  {
    "query": "What are the tenant isolation standards?",
    "top_k": 3,
    "document_id": null
  }
  ```
- **Responses**:
  - `200 OK`:
    ```json
    {
      "query": "...",
      "answer": "Based on the provided documents, tenant isolation standards require... [S1]",
      "citations": [
        {
          "id": 1,
          "document_id": "...",
          "document_title": "...",
          "page_number": 1,
          "chunk_content": "..."
        }
      ]
    }
    ```

---

## 4. Enterprise Intelligence Services (`/intelligence`, `/research`)

### `POST /documents/{id}/summarize`
Generates full-document executive summaries (`mode`: "concise" or "detailed").

### `POST /documents/{id}/extract-structured`
Extracts domain-specific structured entities, dates, obligations, and risk factors.

### `POST /documents/compare`
Executes multi-document differential cross-analysis.

### `POST /reports/generate`
Synthesizes comprehensive multi-section research reports with citation matrices.

### `POST /research/deep-query`
Executes multi-step query decomposition and deep research.

---

## 5. Collections & Conversations (`/collections`, `/conversations`)

### `POST /collections`: Create collection
### `POST /collections/{id}/documents`: Add document to collection
### `DELETE /collections/{id}/documents/{doc_id}`: Remove document from collection
### `POST /conversations`: Create conversation thread
### `GET /conversations`: List paginated conversation threads

---

## 6. Evaluation, Health, & Audit (`/evaluation`, `/health`, `/audit-logs`)

### `GET /health`
Liveness probe returning application name, version, commit hash, and correlation ID.

### `GET /health/ready`
Readiness probe verifying PostgreSQL connectivity and storage configuration.

### `GET /evaluation/metrics`
Exposes live operational telemetry alongside benchmark scores.

### `GET /audit-logs`
Returns tenant-isolated security and operational audit logs with redacted secrets.
