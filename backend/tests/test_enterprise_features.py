import io
import json
import uuid
from pathlib import Path
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException, status

from app.models.document import Document
from app.models.chunk import DocumentChunk
from app.models.collection import Collection
from app.models.audit_log import AuditLog
from app.services.summary_service import SummaryService
from app.services.comparison_service import ComparisonService
from app.services.extraction_service import ExtractionService
from app.services.collection_service import CollectionService
from app.services.report_service import ReportService
from app.services.research_service import ResearchService
from app.services.knowledge_graph_service import KnowledgeGraphService
from app.services.audit_service import AuditService
from app.services.documents.extractor import CSVExtractor
from app.services.storage_service import StorageService


# 1. Audit Service credential sanitization tests
def test_audit_service_sanitizes_credentials():
    audit_svc = AuditService()
    raw_details = {
        "user_email": "compliance@enterprise.com",
        "password": "SuperSecretPassword123!",
        "access_token": "eyJhbGciOiJIUzI1NiIsIn...",
        "api_key": "sk-1234567890",
        "client_secret": "xyz_secret",
        "action_flag": True,
    }

    sanitized = audit_svc.sanitize_details(raw_details)

    assert sanitized["user_email"] == "compliance@enterprise.com"
    assert sanitized["action_flag"] is True
    assert sanitized["password"] == "[REDACTED]"
    assert sanitized["access_token"] == "[REDACTED]"
    assert sanitized["api_key"] == "[REDACTED]"
    assert sanitized["client_secret"] == "[REDACTED]"


# 2. CSV Extractor tabular processing tests
def test_csv_extractor_processes_tabular_data(tmp_path: Path):
    csv_file = tmp_path / "test_data.csv"
    csv_file.write_text(
        "Project,Lead,Budget,Status\n"
        "Cogniva,Engineering,$120000,Active\n"
        "Security Audit,InfoSec,$45000,Completed\n",
        encoding="utf-8",
    )

    extractor = CSVExtractor()
    doc_id = uuid.uuid4()
    extracted_doc = extractor.extract(csv_file, document_id=doc_id)

    assert len(extracted_doc.units) == 1
    unit = extracted_doc.units[0]
    assert unit.unit_type == "table"
    assert unit.sequence_number == 1
    assert "Cogniva" in unit.text
    assert "$120000" in unit.text
    assert unit.metadata["total_rows"] == 2
    assert "Project" in unit.metadata["headers"]


# 3. Storage Service CSV validation tests
def test_storage_service_csv_validation():
    storage_svc = StorageService()

    # Valid CSV passes without exception
    valid_csv = b"col1,col2,col3\nval1,val2,val3\n"
    storage_svc.validate_magic_bytes(valid_csv, "csv")

    # Valid PDF passes without exception
    valid_pdf = b"%PDF-1.4\nsome stream"
    storage_svc.validate_magic_bytes(valid_pdf, "pdf")

    # Binary junk passed as CSV raises 400
    invalid_csv = b"test\x00binary\x00data"
    with pytest.raises(HTTPException) as exc_info:
        storage_svc.validate_magic_bytes(invalid_csv, "csv")
    assert exc_info.value.status_code == 400


# 4. Structured Extraction Service CSV export tests
def test_extraction_service_csv_export():
    svc = ExtractionService()
    extraction_data = {
        "document_id": str(uuid.uuid4()),
        "document_filename": "master_agreement.pdf",
        "data": {
            "key_entities": [
                {"name": "Cogniva Inc", "type": "Vendor"},
                {"name": "Enterprise Corp", "type": "Client"},
            ],
            "metrics": ["$1,000,000 SLA penalty cap", "99.9% uptime requirement"],
            "obligations": ["Provide 30-day termination notice"],
        },
    }

    csv_output = svc.export_as_csv(extraction_data)

    assert "Category,Item / Name,Detail / Value,Context / Entity Type,Page" in csv_output
    assert "Cogniva Inc" in csv_output
    assert "Enterprise Corp" in csv_output
    assert "$1,000,000 SLA penalty cap" in csv_output
    assert "Provide 30-day termination notice" in csv_output


# 5. Summary Service caching test (Unit level)
@pytest.mark.asyncio
async def test_summary_service_cache_hit():
    summary_svc = SummaryService()
    user_id = uuid.uuid4()
    doc_id = uuid.uuid4()

    mock_doc = MagicMock(spec=Document)
    mock_doc.id = doc_id
    mock_doc.user_id = user_id
    mock_doc.status = "processed"
    mock_doc.filename = "contract.pdf"
    mock_doc.original_filename = "Master_Contract.pdf"
    mock_doc.metadata_ = {
        "summary_concise": {
            "summary": "Cached concise summary of the contract.",
            "key_takeaways": ["Point 1", "Point 2"],
            "generated_at": "2026-10-13T10:00:00",
        }
    }

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_doc
    mock_db.execute.return_value = mock_result

    # Call with force_refresh=False
    res = await summary_svc.get_document_summary(
        db=mock_db,
        user_id=user_id,
        document_id=doc_id,
        mode="concise",
        force_refresh=False,
    )

    assert res["cached"] is True
    assert res["summary"] == "Cached concise summary of the contract."
    assert len(res["key_takeaways"]) == 2


# 6. Deep Research Query Decomposition
@pytest.mark.asyncio
async def test_research_service_decomposition():
    research_svc = ResearchService()
    user_id = uuid.uuid4()

    mock_db = AsyncMock()

    # Mock LLM generation for decomposition and synthesis
    mock_decomp_resp = MagicMock()
    mock_decomp_resp.content = '["What is the liability cap?", "What are the termination clauses?"]'

    mock_synthesis_resp = MagicMock()
    mock_synthesis_resp.content = "Multi-step inquiry synthesis findings: All terms evaluated."

    mock_retrieval_res = MagicMock()
    mock_retrieval_res.results = []

    with patch("app.services.research_service.llm_service.generate") as mock_generate, \
         patch("app.services.research_service.retrieval_service.search", new_callable=AsyncMock) as mock_search:
        mock_generate.side_effect = [mock_decomp_resp, mock_synthesis_resp]
        mock_search.return_value = mock_retrieval_res

        res = await research_svc.execute_deep_research(
            db=mock_db,
            user_id=user_id,
            topic="Investigate contract liability and termination conditions",
            max_subquestions=2,
        )

        assert res["topic"] == "Investigate contract liability and termination conditions"
        assert len(res["subquestions"]) == 2
        assert "liability cap" in res["subquestions"][0]
        assert "synthesis" in res
        assert "has_conflicts" in res


# 7. MockLLMProvider QA: Specific technology and role breakdown without false refusal
@pytest.mark.asyncio
async def test_mock_llm_answers_roles_and_technologies_without_contradiction():
    from app.services.llm.client import MockLLMProvider
    from app.services.llm.prompt import build_rag_messages

    provider = MockLLMProvider()
    evidence = (
        "[S1]\n"
        "Document: Architecture.docx\n"
        "Content:\n"
        "The telemetry pipeline uses FastAPI for REST endpoints, pgvector for semantic retrieval, "
        "and Twilio SMS alerting to notify emergency caregivers when an incident occurs.\n\n"
        "[S2]\n"
        "Document: Overview.docx\n"
        "Content:\n"
        "The project is an automated elder care safety monitor."
    )
    query = "What technologies are used in the system, and what role does each play?"
    messages = build_rag_messages(query=query, context_text=evidence)

    resp = await provider.generate(messages=messages)

    ans = resp.content
    assert "FastAPI" in ans
    assert "pgvector" in ans.lower()
    assert "Twilio" in ans
    # Crucial: Must NOT contradict itself by falsely refusing the role part
    assert "does not mention what role does each play" not in ans.lower()
    assert "no information about what role does each play" not in ans.lower()
    assert "[S1]" in ans


# 8. MockLLMProvider QA: Evaluation metrics extraction
@pytest.mark.asyncio
async def test_mock_llm_extracts_evaluation_metrics():
    from app.services.llm.client import MockLLMProvider
    from app.services.llm.prompt import build_rag_messages

    provider = MockLLMProvider()
    evidence = (
        "[S1]\n"
        "Document: Evaluation.docx\n"
        "Content:\n"
        "The prototype will be evaluated using latency (under 150ms), precision (target 96%), "
        "and false positive rate during continuous 24-hour testing."
    )
    query = "What metrics will be used to evaluate the prototype?"
    messages = build_rag_messages(query=query, context_text=evidence)

    resp = await provider.generate(messages=messages)

    ans = resp.content
    assert "latency" in ans.lower()
    assert "precision" in ans.lower()
    assert "[S1]" in ans


# 9. MockLLMProvider QA: Grounded refusal for unmentioned facts
@pytest.mark.asyncio
async def test_mock_llm_refusal_for_unmentioned_query():
    from app.services.llm.client import MockLLMProvider
    from app.services.llm.prompt import build_rag_messages

    provider = MockLLMProvider()
    evidence = (
        "[S1]\n"
        "Document: DB.docx\n"
        "Content:\n"
        "PostgreSQL 16 with pgvector extension is configured for vector storage."
    )
    query = "What is the recommended dog food brand?"
    messages = build_rag_messages(query=query, context_text=evidence)

    resp = await provider.generate(messages=messages)

    ans = resp.content.lower()
    assert ("not contain" in ans or "no mention" in ans or "not mentioned" in ans or "does not state" in ans)


# 10. Document Service: Resilient extraction fallback when disk JSON is missing
@pytest.mark.asyncio
async def test_document_service_fallback_to_chunks():
    from app.services.document_service import DocumentService
    doc_service = DocumentService()
    user_id = uuid.uuid4()
    doc_id = uuid.uuid4()

    mock_doc = MagicMock(spec=Document)
    mock_doc.id = doc_id
    mock_doc.user_id = user_id
    mock_doc.status = "processed"
    mock_doc.file_type = "docx"
    mock_doc.created_at = None
    mock_doc.metadata_ = {"extracted_path": "missing_extracted.json"}

    chunk1 = MagicMock(spec=DocumentChunk)
    chunk1.id = uuid.uuid4()
    chunk1.document_id = doc_id
    chunk1.chunk_index = 0
    chunk1.content = "Section 1: Architecture Overview and Objectives."
    chunk1.page_number = 1
    chunk1.metadata_ = {"unit_type": "paragraph"}

    chunk2 = MagicMock(spec=DocumentChunk)
    chunk2.id = uuid.uuid4()
    chunk2.document_id = doc_id
    chunk2.chunk_index = 1
    chunk2.content = "Section 2: Telemetry Implementation and Data Flow."
    chunk2.page_number = 1
    chunk2.metadata_ = {"unit_type": "paragraph"}

    mock_db = AsyncMock()

    # First call to get_user_document returns mock_doc
    # Second execute returns chunks
    doc_result = MagicMock()
    doc_result.scalar_one_or_none.return_value = mock_doc

    chunk_result = MagicMock()
    chunk_result.scalars.return_value.all.return_value = [chunk1, chunk2]

    mock_db.execute.side_effect = [doc_result, chunk_result]

    with patch("app.services.document_service.storage_service.load_extracted_json", return_value=None):
        extracted = await doc_service.get_extracted_document(
            db=mock_db,
            user_id=user_id,
            document_id=doc_id,
        )

        assert extracted.document_id == doc_id
        assert extracted.total_units == 2
        assert len(extracted.units) == 2
        assert "Section 1" in extracted.units[0].text
        assert "Section 2" in extracted.units[1].text
        assert extracted.total_words > 0


# 11. Report Service: Schema conformance with filename and excerpt in sources
@pytest.mark.asyncio
async def test_report_service_schema_conformance():
    report_svc = ReportService()
    user_id = uuid.uuid4()
    doc_id = uuid.uuid4()

    mock_doc = MagicMock(spec=Document)
    mock_doc.id = doc_id
    mock_doc.user_id = user_id
    mock_doc.status = "processed"
    mock_doc.filename = "research.pdf"
    mock_doc.original_filename = "AI_Safety_Whitepaper.pdf"

    mock_chunk = MagicMock(spec=DocumentChunk)
    mock_chunk.id = uuid.uuid4()
    mock_chunk.document_id = doc_id
    mock_chunk.chunk_index = 0
    mock_chunk.content = "Key finding: automated fallback mechanisms reduce downtime by 40%."
    mock_chunk.page_number = 1

    mock_db = AsyncMock()
    doc_res = MagicMock()
    doc_res.scalars.return_value.all.return_value = [mock_doc]

    chunk_res = MagicMock()
    chunk_res.scalars.return_value.all.return_value = [mock_chunk]

    mock_db.execute.side_effect = [doc_res, chunk_res]

    res = await report_svc.generate_report(
        db=mock_db,
        user_id=user_id,
        topic="Evaluate safety whitepaper reliability metrics",
        title="Safety Reliability Report",
        document_ids=[doc_id],
    )

    assert res["title"] == "Safety Reliability Report"
    assert res["documents_count"] == 1
    assert len(res["sources"]) == 1
    src = res["sources"][0]
    assert src["filename"] == "AI_Safety_Whitepaper.pdf"
    assert src["document_filename"] == "AI_Safety_Whitepaper.pdf"
    assert "Key finding" in src["excerpt"]
    assert "content_markdown" in res


# 12. Evaluation Service: Telemetry Contract Conformance
@pytest.mark.asyncio
async def test_evaluation_service_contract_conformance():
    from app.services.evaluation_service import EvaluationService
    eval_svc = EvaluationService()
    user_id = uuid.uuid4()

    mock_db = AsyncMock()
    doc_res = MagicMock()
    doc_res.scalar.return_value = 3

    chunk_res = MagicMock()
    chunk_res.scalar.return_value = 24

    mock_msg1 = MagicMock()
    mock_msg1.metadata_ = {"citations": [{"citation_id": "S1"}]}
    mock_msg2 = MagicMock()
    mock_msg2.metadata_ = {"citations": []}

    msg_res = MagicMock()
    msg_res.scalars.return_value.all.return_value = [mock_msg1, mock_msg2]

    mock_db.execute.side_effect = [doc_res, chunk_res, msg_res]

    metrics = await eval_svc.get_system_evaluation_metrics(db=mock_db, user_id=user_id)

    # Validate exact frontend contract fields
    assert "tenant_scope" in metrics
    assert "measured_at" in metrics
    assert "live_metrics" in metrics
    assert "benchmark_metrics" in metrics
    assert "provider_telemetry" in metrics

    lm = metrics["live_metrics"]
    assert lm["processed_documents"] == 3
    assert lm["total_indexed_chunks"] == 24
    assert lm["recent_assistant_messages_sample"] == 2
    assert lm["citation_coverage_pct"] == 50.0
    assert lm["avg_citations_per_answer"] == 0.5

    bm = metrics["benchmark_metrics"]
    assert "dataset" in bm
    assert bm["groundedness_faithfulness_score"] >= 0.90
    assert bm["hallucination_rate_pct"] == 0.0

    pt = metrics["provider_telemetry"]
    assert pt["vector_dimension"] == 1536
    assert pt["hybrid_search_enabled"] is True


# 13. Collection Service: CRUD and Document Assignment
@pytest.mark.asyncio
async def test_collection_service_crud_and_assignment():
    from app.services.collection_service import CollectionService
    col_svc = CollectionService()
    user_id = uuid.uuid4()
    col_id = uuid.uuid4()
    doc_id = uuid.uuid4()

    mock_col = MagicMock()
    mock_col.id = col_id
    mock_col.user_id = user_id
    mock_col.name = "Safety Audits"
    mock_col.description = "Curated security docs"
    mock_col.color = "#267653"
    mock_col.created_at = None
    mock_col.updated_at = None

    mock_doc = MagicMock()
    mock_doc.id = doc_id
    mock_doc.filename = "audit.docx"
    mock_doc.original_filename = "ElderShield_Audit.docx"
    mock_doc.file_type = "docx"
    mock_doc.status = "processed"
    mock_doc.created_at = None

    mock_col.documents = [mock_doc]

    mock_db = AsyncMock()
    col_res = MagicMock()
    col_res.scalar_one_or_none.return_value = mock_col

    mock_db.execute.return_value = col_res

    detail = await col_svc.get_collection_detail(db=mock_db, user_id=user_id, collection_id=col_id)
    assert detail["name"] == "Safety Audits"
    assert detail["documents_count"] == 1
    assert len(detail["documents"]) == 1
    assert detail["documents"][0]["original_filename"] == "ElderShield_Audit.docx"
    assert detail["documents"][0]["filename"] == "audit.docx"


# 14. ElderShield AI Grounded Q&A Verification
@pytest.mark.asyncio
async def test_eldershield_ai_grounded_qa():
    from app.services.llm.client import MockLLMProvider
    from app.services.llm.prompt import build_rag_messages

    provider = MockLLMProvider()
    evidence = (
        "[S1] Document: ElderShield_AI.docx\n"
        "Content:\n"
        "Project Problem: Older adults face escalating financial exploitation and fraud through deceptive messaging, "
        "impersonation attacks, and urgent phishing scams.\n\n"
        "[S2] Document: ElderShield_AI.docx\n"
        "Content:\n"
        "The proposed system architecture comprises a Python FastAPI backend providing real-time linguistic risk scoring, "
        "a React user interface tailored for high-contrast accessibility, and an NLP syntactic analysis engine running local inference to detect coercion patterns.\n\n"
        "[S3] Document: ElderShield_AI.docx\n"
        "Content:\n"
        "ElderShield AI prototype evaluation metrics include scam detection precision, false positive rate across legitimate family messages, "
        "analysis latency under 800 milliseconds, and usability completion rate among senior testing cohorts."
    )

    # Q1: Technologies proposed and their roles
    q1 = "What technologies are proposed for the prototype and what roles do they play?"
    resp1 = await provider.generate(messages=build_rag_messages(query=q1, context_text=evidence))
    ans1 = resp1.content
    assert "FastAPI" in ans1
    assert "React" in ans1
    assert "NLP" in ans1 or "syntactic analysis" in ans1.lower()
    assert "[S2]" in ans1

    # Q2: Evaluation metrics
    q2 = "What are all the evaluation metrics?"
    resp2 = await provider.generate(messages=build_rag_messages(query=q2, context_text=evidence))
    ans2 = resp2.content
    assert "precision" in ans2.lower()
    assert "latency" in ans2.lower() or "false positive" in ans2.lower()
    assert "[S3]" in ans2

    # Q3: Main problem
    q3 = "What is the main problem addressed by the project?"
    resp3 = await provider.generate(messages=build_rag_messages(query=q3, context_text=evidence))
    ans3 = resp3.content
    assert "financial exploitation" in ans3.lower() or "fraud" in ans3.lower() or "deceptive messaging" in ans3.lower()
    assert "[S1]" in ans3

    # Q4: Completely unmentioned topic -> Refusal
    q4 = "What is the company pet policy for dogs in the office?"
    resp4 = await provider.generate(messages=build_rag_messages(query=q4, context_text=evidence))
    ans4 = resp4.content
    assert "do not contain enough information" in ans4.lower()


# 15. Critical Regression: Unit #37 Evaluation Metrics & Methods Extraction
@pytest.mark.asyncio
async def test_eldershield_actual_passage_evaluation_metrics_and_methods():
    from app.services.llm.client import MockLLMProvider
    from app.services.llm.prompt import build_rag_messages
    from app.services.rag.citations import citation_validator
    from app.schemas.retrieval import RetrievalResultItem

    provider = MockLLMProvider()
    actual_source_passage = (
        "The prototype will be evaluated using representative legitimate and suspicious examples. "
        "Performance will be assessed using precision, recall, false-positive rates, and usability testing."
    )
    evidence = (
        f"[S1]\n"
        f"Document: ElderShield AI.docx\n"
        f"Page: N/A\n"
        f"Chunk: 36\n"
        f"Content:\n"
        f"{actual_source_passage}\n"
    )

    query = (
        "List every evaluation metric and evaluation method explicitly mentioned in the ElderShield AI document. "
        "Do not add anything that is not stated in the document."
    )
    messages = build_rag_messages(query=query, context_text=evidence)
    resp = await provider.generate(messages=messages)
    ans = resp.content.lower()

    # Assert all four metrics/methods and the representative examples method are extracted
    assert "precision" in ans
    assert "recall" in ans
    assert "false-positive rates" in ans or "false-positive" in ans
    assert "usability testing" in ans
    assert "representative legitimate and suspicious examples" in ans
    assert "[s1]" in ans

    # Verify citation mapping
    mock_retrieval_item = RetrievalResultItem(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        chunk_index=36,
        content=actual_source_passage,
        similarity_score=0.92,
        cosine_distance=0.08,
        page_number=None,
        metadata={"unit_type": "paragraph"},
        document_filename="ElderShield AI.docx",
        document_original_filename="ElderShield AI.docx",
    )
    validated = citation_validator.extract_and_validate(answer=resp.content, sources=[mock_retrieval_item])
    assert len(validated) == 1
    assert validated[0].citation_id == "S1"
    assert validated[0].chunk_index == 36
    assert validated[0].document_filename == "ElderShield AI.docx"


# 16. Technologies & Roles Extraction Test
@pytest.mark.asyncio
async def test_eldershield_technologies_and_roles_grounded():
    from app.services.llm.client import MockLLMProvider
    from app.services.llm.prompt import build_rag_messages

    provider = MockLLMProvider()
    evidence = (
        "[S1]\n"
        "Document: ElderShield AI.docx\n"
        "Content:\n"
        "The proposed system architecture comprises a Python FastAPI backend providing real-time linguistic risk scoring, "
        "a React user interface tailored for high-contrast accessibility, and an NLP syntactic analysis engine running local inference to detect coercion patterns.\n"
    )

    query = "What technologies are proposed for the prototype and what roles do they play?"
    resp = await provider.generate(messages=build_rag_messages(query=query, context_text=evidence))
    ans = resp.content

    assert "FastAPI" in ans
    assert "React" in ans
    assert "NLP" in ans or "syntactic analysis" in ans.lower()
    assert "[S1]" in ans


# 17. Multi-Part Query (Present topic + Absent topic) Test
@pytest.mark.asyncio
async def test_eldershield_multipart_query_partial_refusal():
    from app.services.llm.client import MockLLMProvider
    from app.services.llm.prompt import build_rag_messages

    provider = MockLLMProvider()
    evidence = (
        "[S1]\n"
        "Document: ElderShield AI.docx\n"
        "Content:\n"
        "The proposed system architecture comprises a Python FastAPI backend providing real-time linguistic risk scoring, "
        "a React user interface tailored for high-contrast accessibility, and an NLP syntactic analysis engine running local inference to detect coercion patterns.\n"
    )

    query = "What technologies are used in the system, and what does it say about 401k retirement benefits?"
    resp = await provider.generate(messages=build_rag_messages(query=query, context_text=evidence))
    ans = resp.content.lower()

    # Must answer about technologies
    assert "fastapi" in ans
    assert "react" in ans
    # Must honestly report missing evidence for the unmentioned topic
    assert "do not contain any information regarding 401k" in ans or "do not contain enough information" in ans


# 18. Completely Unrelated Query Honest Refusal Test
@pytest.mark.asyncio
async def test_eldershield_unrelated_query_honest_refusal():
    from app.services.llm.client import MockLLMProvider
    from app.services.llm.prompt import build_rag_messages, INSUFFICIENT_EVIDENCE_RESPONSE
    from app.services.rag.citations import citation_validator
    from app.schemas.retrieval import RetrievalResultItem

    provider = MockLLMProvider()
    evidence = (
        "[S1]\n"
        "Document: ElderShield AI.docx\n"
        "Content:\n"
        "The prototype will be evaluated using representative legitimate and suspicious examples. "
        "Performance will be assessed using precision, recall, false-positive rates, and usability testing.\n"
    )

    query = "What is the recommended dog food brand and veterinary schedule according to the document?"
    resp = await provider.generate(messages=build_rag_messages(query=query, context_text=evidence))

    assert resp.content == INSUFFICIENT_EVIDENCE_RESPONSE

    # Assert no citations are fabricated
    mock_item = RetrievalResultItem(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        chunk_index=36,
        content=evidence,
        similarity_score=0.1,
        cosine_distance=0.9,
        page_number=None,
        metadata={},
        document_filename="ElderShield AI.docx",
        document_original_filename="ElderShield AI.docx",
    )
    validated = citation_validator.extract_and_validate(answer=resp.content, sources=[mock_item])
    assert len(validated) == 0


# 19. ElderShield AI Structured Information Extraction Quality Test
@pytest.mark.asyncio
async def test_eldershield_structured_extraction_quality():
    from app.services.extraction_service import extraction_service

    user_id = uuid.uuid4()
    doc_id = uuid.uuid4()

    mock_doc = MagicMock(spec=Document)
    mock_doc.id = doc_id
    mock_doc.user_id = user_id
    mock_doc.filename = "ElderShield AI.docx"
    mock_doc.original_filename = "ElderShield AI.docx"

    # Persisted chunks representing ElderShield AI document sections
    c1 = MagicMock(spec=DocumentChunk)
    c1.chunk_index = 0
    c1.page_number = None
    c1.content = (
        "Problem Statement: Older adults face escalating financial exploitation and fraud through deceptive messaging, "
        "impersonation attacks, and urgent phishing scams. ElderShield AI is an AI-powered digital safety assistant "
        "designed to help seniors assess suspicious text messages and communications."
    )

    c2 = MagicMock(spec=DocumentChunk)
    c2.chunk_index = 1
    c2.page_number = None
    c2.content = (
        "System Architecture: The proposed system architecture comprises a Python FastAPI backend providing real-time "
        "linguistic risk scoring, a React user interface tailored for senior-friendly accessibility, and an NLP "
        "syntactic analysis engine running local machine learning models to detect coercion patterns. "
        "URL parsing/security checks inspect embedded hyperlinks."
    )

    c3 = MagicMock(spec=DocumentChunk)
    c3.chunk_index = 2
    c3.page_number = None
    c3.content = (
        "Recommendations: Users are advised to independently verify the sender through alternative trusted channels, "
        "avoid clicking unknown links in unexpected messages, and never share confidential credentials or banking passwords."
    )

    c4 = MagicMock(spec=DocumentChunk)
    c4.chunk_index = 36
    c4.page_number = None
    c4.content = (
        "Evaluation Criteria: The prototype will be evaluated using representative legitimate and suspicious examples. "
        "Performance will be assessed using precision, recall, false-positive rates, and usability testing with senior participant cohorts."
    )

    mock_db = AsyncMock()
    doc_exec = MagicMock()
    doc_exec.scalar_one_or_none.return_value = mock_doc

    chunk_exec = MagicMock()
    chunk_exec.scalars.return_value.all.return_value = [c1, c2, c3, c4]

    mock_db.execute.side_effect = [doc_exec, chunk_exec]

    res = await extraction_service.extract_structured_data(
        db=mock_db,
        user_id=user_id,
        document_id=doc_id,
    )

    assert res["document_id"] == str(doc_id)
    assert res["document_filename"] == "ElderShield AI.docx"
    data = res["data"]

    # 1. Entity Extraction Assertions
    ent_names = [e["name"] for e in data.get("entities", [])]
    ent_types = {e["name"]: e["type"] for e in data.get("entities", [])}

    assert "ElderShield AI" in ent_names
    assert ent_types["ElderShield AI"] == "PRODUCT"
    # No overlapping or sentence fragments
    assert "ElderShield AI proposes an AI" not in ent_names
    assert "proposes an AI" not in ent_names
    assert "Powered Digital Safety" not in ent_names
    # Headings must NOT be classified as entities or technologies
    assert "Problem Statement" not in ent_names
    assert "System Architecture" not in ent_names
    assert "Evaluation Criteria" not in ent_names
    assert "Recommendations" not in ent_names

    # Named technologies
    assert "FastAPI" in ent_names
    assert "Python" in ent_names
    assert "React" in ent_names
    assert "NLP" in ent_names
    assert "Machine learning models" in ent_names
    assert "URL parsing/security checks" in ent_names

    # Context must be preserved
    for e in data.get("entities", []):
        assert e.get("context") and len(e["context"]) > 5

    # 2. Risk Extraction Assertions
    risk_names = [r["risk"] for r in data.get("risks", [])]
    assert any("phishing" in r.lower() for r in risk_names)
    assert any("fraud" in r.lower() for r in risk_names)
    assert any("impersonation" in r.lower() for r in risk_names)
    assert any("financial" in r.lower() for r in risk_names)
    # Problem Statement heading must NOT be classified as an individual risk
    assert "Problem Statement" not in risk_names
    assert not any(r.lower().startswith("problem statement:") for r in risk_names)
    # Severity must NOT be fabricated as HIGH or MEDIUM
    for r in data.get("risks", []):
        assert r.get("severity") in (None, "Unassigned")

    # 3. Action Items Assertions
    action_items = [a["item"] for a in data.get("action_items", [])]
    assert any("verify" in a.lower() for a in action_items)
    assert any("unknown links" in a.lower() for a in action_items)
    assert any("credentials" in a.lower() for a in action_items)
    # Assignee must NOT be fabricated as Engineering / Assessment Team
    for a in data.get("action_items", []):
        assert a.get("assignee") in (None, "Unassigned")
        assert "Engineering" not in str(a.get("assignee", ""))

    # 4. Metrics & Evaluation Assertions
    metric_names = [m["metric"] for m in data.get("metrics", [])]
    metric_units = {m["metric"]: m.get("unit") for m in data.get("metrics", [])}

    assert "Precision" in metric_names
    assert metric_units["Precision"] == "Evaluation Metric"
    assert "Recall" in metric_names
    assert metric_units["Recall"] == "Evaluation Metric"
    assert "False-positive rate" in metric_names
    assert metric_units["False-positive rate"] == "Evaluation Metric"
    assert "Usability testing" in metric_names
    assert metric_units["Usability testing"] == "Evaluation Method"
    assert "Representative legitimate and suspicious examples" in metric_names
    assert metric_units["Representative legitimate and suspicious examples"] == "Evaluation Material / Dataset"

    # 5. Dates & Obligations: Must be empty arrays for ElderShield AI
    assert data.get("dates") == []
    assert data.get("obligations") == []

    # 6. CSV Export Test
    csv_content = extraction_service.export_as_csv(res)
    assert "Category,Item / Name,Detail / Value,Context / Entity Type,Page" in csv_content
    assert "ElderShield AI" in csv_content
    assert "FastAPI" in csv_content
    assert "Precision" in csv_content
    assert "Representative legitimate and suspicious examples" in csv_content
    assert "Unassigned" in csv_content


# 20. Structured Information Extraction Contract Edge Case Test
@pytest.mark.asyncio
async def test_structured_extraction_edge_case_contract():
    from app.services.extraction_service import extraction_service

    user_id = uuid.uuid4()
    doc_id = uuid.uuid4()

    mock_doc = MagicMock(spec=Document)
    mock_doc.id = doc_id
    mock_doc.user_id = user_id
    mock_doc.filename = "Master_Services_Agreement.pdf"
    mock_doc.original_filename = "Master_Services_Agreement.pdf"

    c1 = MagicMock(spec=DocumentChunk)
    c1.chunk_index = 0
    c1.page_number = 1
    c1.content = (
        "Agreement Effective Date: 2026-06-01 between Initech Corp and Acme Corp. "
        "Vendor shall maintain 99.9% service availability during all business hours. "
        "Acme Corp shall remit payment within 30 days of invoice receipt."
    )

    mock_db = AsyncMock()
    doc_exec = MagicMock()
    doc_exec.scalar_one_or_none.return_value = mock_doc
    chunk_exec = MagicMock()
    chunk_exec.scalars.return_value.all.return_value = [c1]
    mock_db.execute.side_effect = [doc_exec, chunk_exec]

    res = await extraction_service.extract_structured_data(
        db=mock_db,
        user_id=user_id,
        document_id=doc_id,
    )
    data = res["data"]

    # When explicit calendar dates are present, they are extracted
    assert len(data.get("dates", [])) >= 1
    assert "2026-06-01" in [d["date"] for d in data.get("dates", [])]

    # When explicit contractual covenants are present, they are extracted
    assert len(data.get("obligations", [])) >= 1
    parties = [o["party"] for o in data.get("obligations", [])]
    assert any("Vendor" in p or "Acme" in p for p in parties)

    # When percentages are present, they are extracted
    assert any("99.9%" in m["value"] for m in data.get("metrics", []))

    # Entities
    ent_names = [e["name"] for e in data.get("entities", [])]
    assert "Initech Corp" in ent_names or "Acme Corp" in ent_names


# 21. ElderShield AI Concise Executive Summary Grounding Test
@pytest.mark.asyncio
async def test_eldershield_concise_summary_grounding():
    from app.services.summary_service import summary_service

    user_id = uuid.uuid4()
    doc_id = uuid.uuid4()

    mock_doc = MagicMock(spec=Document)
    mock_doc.id = doc_id
    mock_doc.user_id = user_id
    mock_doc.status = "processed"
    mock_doc.filename = "ElderShield AI.docx"
    mock_doc.original_filename = "ElderShield AI.docx"
    mock_doc.metadata_ = {}

    # Chunks representing document sections
    c_prob = MagicMock(spec=DocumentChunk)
    c_prob.chunk_index = 5
    c_prob.page_number = None
    c_prob.content = (
        "With the increasing use of smartphones, digital payments, and online communication, senior citizens are becoming "
        "more exposed to phishing links, fraudulent messages, impersonation attempts, and scam calls. Many elderly people find "
        "it difficult to identify these threats, which can lead to financial losses, identity theft, privacy breaches, and reduced confidence in digital services."
    )

    c_sol = MagicMock(spec=DocumentChunk)
    c_sol.chunk_index = 6
    c_sol.page_number = None
    c_sol.content = (
        "ElderShield AI proposes an AI-powered digital safety assistant that helps users assess suspicious communications before taking action. "
        "The platform will analyze submitted text messages and URLs using Natural Language Processing (NLP), machine learning techniques, and URL security checks. "
        "It will identify potential warning signs, assign a risk category, explain why the content may be suspicious, and recommend appropriate safety measures in simple language."
    )

    c_aud_pri = MagicMock(spec=DocumentChunk)
    c_aud_pri.chunk_index = 9
    c_aud_pri.page_number = None
    c_aud_pri.content = (
        "The primary target audience is senior citizens who use smartphones, messaging applications, online banking, and other digital services but may have difficulty recognizing evolving online scams."
    )

    c_aud_sec = MagicMock(spec=DocumentChunk)
    c_aud_sec.chunk_index = 10
    c_aud_sec.page_number = None
    c_aud_sec.content = (
        "Secondary beneficiaries include family members, caregivers, community organizations, and digital literacy initiatives that support elderly people in using technology safely."
    )

    c_tech = MagicMock(spec=DocumentChunk)
    c_tech.chunk_index = 29
    c_tech.page_number = None
    c_tech.content = (
        "The proposed prototype will use Python for the detection engine, FastAPI for backend services, and React for the user interface. "
        "NLP libraries and machine learning models will analyze message content, while URL parsing and security checks will assess suspicious links."
    )

    c_eval = MagicMock(spec=DocumentChunk)
    c_eval.chunk_index = 36
    c_eval.page_number = None
    c_eval.content = (
        "The prototype will be evaluated using representative legitimate and suspicious examples. Performance will be assessed using precision, recall, false-positive rates, and usability testing with senior participant cohorts."
    )

    c_imp = MagicMock(spec=DocumentChunk)
    c_imp.chunk_index = 16
    c_imp.page_number = None
    c_imp.content = (
        "Reduced exposure to fraud: Encouraging users to verify suspicious communications before clicking links, sharing personal information, or making payments. "
        "Expected positive impacts include improved digital literacy, greater independence, and privacy awareness."
    )

    mock_db = AsyncMock()
    doc_exec = MagicMock()
    doc_exec.scalar_one_or_none.return_value = mock_doc

    chunk_exec = MagicMock()
    chunk_exec.scalars.return_value.all.return_value = [c_prob, c_sol, c_aud_pri, c_aud_sec, c_tech, c_eval, c_imp]

    mock_db.execute.side_effect = [doc_exec, chunk_exec]

    res = await summary_service.get_document_summary(
        db=mock_db,
        user_id=user_id,
        document_id=doc_id,
        mode="concise",
        force_refresh=True,
    )

    assert res["document_id"] == str(doc_id)
    assert res["mode"] == "concise"
    summary_text = res["summary"]
    takeaways = res["key_takeaways"]

    # 1. Central problem verified
    assert "senior citizens" in summary_text.lower()
    assert "phishing" in summary_text.lower()
    assert "fraudulent messages" in summary_text.lower() or "fraud" in summary_text.lower()
    assert "impersonation" in summary_text.lower()
    assert "scam calls" in summary_text.lower() or "scam" in summary_text.lower()

    # 2. Proposed solution verified
    assert "safety assistant" in summary_text.lower() or "eldershield ai" in summary_text.lower()
    assert "urls" in summary_text.lower()
    assert "risk" in summary_text.lower()

    # 3. Target audience verified
    assert "caregivers" in summary_text.lower() or "family members" in summary_text.lower()

    # 4. Technical approach verified
    assert "python" in summary_text.lower()
    assert "fastapi" in summary_text.lower()
    assert "react" in summary_text.lower()

    # 5. Takeaways count & grounding
    assert len(takeaways) >= 3
    assert any("problem" in t.lower() for t in takeaways)
    assert any("solution" in t.lower() for t in takeaways)
    assert any("target" in t.lower() or "audience" in t.lower() for t in takeaways)
    assert any("technical" in t.lower() or "stack" in t.lower() for t in takeaways)

    # 6. No generic boilerplate
    assert "engineered to protect users and enhance communication security" not in summary_text.lower()
    assert "structured across modular components" not in summary_text.lower()

    # 7. Citations present and valid
    assert "[s" in summary_text.lower()
    for t in takeaways:
        assert "[s" in t.lower()


# 22. ElderShield AI Detailed Summary & Mode Differentiation Test
@pytest.mark.asyncio
async def test_eldershield_detailed_summary_and_mode_differentiation():
    from app.services.summary_service import summary_service

    user_id = uuid.uuid4()
    doc_id = uuid.uuid4()

    mock_doc = MagicMock(spec=Document)
    mock_doc.id = doc_id
    mock_doc.user_id = user_id
    mock_doc.status = "processed"
    mock_doc.filename = "ElderShield AI.docx"
    mock_doc.original_filename = "ElderShield AI.docx"
    mock_doc.metadata_ = {}

    all_chunks = [
        MagicMock(spec=DocumentChunk, chunk_index=i, page_number=None, content=f"Chunk {i} content")
        for i in range(10)
    ]
    all_chunks[0].content = "ElderShield AI: AI-Powered Digital Safety Assistant for Senior Citizens."
    all_chunks[1].content = "With the increasing use of smartphones, senior citizens are becoming more exposed to phishing links, fraudulent messages, impersonation attempts, and scam calls."
    all_chunks[2].content = "ElderShield AI proposes an AI-powered digital safety assistant that analyzes submitted text messages and URLs using NLP and security checks."
    all_chunks[3].content = "Primary target audience is senior citizens, with secondary beneficiaries including family members, caregivers, and community organizations."
    all_chunks[4].content = "Technical approach: Python detection engine, FastAPI backend services, React user interface, NLP models, and URL parsing/security checks."
    all_chunks[5].content = "Evaluation: Precision, recall, false-positive rates, and usability testing with senior participant cohorts using representative legitimate and suspicious examples."
    all_chunks[6].content = "Expected positive impacts include improved digital literacy, reduced exposure to fraud, greater independence, and privacy awareness."
    all_chunks[7].content = "The platform communicates security risks clearly without making unrealistic guarantees."

    mock_db = AsyncMock()
    doc_exec = MagicMock()
    doc_exec.scalar_one_or_none.return_value = mock_doc

    chunk_exec = MagicMock()
    chunk_exec.scalars.return_value.all.return_value = all_chunks

    mock_db.execute.side_effect = [doc_exec, chunk_exec]

    detailed_res = await summary_service.get_document_summary(
        db=mock_db,
        user_id=user_id,
        document_id=doc_id,
        mode="detailed",
        force_refresh=True,
    )

    det_summary = detailed_res["summary"]
    det_takeaways = detailed_res["key_takeaways"]

    # 1. Verification of evaluation criteria in detailed summary
    assert "precision" in det_summary.lower()
    assert "recall" in det_summary.lower()
    assert "false-positive" in det_summary.lower()
    assert "usability testing" in det_summary.lower()
    assert "representative legitimate and suspicious" in det_summary.lower()

    # 2. Verification of expected social impact & ethical boundaries
    assert "digital literacy" in det_summary.lower()
    assert "reduced exposure to fraud" in det_summary.lower() or "fraud" in det_summary.lower()
    assert "independence" in det_summary.lower()
    assert "privacy awareness" in det_summary.lower()
    assert "unrealistic guarantees" in det_summary.lower()

    # 3. Takeaways count
    assert len(det_takeaways) >= 5

    # 4. No invented benchmark scores
    assert "99." not in det_summary
    assert "100%" not in det_summary


# 23. Summary Stale Boilerplate Invalidation Test
@pytest.mark.asyncio
async def test_summary_stale_boilerplate_invalidation():
    from app.services.summary_service import summary_service

    user_id = uuid.uuid4()
    doc_id = uuid.uuid4()

    mock_doc = MagicMock(spec=Document)
    mock_doc.id = doc_id
    mock_doc.user_id = user_id
    mock_doc.status = "processed"
    mock_doc.filename = "ElderShield AI.docx"
    mock_doc.original_filename = "ElderShield AI.docx"
    # Metadata contains old stale generic boilerplate
    mock_doc.metadata_ = {
        "summary_concise": {
            "summary": "ElderShield AI. [S1]. Engineered to protect users and enhance communication security [S1].",
            "key_takeaways": ["- Structured across modular components with verifiable quality standards [S2]."],
            "generated_at": "2026-10-10T00:00:00",
        }
    }

    c1 = MagicMock(spec=DocumentChunk, chunk_index=0, page_number=None, content="ElderShield AI text")

    mock_db = AsyncMock()
    doc_exec = MagicMock()
    doc_exec.scalar_one_or_none.return_value = mock_doc
    chunk_exec = MagicMock()
    chunk_exec.scalars.return_value.all.return_value = [c1]
    mock_db.execute.side_effect = [doc_exec, chunk_exec]

    # Without force_refresh, the service should detect stale generic boilerplate and refresh it automatically
    res = await summary_service.get_document_summary(
        db=mock_db,
        user_id=user_id,
        document_id=doc_id,
        mode="concise",
        force_refresh=False,
    )

    assert "Engineered to protect users" not in res["summary"]
    assert "Structured across modular components" not in " ".join(res["key_takeaways"])


# 24. ElderShield AI Research Report Grounding and Title Derivation Test
@pytest.mark.asyncio
async def test_eldershield_research_report_grounding():
    from app.services.report_service import ReportService

    report_svc = ReportService()
    user_id = uuid.uuid4()
    doc_id = uuid.uuid4()

    mock_doc = MagicMock(spec=Document)
    mock_doc.id = doc_id
    mock_doc.user_id = user_id
    mock_doc.status = "processed"
    mock_doc.filename = "ElderShield AI.docx"
    mock_doc.original_filename = "ElderShield AI.docx"

    # Full set of chunks matching ElderShield AI structure
    c_prob = MagicMock(spec=DocumentChunk, id=uuid.uuid4(), document_id=doc_id, chunk_index=5, page_number=None)
    c_prob.content = (
        "With the increasing use of smartphones, digital payments, and online communication, senior citizens are becoming "
        "more exposed to phishing links, fraudulent messages, impersonation attempts, and scam calls. Many elderly people find "
        "it difficult to identify these threats, which can lead to financial losses, identity theft, privacy breaches, and reduced confidence in digital services."
    )

    c_sol = MagicMock(spec=DocumentChunk, id=uuid.uuid4(), document_id=doc_id, chunk_index=6, page_number=None)
    c_sol.content = (
        "ElderShield AI proposes an AI-powered digital safety assistant that helps users assess suspicious communications before taking action. "
        "The platform will analyze submitted text messages and URLs using Natural Language Processing (NLP), machine learning techniques, and URL security checks. "
        "It will identify potential warning signs, assign a risk category, explain why the content may be suspicious, and recommend appropriate safety measures in simple language."
    )

    c_aud_pri = MagicMock(spec=DocumentChunk, id=uuid.uuid4(), document_id=doc_id, chunk_index=9, page_number=None)
    c_aud_pri.content = (
        "The primary target audience is senior citizens who use smartphones, messaging applications, online banking, and other digital services but may have difficulty recognizing evolving online scams."
    )

    c_aud_sec = MagicMock(spec=DocumentChunk, id=uuid.uuid4(), document_id=doc_id, chunk_index=10, page_number=None)
    c_aud_sec.content = (
        "Secondary beneficiaries include family members, caregivers, community organizations, and digital literacy initiatives that support elderly people in using technology safely."
    )

    c_feat1 = MagicMock(spec=DocumentChunk, id=uuid.uuid4(), document_id=doc_id, chunk_index=22, page_number=None)
    c_feat1.content = "Suspicious Message Detection: The assistant analyzes submitted text messages for indicators of urgency, coercive language, impersonation, and fraudulent payment solicitations."

    c_feat2 = MagicMock(spec=DocumentChunk, id=uuid.uuid4(), document_id=doc_id, chunk_index=23, page_number=None)
    c_feat2.content = "URL Risk Analysis: Examines submitted links for suspicious domain characteristics, misleading addresses, and phishing indicators."

    c_feat3 = MagicMock(spec=DocumentChunk, id=uuid.uuid4(), document_id=doc_id, chunk_index=24, page_number=None)
    c_feat3.content = "AI-Based Risk Classification: Categorizes content into understandable levels (Low Risk, Suspicious, High Risk) based on the available evidence."

    c_feat4 = MagicMock(spec=DocumentChunk, id=uuid.uuid4(), document_id=doc_id, chunk_index=25, page_number=None)
    c_feat4.content = "Explainable Alerts: Highlights warning signs and explains the underlying reasons for a risk assessment in simple language."

    c_feat5 = MagicMock(spec=DocumentChunk, id=uuid.uuid4(), document_id=doc_id, chunk_index=26, page_number=None)
    c_feat5.content = "Actionable Safety Guidance: Recommends concrete steps, such as independently verifying senders through trusted alternative channels, avoiding unknown links, and never sharing confidential credentials."

    c_feat6 = MagicMock(spec=DocumentChunk, id=uuid.uuid4(), document_id=doc_id, chunk_index=27, page_number=None)
    c_feat6.content = "Accessible User Interface: Provides a straightforward interface tailored for senior citizens, featuring readable typography, clear visual alerts, and simple navigation."

    c_tech = MagicMock(spec=DocumentChunk, id=uuid.uuid4(), document_id=doc_id, chunk_index=29, page_number=None)
    c_tech.content = (
        "The proposed prototype will use Python for the detection engine, FastAPI for backend services, and React for the user interface. "
        "NLP libraries and machine learning models will analyze message content, while URL parsing and security checks will assess suspicious links."
    )

    c_eval = MagicMock(spec=DocumentChunk, id=uuid.uuid4(), document_id=doc_id, chunk_index=36, page_number=None)
    c_eval.content = (
        "The prototype will be evaluated using representative legitimate and suspicious examples. Performance will be assessed using precision, recall, false-positive rates, and usability testing with senior participant cohorts."
    )

    c_scope = MagicMock(spec=DocumentChunk, id=uuid.uuid4(), document_id=doc_id, chunk_index=42, page_number=None)
    c_scope.content = (
        "The project is initially scoped as a web-based prototype to validate core functionality and user experience. "
        "The platform is intended to complement existing security tools and awareness programs, communicating risks clearly without making unrealistic guarantees."
    )

    mock_db = AsyncMock()
    doc_res = MagicMock()
    doc_res.scalars.return_value.all.return_value = [mock_doc]

    chunk_res = MagicMock()
    chunk_res.scalars.return_value.all.return_value = [
        c_prob, c_sol, c_aud_pri, c_aud_sec,
        c_feat1, c_feat2, c_feat3, c_feat4, c_feat5, c_feat6,
        c_tech, c_eval, c_scope
    ]

    mock_db.execute.side_effect = [doc_res, chunk_res]

    # Test report generation when user provides generic action label "Summarize Document"
    res = await report_svc.generate_report(
        db=mock_db,
        user_id=user_id,
        topic="Summarize Document",
        title=None,
        document_ids=[doc_id],
    )

    # 1. Title and identity assertions:
    assert res["title"] == "ElderShield AI Research Report"
    assert "Summarize Document" not in res["title"]
    assert "Intelligence Report: Summarize Document" != res["title"]
    assert "ElderShield AI" in res["topic"]

    md = res["content_markdown"]

    # 2. Section structure assertions (7 mandatory sections):
    assert "## 1. Executive Summary" in md
    assert "## 2. Scope and Target Audience" in md
    assert "## 3. Proposed Solution and Features" in md
    assert "## 4. Technical Approach" in md
    assert "## 5. Evaluation Plan" in md
    assert "## 6. Risks and Limitations" in md
    assert "## 7. Recommendations" in md

    # 3. Grounded technical approach assertions:
    assert "Python" in md
    assert "FastAPI" in md
    assert "React" in md
    assert "NLP" in md or "Natural Language Processing" in md
    assert "machine learning models" in md.lower()
    assert "url parsing" in md.lower() or "security checks" in md.lower()

    # 4. Grounded target audience assertions:
    assert "senior citizens" in md.lower()
    assert "caregivers" in md.lower()
    assert "family members" in md.lower()
    assert "community organizations" in md.lower()
    assert "digital literacy initiatives" in md.lower()

    # 5. Grounded features assertions:
    assert "suspicious message detection" in md.lower()
    assert "url risk analysis" in md.lower()
    assert "risk classification" in md.lower()
    assert "explainable alerts" in md.lower()
    assert "actionable safety guidance" in md.lower()
    assert "accessible user interface" in md.lower()

    # 6. Evaluation plan assertions:
    assert "precision" in md.lower()
    assert "recall" in md.lower()
    assert "false-positive" in md.lower()
    assert "usability testing" in md.lower()
    assert "representative legitimate and suspicious" in md.lower()

    # 7. Explicitly labeled limitations & inferred recommendations:
    assert "[Document Limitation]" in md
    assert "[Inferred System Recommendation]" in md
    assert "Stated in Source:" in md
    assert "Inferred System Recommendations:" in md

    # 8. Negative checks against ungrounded enterprise boilerplate:
    assert "multimodal capabilities" not in md.lower()
    assert "model drift" not in md.lower()
    assert "multi-factor verification" not in md.lower()
    assert "system separation of concerns" not in md.lower()

    # 9. Citations and Source Manifest integrity:
    assert len(res["sources"]) == 13
    for src in res["sources"]:
        assert src["filename"] == "ElderShield AI.docx"
        assert src["document_filename"] == "ElderShield AI.docx"
        assert "chunk_id" in src
        assert "chunk_index" in src
        assert "excerpt" in src and len(src["excerpt"]) > 0

    # Ensure citations [S#] exist in the report markdown
    assert "[S" in md


# 25. Research Report Retrieval at Document End Test
@pytest.mark.asyncio
async def test_research_report_retrieval_at_document_end():
    from app.services.report_service import ReportService

    report_svc = ReportService()
    user_id = uuid.uuid4()
    doc_id = uuid.uuid4()

    mock_doc = MagicMock(spec=Document)
    mock_doc.id = doc_id
    mock_doc.user_id = user_id
    mock_doc.status = "processed"
    mock_doc.filename = "Long_Document.pdf"
    mock_doc.original_filename = "Long_Document.pdf"

    # Create 45 mock chunks where key evaluation data is at chunk 40
    chunks = []
    for i in range(45):
        c = MagicMock(spec=DocumentChunk, id=uuid.uuid4(), document_id=doc_id, chunk_index=i, page_number=i + 1)
        if i == 40:
            c.content = "Evaluation Benchmarks: Target latency under 150ms with 99.5% accuracy achieved in final validation trials."
        elif i == 0:
            c.content = "Project Alpha overview and introductory background."
        else:
            c.content = f"Intermediary technical documentation paragraph {i} providing system specifications."
        chunks.append(c)

    mock_db = AsyncMock()
    doc_res = MagicMock()
    doc_res.scalars.return_value.all.return_value = [mock_doc]

    chunk_res = MagicMock()
    chunk_res.scalars.return_value.all.return_value = chunks

    mock_db.execute.side_effect = [doc_res, chunk_res]

    res = await report_svc.generate_report(
        db=mock_db,
        user_id=user_id,
        topic="Evaluate Alpha System",
        document_ids=[doc_id],
    )

    # All 45 chunks were retrieved (retrieval limit is 100 for single doc, not 5)
    assert len(res["sources"]) == 45
    # The chunk at index 40 is present in the source manifest
    chunk_indices = [s["chunk_index"] for s in res["sources"]]
    assert 40 in chunk_indices
    assert any("latency under 150ms" in s["excerpt"] for s in res["sources"])


# 26. Research Report Tenant Isolation Test
@pytest.mark.asyncio
async def test_research_report_tenant_isolation():
    from app.services.report_service import ReportService

    report_svc = ReportService()
    owner_user_id = uuid.uuid4()
    attacker_user_id = uuid.uuid4()
    doc_id = uuid.uuid4()

    mock_db = AsyncMock()
    # Query for document belonging to attacker_user_id returns empty
    doc_res = MagicMock()
    doc_res.scalars.return_value.all.return_value = []
    mock_db.execute.return_value = doc_res

    with pytest.raises(HTTPException) as exc_info:
        await report_svc.generate_report(
            db=mock_db,
            user_id=attacker_user_id,
            topic="Steal confidential data",
            document_ids=[doc_id],
        )

    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
    assert "access denied" in exc_info.value.detail.lower() or "not found" in exc_info.value.detail.lower()

