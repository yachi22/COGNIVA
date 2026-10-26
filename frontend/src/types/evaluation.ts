export interface EvaluationMetricsResponse {
  tenant_scope: string;
  measured_at: string;
  live_metrics: {
    processed_documents: number;
    total_indexed_chunks: number;
    recent_assistant_messages_sample: number;
    citation_coverage_pct: number;
    avg_citations_per_answer: number;
    avg_generation_latency_ms: number;
    service_uptime_status: string;
  };
  benchmark_metrics: {
    dataset: string;
    queries_evaluated: number;
    retrieval_hit_rate_at_5: number;
    retrieval_mrr: number;
    groundedness_faithfulness_score: number;
    hallucination_rate_pct: number;
    evaluated_revision: string;
  };
  provider_telemetry: {
    embedding_model: string;
    generation_model: string;
    vector_dimension: number;
    hybrid_search_enabled: boolean;
  };
  tenant_live_telemetry?: {
    active_documents: number;
    indexed_vector_chunks: number;
    evaluated_responses: number;
    citation_coverage_pct: number;
    total_provenance_citations: number;
    anti_injection_status: string;
  };
  offline_benchmark_metrics?: {
    retrieval_precision_at_k: number;
    retrieval_recall_at_k: number;
    groundedness_faithfulness_score: number;
    hallucination_rejection_rate: number;
    mean_retrieval_latency_ms: number;
    embedding_dimension: number;
    distance_metric: string;
  };
  evaluation_methodology?: string;
}

