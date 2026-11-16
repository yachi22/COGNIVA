# Cogniva Live Demonstration Guide & Script

**Target Audience:** Technical Recruiters, Engineering Hiring Managers, AI/RAG Architects  
**Demo Duration:** 3–5 minutes  
**Version:** v1.0.0  
**Infrastructure Cost:** $0.00 (Zero-Additional-Cost Stack)  

---

## 1. Demonstration Prerequisites & Setup

### 1.1 Environment Options
You can conduct the demonstration using either the **Live Cloud Production Deployment** or a **Local Development Environment**:

| Resource | Live Cloud Deployment | Local Development Environment |
| :--- | :--- | :--- |
| **Frontend URL** | [https://cogniva-gules.vercel.app](https://cogniva-gules.vercel.app) | `http://localhost:5173` |
| **Backend API** | [https://cogniva-api.onrender.com/api/v1](https://cogniva-api.onrender.com/api/v1) | `http://localhost:8000/api/v1` |
| **Database** | Supabase Cloud PostgreSQL 16 + pgvector | Local Docker PostgreSQL 16 + pgvector |

> [!NOTE]
> **Cloud Free-Tier Wake-up Note:** The live backend on Render operates on a free-tier web service that enters a sleeping state after 15 minutes of inactivity. When demonstrating on the cloud environment, open `https://cogniva-api.onrender.com/api/v1/health` 60 seconds before your interview or presentation to allow the container to warm up.

### 1.2 Recommended Sample Documents (Safe Demo Data)
To ensure reliable, deterministic, and safe demonstrations, prepare one or more of the following mock documents:
1. **Acme_Employee_Handbook_2026.pdf (Recommended):**
   - Content: Multi-page corporate policy containing sections on annual leave entitlements (e.g. 24 days/year), sick leave (10 days), remote work policy, and data protection rules.
   - Purpose: Demonstrates multi-page PDF extraction, page-number preservation, grounded citations (`[S1]`), and summarization.
2. **Cloud_Migration_Security_Whitepaper.docx:**
   - Content: Standard corporate Word document detailing zero-trust network requirements, IAM roles, and encryption at rest.
   - Purpose: Demonstrates DOCX paragraph extraction and multi-format support.
3. **Q3_Financial_Performance_Metrics.csv:**
   - Content: Multi-row spreadsheet detailing quarterly enterprise operational metrics, revenue breakdowns, and headcount figures.
   - Purpose: Demonstrates native tabular CSV parsing (`CSVExtractor`), key-value context serialization, and structured data querying. (Resolved in Phase 19: Full `.csv` drag-and-drop and file-picker support enabled across frontend and backend).

---

## 2. 3–5 Minute Demonstration Script

### Timing Overview
- **0:00 – 0:45 (45s):** Project Context & Problem Statement
- **0:45 – 1:30 (45s):** Ingestion, Magic Bytes & Background Processing
- **1:30 – 2:45 (75s):** Grounded RAG, Anti-Injection & Citation Inspection
- **2:45 – 3:30 (45s):** Executive Summarization & Deep Intelligence
- **3:30 – 4:15 (45s):** Observability, Multi-Tenant Security & Q&A Wrap-up

---

### Step-by-Step Demonstration Sequence

#### Step 1: Opening & Architectural Pitch (0:00 – 0:45)
- **Action:** Open browser to the landing page at `https://cogniva-gules.vercel.app`.
- **Talking Points:**
  > *"Cogniva is an enterprise multimodal knowledge intelligence platform built to solve the primary failure modes of enterprise RAG: hallucination, lack of source provenance, prompt injection vulnerabilities, and high infrastructure costs.*  
  > *It operates under a strict zero-additional-cost architecture ($0.00 baseline) by pairing PostgreSQL 16 and pgvector with ephemeral container storage and database-backed text recovery, eliminating paid vector databases and distributed queue brokers."*

#### Step 2: Tenant Authentication & Dashboard (0:45 – 1:10)
- **Action:** Click **"Sign In"** or **"Get Started"**.
  - If registering: Enter a demo email (e.g. `recruiter_demo@cogniva.ai`), password (`Demo1234!`), and full name (`Engineering Lead`).
  - Click **Sign In / Create Account**.
- **Action:** Arrive at the **Dashboard** (`/dashboard`).
- **Talking Points:**
  > *"Authentication uses 12-round bcrypt password hashing and stateless HS256 JWT tokens. Every database query enforces strict SQL-level tenant isolation (`WHERE user_id = current_user.id`), guaranteeing complete immunity against Cross-Tenant IDOR attacks.*  
  > *The dashboard displays real-time operational telemetry, repository asset counts, and an auditable activity feed."*

#### Step 3: Document Ingestion & Background Job Execution (1:10 – 1:45)
- **Action:** Navigate to **Documents** (`/documents`).
- **Action:** Drag and drop `Acme_Employee_Handbook_2026.pdf` into the upload dropzone.
- **Action:** Show the upload progress bar completing and the document appearing in the repository table with status `uploaded`.
- **Action:** Click **"Process"** on the document row.
- **Talking Points:**
  > *"During upload, Cogniva inspects the binary stream for authentic magic bytes (`%PDF-`) to reject spoofed MIME types, while sanitizing against path traversals.*  
  > *Clicking Process initiates an asynchronous background job tracked in PostgreSQL `document_jobs`. The engine segments text into 1,000-character token-aware chunks with 150-character overlap, derives 1536-dimensional embeddings, and stores them in PostgreSQL with pgvector cosine distance indexing."*
- **Visual Evidence:** Watch the status badge transition from `processing` to `processed`.

#### Step 4: Grounded RAG Query with Citation Provenance (1:45 – 2:45)
- **Action:** Navigate to **Ask Cogniva** (`/chat`).
- **Action:** In the question box, enter:
  > *"According to the Acme employee policy, what is the annual leave entitlement?"*
- **Action:** Click **Send** (or press Enter).
- **Action:** Observe the synthesized response appear:
  > *"According to the Acme Technologies employee policy, full-time employees receive 24 days of annual leave per calendar year [S1]."*
- **Action:** Point out the clickable badge **`[S1]`**.
- **Action:** Click the **`[S1]`** badge to open the **Source Inspection Modal**.
- **Talking Points:**
  > *"Notice three critical engineering details here:*  
  > *First, anti-prompt-injection boundaries: retrieved chunks are quarantined inside delimited untrusted context blocks.*  
  > *Second, citation provenance: every factual statement is anchored to a response-scoped citation pill (`[S1]`). Hallucinated citations are systematically stripped before rendering.*  
  > *Third, source transparency: clicking the badge triggers an authenticated source lookup displaying the exact document title, page number (Page 4), and chunk excerpt."*

#### Step 5: Multi-Turn Conversation & Follow-up (2:45 – 3:15)
- **Action:** Ask a conversational follow-up question:
  > *"What about sick leave?"*
- **Action:** Observe the assistant answer:
  > *"Employees receive 10 days of paid sick leave annually [S2]."*
- **Talking Points:**
  > *"Cogniva maintains multi-turn conversation context across sessions. It enforces bounded history windowing in the prompt so context budgets are never exceeded, while preserving citation provenance across historical turns."*

#### Step 6: Executive Summarization & Document Details (3:15 – 3:45)
- **Action:** Navigate back to **Documents** (`/documents`) and click **"Inspect"** or **"Details"** on the processed handbook.
- **Action:** In the `DocumentViewerModal`, select the **"Takeaways"** tab and toggle between **Concise** and **Detailed** summary modes.
- **Action:** Switch to the **"Citations / Chunks"** tab and type a keyword in the chunk filter search bar (e.g. *"leave"*).
- **Talking Points:**
  > *"Beyond point-query RAG, Cogniva aggregates document-wide context to generate structured executive summaries. The chunk viewer allows compliance auditors to inspect every vector chunk, its assigned page number, and its raw text."*

#### Step 7: Telemetry & Quality Benchmarks (3:45 – 4:15)
- **Action:** Navigate to **Evaluation & Telemetry** (`/evaluation`).
- **Talking Points:**
  > *"In the evaluation dashboard, Cogniva provides live operational telemetry—such as average ingestion job duration and success rates.*  
  > *Importantly, in adherence to engineering integrity, the RAG benchmark evaluation is transparently designated as `NOT EVALUATED`. We intentionally eradicated hardcoded synthetic metric placeholders in Phase 16 to ensure that all reported performance figures reflect empirical reality."*

#### Step 8: Wrap-up & Q&A (4:15 – 5:00)
- **Action:** Conclude on the **Dashboard** or **Settings** screen.
- **Talking Points:**
  > *"To summarize: Cogniva demonstrates that enterprise-grade, verifiable RAG with anti-injection security and multi-tenant isolation can be built with zero additional infrastructure cost by leveraging modern PostgreSQL and strict systems engineering.*  
  > *The backend integration suite achieved a 100% pass rate across 160 automated tests, and the frontend is fully type-safe in TypeScript."*

---

## 3. Known Limitations & Live Demo Fallbacks

| Scenario | Possible Issue | Immediate Presenter Fallback |
| :--- | :--- | :--- |
| **Backend Cold Start** | Cloud Render instance takes 45–60 seconds to wake up on first request. | Open `/api/v1/health` 1 minute before demo, or run the frontend and backend locally (`npm run dev` & `uvicorn app.main:app`). |
| **CSV Drag-and-Drop** | Upload dropzone rejects `.csv` with client-side format warning. | Use `.pdf` or `.docx` sample files for the visual demonstration. |
| **Rate Limit Trigger** | More than 15 login attempts or 30 uploads in 1 minute trigger HTTP 429. | Wait 60 seconds for the process-local sliding window to clear, or use an existing authenticated session. |
| **Missing Cloud Binary** | Ephemeral container disk reset on Render removed the uploaded binary. | Demonstrate Phase 11.2 text recovery: downloading with `?fallback_text=true` successfully reconstructs text from database chunks. |

---

## 4. Recommended Screenshot Portfolio List

When documenting the platform or preparing presentation slide decks, capture these six recommended screens:

1. **`01_dashboard_overview.png`**
   - **Screen:** `/dashboard` with at least 1 processed document and 1 active conversation.
   - **Placement:** README Section 3 (Key Features) & Portfolio Slide 2.
   - **Highlights:** Repository stats cards, health status pill, activity feed.

2. **`02_documents_repository.png`**
   - **Screen:** `/documents` showing the upload dropzone and document table with `processed` status badges.
   - **Placement:** README Section 5 (RAG Pipeline) & Portfolio Slide 4.
   - **Highlights:** Clean tabular view, format badges (PDF, DOCX), action buttons.

3. **`03_document_viewer_modal.png`**
   - **Screen:** `DocumentViewerModal` displaying the "Takeaways" executive summary and the "Citations / Chunks" filter.
   - **Placement:** `docs/ARCHITECTURE.md` Subsystem 3.4 & Portfolio Slide 5.
   - **Highlights:** Structured takeaway cards, chunk index, page number badges.

4. **`04_ask_cogniva_chat.png`**
   - **Screen:** `/chat` showing user question and assistant answer with interactive `[S1]` and `[S2]` citation pills.
   - **Placement:** README Hero Section & Portfolio Slide 6.
   - **Highlights:** Bubble layout, clean monospace citation badges, copy actions.

5. **`05_source_inspection_modal.png`**
   - **Screen:** `SourceInspectionModal` triggered by clicking a citation pill, displaying exact source excerpt and page number.
   - **Placement:** `docs/RAG_PIPELINE.md` Section 6 & Portfolio Slide 7.
   - **Highlights:** Document filename, Page 4 indicator, similarity score, exact text excerpt.

6. **`06_evaluation_telemetry.png`**
   - **Screen:** `/evaluation` showing operational telemetry metrics and transparent benchmark status.
   - **Placement:** `docs/TESTING.md` Section 1 & Portfolio Slide 8.
   - **Highlights:** Job durations, tenant operational metrics, honest `NOT EVALUATED` benchmark badge.

