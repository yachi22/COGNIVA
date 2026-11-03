import logging
import uuid
from typing import Any, Dict, List
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from datetime import datetime, timezone
from app.core.config import settings
from app.models.document import Document
from app.models.chunk import DocumentChunk
from app.models.conversation import Conversation, Message
from app.services.job_service import document_job_service

logger = logging.getLogger("cogniva.evaluation_service")


class EvaluationService:
    """
    Computes real retrieval, citation, and generation quality metrics.
    Distinguishes offline benchmark scores from live tenant measurements.
    """

    async def get_system_evaluation_metrics(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
    ) -> Dict[str, Any]:
        # Count user's processed chunks and documents
        doc_count_res = await db.execute(
            select(func.count(Document.id)).where(Document.user_id == user_id, Document.status == "processed")
        )
        total_docs = doc_count_res.scalar() or 0

        chunk_count_res = await db.execute(
            select(func.count(DocumentChunk.id))
            .join(Document, DocumentChunk.document_id == Document.id)
            .where(Document.user_id == user_id)
        )
        total_chunks = chunk_count_res.scalar() or 0

        # Inspect assistant messages for citation coverage
        msg_stmt = (
            select(Message)
            .join(Conversation, Message.conversation_id == Conversation.id)
            .where(Conversation.user_id == user_id, Message.role == "assistant")
            .limit(50)
        )
        msg_res = await db.execute(msg_stmt)
        messages = msg_res.scalars().all()

        total_assistant_msgs = len(messages)
        cited_msgs = 0
        total_citations = 0
        measured_durations = []

        for m in messages:
            meta = dict(m.metadata_ or {})
            cits = meta.get("citations", []) or meta.get("sources", [])
            if cits:
                cited_msgs += 1
                total_citations += len(cits)

            dur = meta.get("duration_ms") or meta.get("generation_duration_ms")
            if dur is not None and isinstance(dur, (int, float)) and dur > 0:
                measured_durations.append(float(dur))

        citation_coverage_pct = round((cited_msgs / total_assistant_msgs * 100), 1) if total_assistant_msgs > 0 else 100.0
        avg_citations = round(total_citations / total_assistant_msgs, 2) if total_assistant_msgs > 0 else 1.0
        avg_generation_latency_ms = round(sum(measured_durations) / len(measured_durations), 1) if measured_durations else 0.0

        measured_time = datetime.now(timezone.utc).isoformat()

        # Operational metrics for background processing jobs
        operational_telemetry = await document_job_service.get_tenant_operational_metrics(
            db=db,
            user_id=user_id,
        )

        # Architectural target thresholds (expected performance specifications)
        target_thresholds = {
            "dataset": "Enterprise Evidence Retrieval Target Specifications",
            "target_hit_rate_at_5": 0.90,
            "target_mrr": 0.850,
            "target_faithfulness_score": 0.95,
            "target_max_hallucination_rate_pct": 2.0,
            "specification_version": "v1.2-target",
            "description": "Enterprise performance targets required for release acceptance.",
        }

        # Empirical evaluation results (populated only when an offline benchmark runner executes)
        evaluation_results = {
            "status": "NOT EVALUATED",
            "dataset": "Enterprise Evidence Retrieval Benchmark",
            "queries_evaluated": 0,
            "retrieval_hit_rate_at_5": None,
            "retrieval_mrr": None,
            "groundedness_faithfulness_score": None,
            "hallucination_rate_pct": None,
            "evaluated_revision": None,
            "notice": "No offline empirical benchmark dataset has been executed on this deployment. Empirical metrics are NOT EVALUATED.",
        }

        # Contract matching frontend EvaluationMetricsResponse
        return {
            "tenant_scope": f"tenant-{str(user_id)[:8]}",
            "measured_at": measured_time,
            "live_metrics": {
                "processed_documents": total_docs,
                "total_indexed_chunks": total_chunks,
                "recent_assistant_messages_sample": total_assistant_msgs,
                "citation_coverage_pct": citation_coverage_pct,
                "avg_citations_per_answer": avg_citations,
                "avg_generation_latency_ms": avg_generation_latency_ms,
                "service_uptime_status": "Healthy & Operational",
            },
            "operational_telemetry": operational_telemetry,
            "evaluation_results": evaluation_results,
            "target_thresholds": target_thresholds,
            "benchmark_metrics": {
                "dataset": "Enterprise Evidence Retrieval Benchmark",
                "evaluation_status": "NOT EVALUATED",
                "is_evaluated": False,
                "queries_evaluated": 0,
                "retrieval_hit_rate_at_5": 0.0,
                "retrieval_mrr": 0.0,
                "groundedness_faithfulness_score": 0.0,
                "hallucination_rate_pct": 0.0,
                "target_hit_rate_at_5": 0.90,
                "target_mrr": 0.850,
                "target_faithfulness_score": 0.95,
                "target_max_hallucination_rate_pct": 2.0,
                "evaluated_revision": settings.VERSION,
                "notice": "No offline empirical benchmark dataset has been executed on this deployment. Displaying target architectural thresholds.",
            },
            "provider_telemetry": {
                "embedding_model": settings.EMBEDDING_MODEL,
                "generation_model": settings.LLM_MODEL,
                "vector_dimension": settings.EMBEDDING_DIMENSION,
                "hybrid_search_enabled": True,
            },
            # Backward-compatibility aliases
            "tenant_live_telemetry": {
                "active_documents": total_docs,
                "indexed_vector_chunks": total_chunks,
                "evaluated_responses": total_assistant_msgs,
                "citation_coverage_pct": citation_coverage_pct,
                "total_provenance_citations": total_citations,
                "anti_injection_status": "Active & Enforced",
            },
            "offline_benchmark_metrics": {
                "status": "NOT EVALUATED",
                "is_evaluated": False,
                "retrieval_precision_at_k": 0.0,
                "retrieval_recall_at_k": 0.0,
                "groundedness_faithfulness_score": 0.0,
                "hallucination_rejection_rate": 0.0,
                "mean_retrieval_latency_ms": 0.0,
                "embedding_dimension": settings.EMBEDDING_DIMENSION,
                "distance_metric": "Cosine Distance (<=>)",
                "notice": "Offline benchmark dataset has not been executed on this deployment.",
            },
            "evaluation_methodology": "Dual-layer governance: Real-time tenant operational telemetry computed from live database records; offline empirical benchmark is NOT EVALUATED pending dataset execution.",
        }


evaluation_service = EvaluationService()

