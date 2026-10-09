# Cogniva | Multimodal Enterprise Knowledge Agent

> **Tagline:** Understand. Retrieve. Analyze. Act.

Cogniva is an enterprise-grade multimodal knowledge intelligence platform engineered to ingest, index, and reason over heterogeneous enterprise assets (PDFs, Word DOCX documents, and structured knowledge). It delivers strictly grounded, source-cited intelligence through deterministic chunking, semantic vector retrieval via PostgreSQL `pgvector`, robust anti-prompt-injection boundaries, verified citation provenance, and persistent multi-turn conversations with tenant isolation.

---

## 1. Project Overview & Architecture

Cogniva is built with a decoupled, modular 3-tier architecture:

```
Cogniva Enterprise Platform
├── Frontend Client (Port 5173 / Vercel)
│   ├── React 18 + TypeScript + Vite + Tailwind CSS
│   ├── Responsive SaaS Shell (Dashboard, Documents Library, Ask Cogniva Chat, Settings)
│   ├── Compact Citation Badges ([S1] doc.pdf · p.1) & Interactive Source Inspection Modal
│   └── Multi-turn Conversation History Drawer with instant navigation
│
├── Backend API Service (Port 8000 / Render / Railway)
│   ├── FastAPI + Uvicorn ASGI Application
│   ├── Pydantic v2 validation & Pydantic-Settings environment management
│   ├── PyMuPDF & python-docx deterministic document extractors
│   ├── Structural chunking (1000-char units, 150-char overlap, provenance tracking)
│   ├── 1536-dimensional dense embedding generation (OpenAI text-embedding-3-small)
│   ├── Grounded RAG orchestrator with anti-injection defense boundaries
│   ├── Regex citation extraction ([S1], [S2]) & authentic source validation
│   └── Persistent ConversationService managing chat threads and turns
│
└── Managed Database (PostgreSQL 16 + pgvector / Supabase / Neon)
    ├── users: Tenant accounts & bcrypt password hashes
    ├── documents: Document metadata, status lifecycle, tenant mapping
    ├── document_chunks: Document excerpts, page numbers, and 1536-d vector embeddings
    ├── conversations: Persistent chat threads, auto-generated titles, timestamps
    └── messages: User questions & assistant answers with JSONB citation/source metadata
```

---

## 2. Implemented Features (MVP Scope)

Cogniva MVP implements complete functionality for Phases 0 through 12:

* **Authentication & Tenant Security**:
  - Email/password user registration and login with bcrypt hashing (12 salt rounds).
  - Signed JWT Bearer tokens with configurable expiration (HS256).
  - Strict database-level tenant isolation: users can never access, query, inspect, or delete another tenant's documents, chunks, conversations, or messages.

* **Document Ingestion & Extraction**:
  - Secure upload supporting PDF (`.pdf`) and Word (`.docx`) up to 50MB.
  - Magic byte inspection and path traversal sanitization.
  - Page-aware PDF extraction (PyMuPDF / `fitz`) and paragraph-aware Word extraction (`python-docx`).
  - Text normalization and deterministic whitespace cleaning.

* **Chunking & Vector Embeddings**:
  - Token-aware structural chunking with provenance preservation (document filename, page number, unit type, source sequence).
  - 1536-dimensional dense vector embeddings generated via OpenAI `text-embedding-3-small` (with offline `MockEmbeddingProvider` for testing).
  - Idempotent document reprocessing replacing previous chunk records cleanly.

* **Semantic Vector Retrieval**:
  - Native PostgreSQL `pgvector` cosine distance retrieval (`<=>`).
  - Tenant-isolated vector search with configurable `top_k` and `min_similarity` thresholds.
  - Document-scoped retrieval filtering.

* **Retrieval-Augmented Generation (RAG) & Citations**:
  - Grounded answer generation using OpenAI `gpt-4o-mini`.
  - Strict operating rules: answers must be based exclusively on retrieved context.
  - Anti-prompt-injection boundaries: untrusted document context is isolated from instructions.
  - Backend-owned, response-scoped citation identifiers (`[S1]`, `[S2]`).
  - Hallucinated citation rejection: citations not present in the retrieved set are discarded.
  - Deterministic fallback for insufficient evidence without LLM speculation.

* **Source Provenance & Inspection**:
  - Compact citation pills rendering badge, document filename, and page number.
  - Secure source inspection endpoint (`GET /api/v1/documents/{doc_id}/chunks/{chunk_id}`) allowing users to view the authentic retrieved text with zero vector or filesystem leakage.

* **Persistent Conversations & Chat History**:
  - PostgreSQL-backed persistent conversations surviving browser refreshes and server restarts.
  - Automatic, deterministic conversation title generation from the first user query.
  - Multi-turn conversation context with bounded history (last 6 messages) for follow-up questions.
  - Follow-up query enrichment for semantic retrieval.
  - Reopening past chats restores original answer citations and enables instant source inspection.
  - Thread deletion with cascade cleanup across all turns.

* **Production Readiness & Deployment**:
  - Dynamic cloud container port binding (`$PORT`).
  - Comma-separated and JSON-formatted CORS origins configuration.
  - Production security validation: forces `DEBUG=False` and rejects development secret keys.
  - Cloud database URL normalization supporting `postgres://` and `sslmode=require`.
  - Containerization with multi-stage Dockerfiles, healthchecks, and Alembic migrations on startup.
  - Single-Page Application (SPA) client-side routing rewrites (`vercel.json`).

### Planned Future Features (Post-MVP):
* Tabular data and spreadsheet analysis (Excel/CSV).
* Multi-document comparison and cross-document synthesis.
* Visual reasoning and image understanding.
* Autonomous agent orchestration and tool execution.

---

## 3. Technology Stack

| Layer | Technology | Details |
|---|---|---|
| **Frontend Framework** | React 18 + Vite 5 | Fast HMR, optimized production chunks |
| **Language** | TypeScript 5 | Strict typing across all components and API schemas |
| **Styling** | Tailwind CSS 3 | Modern enterprise theme, responsive layouts |
| **Icons & UI** | Lucide React | Minimalist enterprise iconography |
| **HTTP Client** | Axios | Configured with token interceptors & 30s timeout |
| **Backend Framework** | FastAPI 0.111 | High performance async ASGI framework |
| **ASGI Server** | Uvicorn 0.30 | Production ASGI server |
| **ORM & Database** | SQLAlchemy 2.0 (Async) | `asyncpg` for queries, `psycopg` for migrations |
| **Vector Engine** | PostgreSQL 16 + pgvector | Cosine distance similarity indexing |
| **Migrations** | Alembic 1.13 | Version-controlled schema migrations |
| **Document Processing**| PyMuPDF + python-docx | High-fidelity text and structure extraction |
| **Embedding Model** | text-embedding-3-small | 1536-dimensional dense embeddings |
| **LLM Model** | gpt-4o-mini | Temperature 0.0 for deterministic factual grounding |

---

## 4. Local Development Setup

### Prerequisites
- **Node.js** (v18+ or v20+) & **npm**
- **Python** (v3.11+ or v3.12+)
- **PostgreSQL** with `pgvector` extension installed (or Docker)

### 1. Clone & Environment Setup
```bash
# Clone repository
git clone <repository-url>
cd cogniva

# Copy environment template
cp .env.example .env
```

Edit `.env` to configure your local database credentials and OpenAI API key.

### 2. Backend Setup
```bash
cd backend

# Create and activate virtual environment
python -m venv .venv

# Windows:
.venv\Scripts\activate
# Linux / macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run database migrations
alembic upgrade head

# Start backend dev server
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
The backend will be available at `http://127.0.0.1:8000`. Swagger API documentation is accessible at `http://127.0.0.1:8000/api/v1/docs`.

### 3. Frontend Setup
```bash
cd frontend

# Install Node dependencies
npm install

# Start Vite dev server
npm run dev
```
The frontend will be available at `http://127.0.0.1:5173`. In development, requests to `/api` are automatically proxied to the backend at `http://127.0.0.1:8000`.

---

## 5. Environment Variables Configuration

| Variable | Description | Default / Example |
|---|---|---|
| `PROJECT_NAME` | Application display name | `Cogniva` |
| `ENVIRONMENT` | Runtime environment (`development` or `production`) | `development` |
| `DEBUG` | Enable debug mode (forced to `False` in production) | `True` |
| `HOST` | Backend host bind address | `0.0.0.0` |
| `PORT` | Backend port (overridden by `$PORT` on cloud hosts) | `8000` |
| `CORS_ORIGINS` | Allowed frontend origins (JSON array or comma-separated) | `["http://localhost:5173"]` |
| `VITE_API_BASE_URL` | Frontend API target URL (in production on Vercel) | `https://<backend>.onrender.com/api/v1` |
| `DATABASE_URL` | PostgreSQL connection URL with pgvector | `postgresql+asyncpg://postgres:postgres@localhost:5432/cogniva` |
| `SECRET_KEY` | JWT signing secret (use `openssl rand -hex 32` in production) | `cogniva-super-secret-key-for-development-change-in-production` |
| `ALGORITHM` | JWT signing algorithm | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | JWT token lifetime | `1440` (24 hours) |
| `STORAGE_DIR` | Directory for uploaded documents (or mounted volume) | `storage` |
| `MAX_UPLOAD_SIZE_MB` | Maximum allowed document upload size | `50` |
| `EMBEDDING_PROVIDER` | Embedding engine (`openai` or `mock` for testing) | `openai` |
| `EMBEDDING_MODEL` | OpenAI embedding model name | `text-embedding-3-small` |
| `LLM_PROVIDER` | LLM generation engine (`openai` or `mock`) | `openai` |
| `LLM_MODEL` | Grounded answer generation model | `gpt-4o-mini` |
| `OPENAI_API_KEY` | OpenAI API authentication key | `sk-...` |

---

## 6. Running Tests & Production Builds

### Backend Test Suite
The automated test suite covers authentication, chunking, embeddings, pgvector retrieval, RAG, citations, conversations, tenant isolation, and deployment configuration across 65 tests:

```bash
cd backend
pytest -v
```

### Frontend Production Build
```bash
cd frontend
npm run build
```
This runs TypeScript type checking (`tsc`) and bundles optimized static assets into `dist/`.

---

## 7. Cloud Deployment Guide (MVP)

Cogniva MVP is designed for cost-conscious, reliable cloud deployment on modern hosting platforms suitable for student projects and enterprise prototypes.

### Recommended Target Architecture:
* **Frontend**: **Vercel** (Static Site CDN)
* **Backend**: **Render** or **Railway** (Python Web Service / Container)
* **Database**: **Supabase** or **Neon** (Managed PostgreSQL with native `pgvector`)

### Step 1: Deploy Database (Supabase or Neon)
1. Create a free PostgreSQL project on [Supabase](https://supabase.com) or [Neon](https://neon.tech).
2. Ensure the `vector` extension is enabled (Supabase enables it automatically; Neon supports `CREATE EXTENSION IF NOT EXISTS vector;`).
3. Copy the pooled or direct connection string:
   ```
   postgresql://postgres:[PASSWORD]@[HOST]:[PORT]/postgres?sslmode=require
   ```

### Step 2: Deploy Backend (Render)
1. Create a new **Web Service** on [Render](https://render.com) pointing to the repository.
2. Root Directory: `backend` (or use Dockerfile).
3. **Environment**: `Python 3` (or `Docker`).
4. **Build Command**:
   ```bash
   pip install -r requirements.txt && alembic upgrade head
   ```
5. **Start Command**:
   ```bash
   sh start.sh
   # or: uvicorn app.main:app --host 0.0.0.0 --port $PORT
   ```
6. **Environment Variables**:
   * `ENVIRONMENT`: `production`
   * `DEBUG`: `False`
   * `DATABASE_URL`: Your Supabase/Neon connection URL
   * `SECRET_KEY`: Generate a random key: `openssl rand -hex 32`
   * `OPENAI_API_KEY`: Your OpenAI API key
   * `CORS_ORIGINS`: Your Vercel frontend URL (e.g. `https://cogniva.vercel.app`)
7. Once deployed, note your service URL: `https://<your-service>.onrender.com`.

### Step 3: Deploy Frontend (Vercel)
1. Import the repository on [Vercel](https://vercel.com).
2. Set **Root Directory** to `frontend`.
3. Framework Preset: **Vite**.
4. **Environment Variables**:
   * `VITE_API_BASE_URL`: `https://<your-service>.onrender.com/api/v1`
5. Deploy. The included `frontend/vercel.json` ensures that direct navigation to `/chat`, `/chat/:id`, and `/documents` routes will not trigger 404 errors.

---

## 8. Health Verification & Monitoring Endpoints

* **Liveness Probe**:
  ```http
  GET /api/v1/health
  ```
  Returns `{"status": "ok", "app": "Cogniva", "version": "0.1.0", "environment": "production"}`.

* **Readiness Probe**:
  ```http
  GET /api/v1/health/ready
  ```
  Executes a safe `SELECT 1` against PostgreSQL without exposing credentials, returning `{"status": "ok", "database": "connected"}`.

---

## 9. Security & Privacy Considerations

1. **Strict Tenant Boundaries**: All document chunks, retrieval queries, and conversation messages are scoped to the authenticated user ID (`WHERE user_id == current_user.id`). Cross-user requests return `404 Not Found` to prevent resource enumeration.
2. **Zero Credential / Embedding Exposure**: Internal server paths (`storage_path`) and 1536-dimensional raw embeddings are never returned over API endpoints.
3. **Input Sanitization**: File uploads are verified by extension and magic byte signatures. Filenames are strictly sanitized to prevent directory traversal.
4. **Grounded RAG Boundaries**: User queries and untrusted document texts are quarantined in delimited data blocks to protect against prompt injection and override attacks.
5. **Production Secret Enforcement**: The backend fails at startup if configured with `ENVIRONMENT=production` while retaining development secrets.

---

## 10. License

Copyright © 2026 Cogniva Team. All rights reserved.
