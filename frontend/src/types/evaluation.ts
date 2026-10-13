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
}
