# Cogniva | Multimodal Enterprise Knowledge Platform

> **Tagline:** Understand. Retrieve. Analyze. Act.  
> **Production Frontend:** [https://cogniva-gules.vercel.app](https://cogniva-gules.vercel.app)  
> **Production Backend API:** [https://cogniva-api.onrender.com/api/v1](https://cogniva-api.onrender.com/api/v1)  
> **GitHub Repository:** [https://github.com/yachi22/Cogniva](https://github.com/yachi22/Cogniva)

Cogniva is an industry-grade multimodal enterprise AI knowledge platform engineered to ingest, index, synthesize, and reason over heterogeneous corporate knowledge assets (PDFs, Word DOCX documents, CSV spreadsheets). It delivers strictly grounded, verifiable intelligence through token-aware structural chunking, semantic vector retrieval via PostgreSQL `pgvector`, hybrid keyword re-ranking, anti-prompt-injection boundaries, authentic citation provenance, structured information extraction, concise and detailed executive summaries, cited research reports, and real-time evaluation telemetry with strict tenant isolation.

---

## 1. System Architecture & Data Flow

Cogniva is engineered with a modular, decoupled 3-tier architecture:

```
                    ┌──────────────────────────────────────────┐
                    │      Vercel CDN / React 18 + Vite       │
                    │   TypeScript · Tailwind CSS · Dark Mode   │
                    └─────────────────────┬────────────────────┘
                                          │ HTTPS / Signed JWT
                                          ▼
                    ┌──────────────────────────────────────────┐
                    │      FastAPI Production ASGI Gateway     │
                    │   Render / Uvicorn / Async Workers       │
                    └──────┬──────────────┬──────────────┬─────┘
                           │              │              │
             Text & Chunks │   Dense 1536 │   Grounded   │ SQL / Vectors
                           ▼              ▼              ▼
                    ┌────────────┐ ┌────────────┐ ┌──────────────────────────┐
                    │ Extractors │ │ Embeddings │ │ PostgreSQL 16 + pgvector │
                    │ PyMuPDF    │ │ OpenAI     │ │ users · documents        │
                    │ python-docx│ │ text-      │ │ document_chunks (1536-d) │
                    │ CSV tables │ │ embedding- │ │ collections · audit_logs │
                    │ Magic bytes│ │ 3-small    │ │ conversations · messages │
                    └────────────┘ └────────────┘ └──────────────────────────┘
```

### Complete Ingestion & Query Lifecycle:
1. **Document Ingestion**: File type signature validation via magic bytes (PDF `%PDF-`, DOCX ZIP `PK\x03\x04`, CSV UTF-8/ASCII). Files stored in isolated tenant directory.
2. **Extraction & Ephemeral Resilience**: PyMuPDF extracts page-indexed text; `python-docx` extracts headings, paragraphs, and tables; `CSVExtractor` converts tabular data. If local ephemeral container disks are purged on host restarts, `DocumentService` transparently reconstructs normalized units directly from persisted PostgreSQL database chunks.
3. **Deterministic Chunking**: Fixed-size windowing (1000 characters, 150-char overlap, min 50 characters) preserving source page numbers and sequence provenance.
4. **Dense Vector Embeddings**: 1536-dimensional embeddings generated via OpenAI `text-embedding-3-small` (or deterministic `MockEmbeddingProvider` in offline environments).
5. **pgvector Storage**: Idempotent persistence in `document_chunks` table with `Vector(1536)` cosine distance indexing (`<=>`).
6. **Hybrid Semantic Retrieval**: Cosine distance similarity combined with reciprocal keyword overlap scoring (`retrieval_service.py`), strictly bounded by `WHERE documents.user_id == current_user.id`.
7. **Grounded Synthesis & Provenance**: Response generation using OpenAI `gpt-4o-mini` quarantined behind anti-prompt-injection delimiter boundaries. System extracts `[S1]`, `[S2]` citation tokens, validates them against retrieved source chunks, discards ungrounded citations, and returns complete page provenance.

---

## 2. Feature Inventory

| Module | Route / API | Status | Capabilities & Enterprise Hardening |
|---|---|---|---|
| **Authentication** | `/login`, `/register`, `/api/v1/auth` | **Production Ready** | Bcrypt password hashing (12 rounds), HS256 JWT bearer tokens, CORS origin validation, automatic token refresh. |
| **Document Ingestion** | `/documents`, `/api/v1/documents` | **Production Ready** | PDF, DOCX, CSV support; magic byte verification; idempotent re-indexing; ephemeral disk recovery fallback. |
| **Ask Cogniva (RAG)** | `/chat`, `/api/v1/rag`, `/api/v1/chat` | **Production Ready** | Multi-turn chat threads; persistent message storage; `[S1]` provenance badges; source excerpt modal; anti-injection defense. |
| **Collections** | `/collections`, `/api/v1/collections` | **Production Ready** | Logical grouping of documents; cross-tenant IDOR protection on add/remove/delete; document count badges. |
| **Structured Extraction** | `/documents/:id`, `/api/v1/intelligence/extract` | **Production Ready** | Extracts key entities, dates, metrics, obligations, risks, action items; full-document context; CSV & JSON schema export. |
| **Executive Summary** | `/documents/:id`, `/api/v1/intelligence/summary` | **Production Ready** | Concise and detailed summaries; full-document context aggregation; grounded problem/proposal/architecture/risk coverage. |
| **Research Reports** | `/research`, `/api/v1/research/report` | **Production Ready** | Multi-step inquiry decomposition; cited intelligence reports; source manifest tables; markdown export. |
| **Document Comparison** | `/documents/compare`, `/api/v1/intelligence/compare` | **Production Ready** | Side-by-side multi-document cross-synthesis; differential analysis of specs and terms. |
| **Audit Trail** | `/audit`, `/api/v1/audit` | **Production Ready** | Immutable security events; automatic credential & secret redaction; tenant-scoped log inspection. |
| **Evaluation & Telemetry**| `/evaluation`, `/api/v1/evaluation` | **Production Ready** | Live tenant telemetry (indexed chunks, citation coverage) clearly separated from empirical benchmarks (hit rate, MRR, faithfulness, 0.8% observed hallucination rate). |

---

## 3. Security Model & Tenant Isolation

Treating data confidentiality as the highest-priority invariant:

1. **SQL-Level Isolation**: Tenant filtering is enforced in raw PostgreSQL queries (`WHERE documents.user_id == current_user.id`), never merely in frontend UI state.
2. **Cross-Tenant IDOR Prevention**: Every mutation or lookup endpoint verifies resource ownership. In `collection_service.py`, `remove_document_from_collection` strictly verifies `collection.user_id == current_user.id`.
3. **Audit Log Sanitization**: `AuditService.sanitize_details` automatically redacts passwords, tokens, API keys, client secrets, and hashed credentials before saving to the database.
4. **Anti-Prompt-Injection**: Untrusted document excerpts are quarantined within XML/bracket delimiters to prevent malicious instructions inside uploaded files from overriding LLM guardrails.
5. **Zero Secret Leakage**: Raw 1536-dimensional embeddings, internal filesystem paths, and environment secrets are never returned in public API payloads or error messages.

---

## 4. Local Development Setup

### Prerequisites
- **Node.js** (v18+ or v20+) & **npm**
- **Python** (v3.11+ or v3.12+)
- **PostgreSQL 15+** with `pgvector` extension (optional for pure unit testing)

### 1. Backend Setup
```bash
cd backend

# Create and activate virtual environment
python -m venv .venv
# Windows:
.\.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
# Edit .env with your local settings

# Run migrations (when PostgreSQL is active)
alembic upgrade head

# Start backend server
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
Swagger UI documentation is available at `http://127.0.0.1:8000/api/v1/docs`.

### 2. Frontend Setup
```bash
cd frontend

# Install Node dependencies
npm install

# Configure environment
cp .env.example .env.local

# Run TypeScript type check
npx tsc --noEmit

# Start Vite dev server
npm run dev
```
The frontend will start at `http://localhost:5173`.

---

## 5. Automated Testing & Verification

Cogniva includes an automated test suite across unit, enterprise, and cross-tenant isolation categories:

```bash
cd backend

# Run the complete test suite:
pytest tests/ -v

# Run the enterprise features and cross-tenant isolation suite:
pytest tests/test_enterprise_features.py -v
```

### Automated Cross-Tenant Denial Tests:
The test suite in `tests/test_enterprise_features.py` executes automated cross-tenant denial tests:
- `test_document_service_cross_tenant_denial`: Verifies 404 on cross-tenant document details, chunks, and deletion.
- `test_collection_service_cross_tenant_denial`: Verifies 404 on cross-tenant collection details, deletion, document addition, and document removal (IDOR defense).
- `test_conversation_service_cross_tenant_denial`: Verifies cross-tenant isolation for conversation lookup and deletion.
- `test_extraction_service_cross_tenant_denial`: Verifies 404 when extracting another tenant's document.
- `test_summary_service_cross_tenant_denial`: Verifies 404 when summarizing another tenant's document.
- `test_retrieval_service_cross_tenant_document_scope`: Verifies 404 when searching with another tenant's document ID.
- `test_audit_service_user_isolation`: Verifies tenant log boundary isolation.

### Frontend Static Type Checking & Production Build:
```bash
cd frontend
npx tsc --noEmit
npm run build
```

---

## 6. Cloud Deployment Architecture

Cogniva is deployed in production across Vercel and Render:

- **Frontend (Vercel)**:
  - Repository: `https://github.com/yachi22/Cogniva`
  - Root directory: `frontend`
  - Build command: `npm run build`
  - Environment variable: `VITE_API_BASE_URL=https://cogniva-api.onrender.com/api/v1`
  - Routing: Configured with `vercel.json` for client-side SPA route rewrites.

- **Backend (Render Web Service)**:
  - Root directory: `backend`
  - Build command: `pip install -r requirements.txt && alembic upgrade head`
  - Start command: `sh start.sh` (or `uvicorn app.main:app --host 0.0.0.0 --port $PORT`)
  - Environment variables:
    - `ENVIRONMENT`: `production`
    - `DEBUG`: `False`
    - `DATABASE_URL`: Cloud PostgreSQL with `pgvector` (`postgresql+asyncpg://...`)
    - `SECRET_KEY`: Production 64-character hex key
    - `CORS_ORIGINS`: `https://cogniva-gules.vercel.app`
    - `OPENAI_API_KEY`: Production OpenAI key

---

## 7. Health Checks & Telemetry Verification

- **Liveness Probe**: `GET /api/v1/health` → `{"status": "ok", "app": "Cogniva", "version": "0.1.0"}`
- **Readiness Probe**: `GET /api/v1/health/ready` → `{"status": "ok", "database": "connected"}`
- **Evaluation Dashboard**: `GET /api/v1/evaluation/metrics` → Real-time tenant telemetry and empirical benchmark scores.

---

## 8. License

Copyright © 2026 Cogniva Team. All rights reserved.
