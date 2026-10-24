import io
import json
import uuid
from pathlib import Path
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException

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



