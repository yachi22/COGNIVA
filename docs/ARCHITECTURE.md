# Cogniva System Architecture & Engineering Specification

## 1. Executive Summary & Design Invariants

Cogniva is a multimodal enterprise knowledge agent platform engineered to ingest, index, synthesize, and reason over unstructured and semi-structured corporate documents (PDF, DOCX, CSV). It delivers grounded intelligence with verifiable citation provenance, zero secret leakage, and strict multi-tenant isolation.

### Architectural Invariants:
1. **Strict Multi-Tenant Scoping**: All database and cache lookups enforce `user_id == current_user.id` at the SQL query level (`WHERE documents.user_id = :user_id`), making Cross-Tenant IDOR impossible.
2. **Zero Additional Cost ($0.00)**: Operates without paid queues (Celery/Redis), managed vector DBs (Pinecone/Weaviate), or cloud bucket storage (AWS S3) by leveraging PostgreSQL 16 + `pgvector` and ephemeral local disk with database-backed text reconstruction.
3. **Anti-Prompt-Injection Boundary**: Untrusted retrieved passage chunks are quarantined within structured delimiters to prevent malicious instructions from overriding system guardrails.
4. **Verifiable Citation Provenance**: Every generated response anchors factual assertions to deterministic citations (`[S1]`, `[S2]`) with document filename, page number, and chunk provenance.

---

## 2. System Topology & Data Flow

```
                      ┌──────────────────────────────────────────┐
                      │    Vercel CDN / React 18 + Vite (SPA)   │
                      │  TypeScript · Tailwind CSS · Heroicons   │
                      └────────────────────┬─────────────────────┘
                                           │ HTTPS / TLS 1.3
                                           │ Bearer JWT (HS256)
                                           ▼
                      ┌──────────────────────────────────────────┐
                      │     Cloudflare Edge / Render Cloud WAF   │
                      │  Path Traversal & Request Scrubbing     │
                      └────────────────────┬─────────────────────┘
                                           │
                                           ▼
                      ┌──────────────────────────────────────────┐
                      │         FastAPI ASGI Application         │
                      │ ├─ SecurityHeadersMiddleware (HSTS, CSP) │
                      │ ├─ CorrelationIdMiddleware (UUIDv4)      │
                      │ ├─ SlidingWindowRateLimiter (In-Memory)  │
                      │ └─ Global Exception Sanitizer (Opaque)   │
                      └────────┬─────────────┬─────────────┬─────┘
                               │             │             │
                    Normalized │   1536-dim  │ Grounded    │ SQL / Cosine
                    TextUnits  │   Vectors   │ Synthesis   │ Distance (<=>)
                               ▼             ▼             ▼
  ┌───────────────────────────────┐  ┌─────────────┐  ┌──────────────────────────────┐
  │     Extractors & Ingestion    │  │ Embeddings  │  │   PostgreSQL 16 + pgvector   │
  │ ├─ PyMuPDF (PDF page tokens)  │  │ OpenAI      │  │ ├─ users (bcrypt hashes)     │
  │ ├─ python-docx (DOCX blocks)  │  │ text-       │  │ ├─ documents (metadata)      │
  │ ├─ CSVExtractor (Tabular)     │  │ embedding-  │  │ ├─ document_chunks (1536-d)  │
  │ └─ Magic Byte Validator       │  │ 3-small     │  │ ├─ document_jobs (durable)   │
  └───────────────────────────────┘  └─────────────┘  │ ├─ collections & mappings    │
                                                      │ ├─ conversations & messages  │
                                                      │ └─ audit_logs (sanitized)    │
                                                      └──────────────────────────────┘
```

---

## 3. Core Subsystems

### 3.1 Document Ingestion & Ephemeral Resilience (Phase 11.2)
- **Signature Validation**: Checks magic bytes (`%PDF-` for PDFs, `PK\x03\x04` for DOCX, ASCII/UTF-8 for CSV) before accepting uploads.
- **Filename Sanitization**: Neutralizes path traversals using `os.path.basename` and regex stripping.
- **Zero-Budget Reconstructed Recovery**: If the ephemeral container disk resets upon redeployment, `DocumentService` reconstructs text from PostgreSQL `document_chunks`. Downloads provide `X-Cogniva-Recovered: true` and `X-Cogniva-Original-Binary-Available: false`.

### 3.2 Durable Background Job Engine (Phase 12)
- **Persistent State**: Background document ingestion state is persisted in the `document_jobs` table (`queued` → `processing` → `completed` / `failed`).
- **Bounded Exponential Backoff**: Transient embedding failures retry up to 3 times with exponential backoff before marking exhaustion.
- **Startup Recovery**: On host restart or worker crash, `recover_interrupted_jobs` automatically recovers in-flight jobs.

### 3.3 Observability & Structured Telemetry (Phase 13)
- **Correlation Propagation**: Every request receives or echoes an `X-Correlation-ID` and `X-Request-ID` across logs, exceptions, and headers.
- **Health & Readiness**: `/health` verifies liveness, `/health/ready` verifies database connectivity and local storage status.
- **Diagnostics**: `/documents/jobs/diagnostics` and `/evaluation/metrics` expose tenant-scoped operational telemetry without external monitoring services.

### 3.4 Enterprise Security & Abuse Protection (Phase 14)
- **Security Headers**: Injects `Strict-Transport-Security`, `Content-Security-Policy: default-src 'self'; frame-ancestors 'none'`, `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, and `Referrer-Policy: strict-origin-when-cross-origin`.
- **In-Memory Rate Limiting**: `SlidingWindowRateLimiter` enforces bounds on auth (15 req/min), uploads (30 req/min), and LLM queries (30 req/min) returning HTTP 429 with `Retry-After`.
- **Sensitive Data Redaction**: Automatically scrubs passwords, API keys, bearer tokens, and DB connection strings from logs and audit trails.

---

## 4. Multi-Tenant Isolation Model

```
+-----------------------------------------------------------------------------------+
| Multi-Tenant Isolation Layers                                                     |
+-----------------------------------------------------------------------------------+
| 1. Network / Edge Layer: TLS 1.3, CSP, Frame Denial, Cloud WAF                   |
| 2. Auth Layer: JWT HS256 validation, sub claims, expiration (1440m)               |
| 3. Middleware Layer: In-memory sliding-window rate limiters per IP / User ID       |
| 4. Service Layer: Ownership verification (404 on mismatched tenant)              |
| 5. Database Layer: Parameterized SQL WHERE user_id = :user_id                     |
| 6. Audit Layer: Automated credential and key redaction                            |
+-----------------------------------------------------------------------------------+
```
