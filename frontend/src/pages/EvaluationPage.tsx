import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  Activity,
  Shield,
  CheckCircle2,
  Database,
  Cpu,
  Layers,
  RefreshCw,
  FileText,
  BarChart3,
  Target,
  Search,
  Zap,
  AlertCircle,
  ArrowRight,
  Lock,
  Clock,
  Sparkles,
  Info,
} from "lucide-react";
import { evaluationService } from "../services/evaluationService";
import { EvaluationMetricsResponse } from "../types/evaluation";
import Button from "../components/common/Button";
import Badge from "../components/common/Badge";

export const EvaluationPage: React.FC = () => {
  const [metrics, setMetrics] = useState<EvaluationMetricsResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchMetrics = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await evaluationService.getEvaluationMetrics();
      setMetrics(data);
    } catch (err: any) {
      setError(
        err?.response?.data?.detail ||
          err?.message ||
          "Failed to retrieve evaluation telemetry from the backend."
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMetrics();
  }, []);

  const formatTimestamp = (isoString?: string) => {
    if (!isoString) return "Just now";
    try {
      return new Date(isoString).toLocaleString(undefined, {
        dateStyle: "medium",
        timeStyle: "medium",
      });
    } catch {
      return isoString;
    }
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      {/* Header Banner */}
      <div className="bg-surface border border-border rounded-xl p-5 sm:p-6 transition-colors shadow-2xs">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="text-xs font-semibold text-accent uppercase tracking-wider flex items-center gap-1.5">
                <Activity className="w-3.5 h-3.5 text-accent animate-pulse" />
                Live System Telemetry
              </span>
              <span className="text-secondary text-xs">•</span>
              {metrics && (
                <span className="text-xs font-mono px-2 py-0.5 rounded bg-panel border border-border text-primary font-medium">
                  {metrics.tenant_scope}
                </span>
              )}
            </div>
            <h2 className="text-xl sm:text-2xl font-bold tracking-tight text-primary">
              Evaluation & Telemetry
            </h2>
            <p className="mt-1 text-xs sm:text-sm text-secondary max-w-2xl leading-relaxed">
              Real-time measurement of retrieval precision, tenant provenance coverage, and deterministic hallucination guardrails across your enterprise knowledge corpus.
            </p>
          </div>

          <div className="flex items-center gap-2.5 shrink-0">
            <Button
              variant="outline"
              size="sm"
              onClick={fetchMetrics}
              disabled={loading}
              className="flex items-center gap-1.5 text-xs"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
              Refresh Telemetry
            </Button>
            <Link to="/chat">
              <Button
                variant="primary"
                size="sm"
                icon={<Search className="w-3.5 h-3.5" />}
              >
                Test Retrieval
              </Button>
            </Link>
          </div>
        </div>

        {metrics && (
          <div className="mt-4 pt-4 border-t border-border flex flex-wrap items-center justify-between gap-3 text-xs text-secondary">
            <div className="flex items-center gap-2">
              <Clock className="w-3.5 h-3.5" />
              <span>Last Measured:</span>
              <span className="font-mono text-primary font-medium">
                {formatTimestamp(metrics.measured_at)}
              </span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              <span className="text-emerald-600 dark:text-emerald-400 font-medium">
                {metrics.live_metrics.service_uptime_status || "Healthy & Operational"}
              </span>
              <span className="text-secondary">•</span>
              <span className="font-mono text-[11px]">
                Revision: v{metrics.benchmark_metrics.evaluated_revision}
              </span>
            </div>
          </div>
        )}
      </div>

      {/* Loading State */}
      {loading && !metrics && (
        <div className="bg-surface border border-border rounded-xl p-12 text-center space-y-3">
          <RefreshCw className="w-8 h-8 text-accent animate-spin mx-auto" />
          <h3 className="text-sm font-semibold text-primary">
            Querying Live Tenant Telemetry...
          </h3>
          <p className="text-xs text-secondary max-w-md mx-auto">
            Aggregating processed document vectors, calculating citation coverage across recent answers, and verifying benchmark accuracy scores.
          </p>
        </div>
      )}

      {/* Error State */}
      {error && (
        <div className="bg-red-500/10 border border-red-500/25 rounded-xl p-5 flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-red-600 dark:text-red-400 shrink-0 mt-0.5" />
          <div className="flex-1">
            <h4 className="text-sm font-semibold text-red-600 dark:text-red-400">
              Telemetry Service Unavailable
            </h4>
            <p className="text-xs text-red-700/80 dark:text-red-300/80 mt-1">
              {error}
            </p>
            <div className="mt-3">
              <Button
                variant="outline"
                size="xs"
                onClick={fetchMetrics}
                className="text-xs border-red-500/30 text-red-600 dark:text-red-400 hover:bg-red-500/15"
              >
                Retry Connection
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Content When Metrics Loaded */}
      {metrics && (
        <>
          {/* Empty State Banner if 0 Documents Processed */}
          {metrics.live_metrics.processed_documents === 0 && (
            <div className="bg-panel/40 border border-border rounded-xl p-5 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
              <div className="flex items-start gap-3">
                <Info className="w-5 h-5 text-accent shrink-0 mt-0.5" />
                <div>
                  <h4 className="text-xs font-semibold text-primary uppercase tracking-wider">
                    Knowledge Base Empty
                  </h4>
                  <p className="text-xs text-secondary mt-0.5">
                    No documents have been indexed in this tenant workspace yet. Upload documents (PDF, DOCX, CSV) to activate live vector chunk retrieval telemetry.
                  </p>
                </div>
              </div>
              <Link to="/documents" className="shrink-0">
                <Button variant="primary" size="xs" icon={<ArrowRight className="w-3.5 h-3.5" />}>
                  Ingest Documents
                </Button>
              </Link>
            </div>
          )}

          {/* SECTION 1: Live Tenant Operational Telemetry */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Shield className="w-4 h-4 text-accent" />
                <h3 className="text-sm font-semibold text-primary uppercase tracking-wider">
                  Live Tenant Measurements ({metrics.tenant_scope})
                </h3>
              </div>
              <span className="text-[11px] text-secondary">
                Calculated strictly from your isolated tenant data
              </span>
            </div>

            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              {/* Processed Documents */}
              <div className="bg-surface border border-border rounded-xl p-4 transition-colors">
                <div className="flex items-center justify-between text-secondary">
                  <span className="text-xs font-medium">Processed Documents</span>
                  <FileText className="w-4 h-4" />
                </div>
                <div className="mt-2 flex items-baseline gap-2">
                  <span className="text-2xl font-bold text-primary">
                    {metrics.live_metrics.processed_documents}
                  </span>
                  <span className="text-xs text-secondary">ready</span>
                </div>
                <p className="mt-1 text-[11px] text-secondary">
                  Active in vector index
                </p>
              </div>

              {/* Indexed Vector Chunks */}
              <div className="bg-surface border border-border rounded-xl p-4 transition-colors">
                <div className="flex items-center justify-between text-secondary">
                  <span className="text-xs font-medium">Indexed Chunks</span>
                  <Layers className="w-4 h-4" />
                </div>
                <div className="mt-2 flex items-baseline gap-2">
                  <span className="text-2xl font-bold text-primary">
                    {metrics.live_metrics.total_indexed_chunks}
                  </span>
                  <span className="text-xs text-secondary">embeddings</span>
                </div>
                <p className="mt-1 text-[11px] text-secondary">
                  pgvector HNSW index
                </p>
              </div>

              {/* Citation Provenance Coverage */}
              <div className="bg-surface border border-border rounded-xl p-4 transition-colors">
                <div className="flex items-center justify-between text-secondary">
                  <span className="text-xs font-medium">Citation Coverage</span>
                  <Target className="w-4 h-4 text-accent" />
                </div>
                <div className="mt-2 flex items-baseline gap-2">
                  <span className="text-2xl font-bold text-accent">
                    {metrics.live_metrics.citation_coverage_pct}%
                  </span>
                </div>
                <div className="w-full bg-panel rounded-full h-1.5 mt-2 overflow-hidden">
                  <div
                    className="bg-accent h-1.5 rounded-full transition-all duration-500"
                    style={{ width: `${Math.min(metrics.live_metrics.citation_coverage_pct, 100)}%` }}
                  />
                </div>
                <p className="mt-1.5 text-[11px] text-secondary">
                  {metrics.live_metrics.recent_assistant_messages_sample > 0
                    ? `From ${metrics.live_metrics.recent_assistant_messages_sample} assistant replies`
                    : "Baseline target: >= 90%"}
                </p>
              </div>

              {/* Avg Citations & Latency */}
              <div className="bg-surface border border-border rounded-xl p-4 transition-colors">
                <div className="flex items-center justify-between text-secondary">
                  <span className="text-xs font-medium">Avg Citations / Answer</span>
                  <Sparkles className="w-4 h-4" />
                </div>
                <div className="mt-2 flex items-baseline gap-2">
                  <span className="text-2xl font-bold text-primary">
                    {metrics.live_metrics.avg_citations_per_answer}
                  </span>
                  <span className="text-xs text-secondary">sources</span>
                </div>
                <p className="mt-1 text-[11px] text-secondary flex items-center gap-1">
                  <Zap className="w-3 h-3 text-accent" />
                  ~{metrics.live_metrics.avg_generation_latency_ms} ms avg latency
                </p>
              </div>
            </div>
          </div>

          {/* SECTION 1.5: Operational Reliability & Background Processing */}
          {metrics.operational_telemetry && (
            <div className="space-y-3">
              <div className="flex items-center justify-between flex-wrap gap-2">
                <div className="flex items-center gap-2">
                  <Cpu className="w-4 h-4 text-accent" />
                  <h3 className="text-sm font-semibold text-primary uppercase tracking-wider">
                    Pipeline Operational Reliability & Ingestion Telemetry
                  </h3>
                </div>
                <Badge variant="neutral" className="text-[11px] font-mono">
                  {metrics.operational_telemetry.total_jobs} Total Jobs Evaluated
                </Badge>
              </div>

              <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                {/* Pipeline Success Rate */}
                <div className="bg-surface border border-border rounded-xl p-4 transition-colors">
                  <span className="text-[11px] text-secondary uppercase font-semibold block">
                    Pipeline Success Rate
                  </span>
                  <div className="mt-2 flex items-baseline gap-2">
                    <span className="text-2xl font-bold text-emerald-600 dark:text-emerald-400">
                      {metrics.operational_telemetry.success_rate_pct}%
                    </span>
                  </div>
                  <div className="w-full bg-panel rounded-full h-1.5 mt-2 overflow-hidden">
                    <div
                      className="bg-emerald-500 h-1.5 rounded-full"
                      style={{ width: `${Math.min(metrics.operational_telemetry.success_rate_pct, 100)}%` }}
                    />
                  </div>
                  <p className="mt-1.5 text-[11px] text-secondary">
                    {metrics.operational_telemetry.completed_jobs} completed / {metrics.operational_telemetry.failed_jobs} failed
                  </p>
                </div>

                {/* Mean Execution Duration */}
                <div className="bg-surface border border-border rounded-xl p-4 transition-colors">
                  <span className="text-[11px] text-secondary uppercase font-semibold block">
                    Mean Execution Duration
                  </span>
                  <div className="mt-2 flex items-baseline gap-2">
                    <span className="text-2xl font-bold text-primary font-mono">
                      {metrics.operational_telemetry.avg_duration_seconds}s
                    </span>
                  </div>
                  <p className="mt-2 text-[11px] text-secondary flex items-center gap-1">
                    <Clock className="w-3 h-3 text-secondary" />
                    Extract, chunk, embed & index
                  </p>
                </div>

                {/* Active & Queued Tasks */}
                <div className="bg-surface border border-border rounded-xl p-4 transition-colors">
                  <span className="text-[11px] text-secondary uppercase font-semibold block">
                    In-Flight Pipelines
                  </span>
                  <div className="mt-2 flex items-baseline gap-2">
                    <span className="text-2xl font-bold text-accent font-mono">
                      {metrics.operational_telemetry.active_jobs}
                    </span>
                    <span className="text-xs text-secondary">active tasks</span>
                  </div>
                  <p className="mt-2 text-[11px] text-secondary">
                    Bounded concurrency: 3 workers
                  </p>
                </div>

                {/* Stuck Jobs & Exhausted Retries */}
                <div className="bg-surface border border-border rounded-xl p-4 transition-colors">
                  <span className="text-[11px] text-secondary uppercase font-semibold block">
                    Diagnosed Pipeline Issues
                  </span>
                  <div className="mt-2 flex items-baseline gap-2">
                    <span
                      className={`text-2xl font-bold font-mono ${
                        metrics.operational_telemetry.stuck_jobs > 0 ||
                        metrics.operational_telemetry.retries_exhausted_jobs > 0
                          ? "text-amber-500"
                          : "text-primary"
                      }`}
                    >
                      {metrics.operational_telemetry.stuck_jobs +
                        metrics.operational_telemetry.retries_exhausted_jobs}
                    </span>
                    <span className="text-xs text-secondary">anomalies</span>
                  </div>
                  <p className="mt-2 text-[11px] text-secondary">
                    {metrics.operational_telemetry.stuck_jobs} stuck,{" "}
                    {metrics.operational_telemetry.retries_exhausted_jobs} retry-exhausted
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* SECTION 2: Deterministic Retrieval & Accuracy Benchmarks */}
          <div className="space-y-3">
            <div className="flex items-center justify-between flex-wrap gap-2">
              <div className="flex items-center gap-2">
                <BarChart3 className="w-4 h-4 text-accent" />
                <h3 className="text-sm font-semibold text-primary uppercase tracking-wider">
                  Retrieval Accuracy & Grounding Benchmarks
                </h3>
              </div>
              <Badge variant="neutral" className="text-[11px] font-mono">
                {metrics.benchmark_metrics.dataset}
              </Badge>
            </div>

            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              {/* Retrieval Hit Rate @ 5 */}
              <div className="bg-surface border border-border rounded-xl p-4 transition-colors">
                <span className="text-[11px] text-secondary uppercase font-semibold block">
                  Retrieval Hit Rate @ 5
                </span>
                <p className="text-2xl font-bold text-primary mt-1">
                  {(metrics.benchmark_metrics.retrieval_hit_rate_at_5 * 100).toFixed(1)}%
                </p>
                <div className="w-full bg-panel rounded-full h-1.5 mt-2 overflow-hidden">
                  <div
                    className="bg-emerald-500 h-1.5 rounded-full"
                    style={{
                      width: `${metrics.benchmark_metrics.retrieval_hit_rate_at_5 * 100}%`,
                    }}
                  />
                </div>
                <p className="mt-1.5 text-[11px] text-secondary">
                  Target threshold: ≥ 90.0%
                </p>
              </div>

              {/* Mean Reciprocal Rank (MRR) */}
              <div className="bg-surface border border-border rounded-xl p-4 transition-colors">
                <span className="text-[11px] text-secondary uppercase font-semibold block">
                  Mean Reciprocal Rank (MRR)
                </span>
                <p className="text-2xl font-bold text-primary mt-1">
                  {metrics.benchmark_metrics.retrieval_mrr.toFixed(3)}
                </p>
                <div className="w-full bg-panel rounded-full h-1.5 mt-2 overflow-hidden">
                  <div
                    className="bg-emerald-500 h-1.5 rounded-full"
                    style={{
                      width: `${metrics.benchmark_metrics.retrieval_mrr * 100}%`,
                    }}
                  />
                </div>
                <p className="mt-1.5 text-[11px] text-secondary">
                  Rank precision across top passages
                </p>
              </div>

              {/* Faithfulness / Groundedness */}
              <div className="bg-surface border border-border rounded-xl p-4 transition-colors">
                <span className="text-[11px] text-secondary uppercase font-semibold block">
                  Faithfulness Score
                </span>
                <p className="text-2xl font-bold text-emerald-600 dark:text-emerald-400 mt-1">
                  {(metrics.benchmark_metrics.groundedness_faithfulness_score * 100).toFixed(1)}%
                </p>
                <div className="w-full bg-panel rounded-full h-1.5 mt-2 overflow-hidden">
                  <div
                    className="bg-emerald-500 h-1.5 rounded-full"
                    style={{
                      width: `${metrics.benchmark_metrics.groundedness_faithfulness_score * 100}%`,
                    }}
                  />
                </div>
                <p className="mt-1.5 text-[11px] text-secondary">
                  Direct passage verification rate
                </p>
              </div>

              {/* Hallucination Rate */}
              <div className="bg-surface border border-border rounded-xl p-4 transition-colors">
                <span className="text-[11px] text-secondary uppercase font-semibold block">
                  Hallucination Rate
                </span>
                <p className="text-2xl font-bold text-accent mt-1">
                  {metrics.benchmark_metrics.hallucination_rate_pct.toFixed(1)}%
                </p>
                <div className="w-full bg-panel rounded-full h-1.5 mt-2 overflow-hidden">
                  <div
                    className="bg-accent h-1.5 rounded-full"
                    style={{ width: "100%" }}
                  />
                </div>
                <p className="mt-1.5 text-[11px] text-secondary">
                  Strict citation enforcement
                </p>
              </div>
            </div>

            <div className="p-3 bg-panel/30 border border-border rounded-lg flex items-center justify-between text-xs text-secondary">
              <span>
                Standardized Evaluation Corpus:{" "}
                <strong className="text-primary font-medium">
                  {metrics.benchmark_metrics.queries_evaluated} multi-turn enterprise queries
                </strong>
              </span>
              <span className="font-mono text-[11px]">
                Deterministic Provider: Active
              </span>
            </div>
          </div>

          {/* SECTION 3: Model & Vector Infrastructure Telemetry */}
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <Cpu className="w-4 h-4 text-accent" />
              <h3 className="text-sm font-semibold text-primary uppercase tracking-wider">
                Inference & Vector Infrastructure Telemetry
              </h3>
            </div>

            <div className="bg-surface border border-border rounded-xl p-5 transition-colors">
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 text-xs">
                {/* Embedding Model */}
                <div className="p-3.5 rounded-lg border border-border bg-panel/20">
                  <div className="flex items-center gap-1.5 text-secondary mb-1">
                    <Database className="w-3.5 h-3.5 text-accent" />
                    <span className="font-semibold uppercase text-[10px]">Embedding Engine</span>
                  </div>
                  <p className="font-mono text-sm font-bold text-primary">
                    {metrics.provider_telemetry.embedding_model}
                  </p>
                  <p className="text-[11px] text-secondary mt-1">
                    Dense semantic vector representation
                  </p>
                </div>

                {/* Synthesis Model */}
                <div className="p-3.5 rounded-lg border border-border bg-panel/20">
                  <div className="flex items-center gap-1.5 text-secondary mb-1">
                    <Cpu className="w-3.5 h-3.5 text-accent" />
                    <span className="font-semibold uppercase text-[10px]">Synthesis LLM</span>
                  </div>
                  <p className="font-mono text-sm font-bold text-primary">
                    {metrics.provider_telemetry.generation_model}
                  </p>
                  <p className="text-[11px] text-secondary mt-1">
                    Grounded answering & structured extraction
                  </p>
                </div>

                {/* Vector Dimensions */}
                <div className="p-3.5 rounded-lg border border-border bg-panel/20">
                  <div className="flex items-center gap-1.5 text-secondary mb-1">
                    <Layers className="w-3.5 h-3.5 text-accent" />
                    <span className="font-semibold uppercase text-[10px]">Vector Dimensions</span>
                  </div>
                  <p className="font-mono text-sm font-bold text-primary">
                    {metrics.provider_telemetry.vector_dimension} dims
                  </p>
                  <p className="text-[11px] text-secondary mt-1">
                    PostgreSQL + pgvector storage
                  </p>
                </div>

                {/* Hybrid Search Pipeline */}
                <div className="p-3.5 rounded-lg border border-border bg-panel/20">
                  <div className="flex items-center gap-1.5 text-secondary mb-1">
                    <Search className="w-3.5 h-3.5 text-accent" />
                    <span className="font-semibold uppercase text-[10px]">Hybrid Retrieval</span>
                  </div>
                  <p className="font-mono text-sm font-bold text-accent">
                    {metrics.provider_telemetry.hybrid_search_enabled
                      ? "Dense + Keyword Boost"
                      : "Dense Vector Only"}
                  </p>
                  <p className="text-[11px] text-secondary mt-1">
                    Reciprocal Rank Fusion enabled
                  </p>
                </div>
              </div>
            </div>
          </div>

          {/* SECTION 4: Architecture Assurance & Tenant Isolation */}
          <div className="bg-panel/25 border border-border rounded-xl p-5 space-y-3">
            <div className="flex items-center gap-2">
              <Lock className="w-4 h-4 text-accent" />
              <h4 className="text-xs font-semibold text-primary uppercase tracking-wider">
                Evaluation Methodology & Governance Standards
              </h4>
            </div>
            <p className="text-xs text-secondary leading-relaxed">
              {metrics.evaluation_methodology ||
                "Dual-layer evaluation framework: Live session telemetry combined with offline deterministic regression test benchmarks."}
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-2 text-xs">
              <div className="p-3 rounded border border-border bg-surface/70">
                <div className="flex items-center gap-1.5 text-emerald-600 dark:text-emerald-400 font-semibold mb-1">
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  Tenant Data Isolation
                </div>
                <p className="text-[11px] text-secondary">
                  User queries, ingested documents, and chunk vectors are strictly scoped by tenant credentials at the database layer.
                </p>
              </div>

              <div className="p-3 rounded border border-border bg-surface/70">
                <div className="flex items-center gap-1.5 text-emerald-600 dark:text-emerald-400 font-semibold mb-1">
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  Provenance Integrity
                </div>
                <p className="text-[11px] text-secondary">
                  Every substantive factual statement requires an explicit passage citation ([S#]) mapped to an indexed document excerpt.
                </p>
              </div>

              <div className="p-3 rounded border border-border bg-surface/70">
                <div className="flex items-center gap-1.5 text-emerald-600 dark:text-emerald-400 font-semibold mb-1">
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  Honest Refusal Guardrail
                </div>
                <p className="text-[11px] text-secondary">
                  When a question cannot be substantiated by the uploaded corpus, Cogniva refuses to hallucinate and provides partial answers when applicable.
                </p>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
};

export default EvaluationPage;
