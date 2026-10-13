import React, { useState, useEffect } from "react";
import {
  User,
  Shield,
  Palette,
  Copy,
  Check,
  Sun,
  Moon,
  Monitor,
  Lock,
  Key,
  Database,
  FileSpreadsheet,
  Activity,
  RefreshCw,
  Clock,
  CheckCircle2,
  AlertTriangle,
} from "lucide-react";
import { useAuth } from "../hooks/useAuth";
import { useTheme, Theme } from "../context/ThemeContext";
import Badge from "../components/common/Badge";
import Button from "../components/common/Button";
import { auditService } from "../services/auditService";
import { evaluationService } from "../services/evaluationService";
import { AuditLogItem } from "../types/audit";
import { EvaluationMetricsResponse } from "../types/evaluation";

export const SettingsPage: React.FC = () => {
  const { user } = useAuth();
  const { theme, setTheme, resolvedTheme } = useTheme();
  const [activeTab, setActiveTab] = useState<
    "profile" | "security" | "appearance" | "audit" | "evaluation"
  >("profile");
  const [copiedId, setCopiedId] = useState(false);

  // Audit Logs State
  const [auditLogs, setAuditLogs] = useState<AuditLogItem[]>([]);
  const [loadingAudit, setLoadingAudit] = useState(false);
  const [auditError, setAuditError] = useState<string | null>(null);

  // Evaluation Metrics State
  const [metrics, setMetrics] = useState<EvaluationMetricsResponse | null>(null);
  const [loadingMetrics, setLoadingMetrics] = useState(false);
  const [metricsError, setMetricsError] = useState<string | null>(null);

  const handleCopyId = () => {
    if (user?.id) {
      navigator.clipboard.writeText(user.id);
      setCopiedId(true);
      setTimeout(() => setCopiedId(false), 2000);
    }
  };

  useEffect(() => {
    if (activeTab === "audit") {
      loadAuditLogs();
    } else if (activeTab === "evaluation") {
      loadEvaluationMetrics();
    }
  }, [activeTab]);

  const loadAuditLogs = async () => {
    setLoadingAudit(true);
    setAuditError(null);
    try {
      const res = await auditService.getAuditLogs(50, 0);
      setAuditLogs(res.items);
    } catch (err: any) {
      setAuditError(err?.response?.data?.detail || "Failed to retrieve audit logs.");
    } finally {
      setLoadingAudit(false);
    }
  };

  const loadEvaluationMetrics = async () => {
    setLoadingMetrics(true);
    setMetricsError(null);
    try {
      const res = await evaluationService.getEvaluationMetrics();
      setMetrics(res);
    } catch (err: any) {
      setMetricsError(err?.response?.data?.detail || "Failed to retrieve system metrics.");
    } finally {
      setLoadingMetrics(false);
    }
  };

  const themeOptions: {
    id: Theme;
    title: string;
    desc: string;
    icon: React.FC<{ className?: string }>;
  }[] = [
    {
      id: "light",
      title: "Enterprise Light",
      desc: "Calibrated high-contrast palette (#E9ECE8 canvas, #F4F5F2 surfaces, #267653 accent).",
      icon: Sun,
    },
    {
      id: "dark",
      title: "Enterprise Dark",
      desc: "Low-fatigue dark workspace (#171C19 canvas, #202622 surfaces, #42B883 accent).",
      icon: Moon,
    },
    {
      id: "system",
      title: "System Preference",
      desc: "Automatically sync with OS display settings and color preference.",
      icon: Monitor,
    },
  ];

  return (
    <div className="space-y-6">
      {/* Navigation tabs */}
      <div className="border-b border-border overflow-x-auto">
        <nav className="flex space-x-6 min-w-max">
          <button
            onClick={() => setActiveTab("profile")}
            className={`py-3 px-1 text-xs sm:text-sm font-semibold border-b-2 transition-colors flex items-center gap-2 cursor-pointer ${
              activeTab === "profile"
                ? "border-accent text-accent"
                : "border-transparent text-secondary hover:text-primary"
            }`}
          >
            <User className="w-4 h-4" />
            Profile & Tenant
          </button>
          <button
            onClick={() => setActiveTab("security")}
            className={`py-3 px-1 text-xs sm:text-sm font-semibold border-b-2 transition-colors flex items-center gap-2 cursor-pointer ${
              activeTab === "security"
                ? "border-accent text-accent"
                : "border-transparent text-secondary hover:text-primary"
            }`}
          >
            <Shield className="w-4 h-4" />
            Security & Compliance
          </button>
          <button
            onClick={() => setActiveTab("appearance")}
            className={`py-3 px-1 text-xs sm:text-sm font-semibold border-b-2 transition-colors flex items-center gap-2 cursor-pointer ${
              activeTab === "appearance"
                ? "border-accent text-accent"
                : "border-transparent text-secondary hover:text-primary"
            }`}
          >
            <Palette className="w-4 h-4" />
            Appearance & Themes
          </button>
          <button
            onClick={() => setActiveTab("audit")}
            className={`py-3 px-1 text-xs sm:text-sm font-semibold border-b-2 transition-colors flex items-center gap-2 cursor-pointer ${
              activeTab === "audit"
                ? "border-accent text-accent"
                : "border-transparent text-secondary hover:text-primary"
            }`}
          >
            <FileSpreadsheet className="w-4 h-4" />
            Audit Trail
          </button>
          <button
            onClick={() => setActiveTab("evaluation")}
            className={`py-3 px-1 text-xs sm:text-sm font-semibold border-b-2 transition-colors flex items-center gap-2 cursor-pointer ${
              activeTab === "evaluation"
                ? "border-accent text-accent"
                : "border-transparent text-secondary hover:text-primary"
            }`}
          >
            <Activity className="w-4 h-4" />
            Evaluation & Quality
          </button>
        </nav>
      </div>

      {/* Profile Tab */}
      {activeTab === "profile" && (
        <div className="bg-surface border border-border rounded-xl p-6 max-w-2xl space-y-6 transition-colors">
          <div>
            <h3 className="text-sm font-semibold text-primary">
              Account & Tenant Details
            </h3>
            <p className="text-xs text-secondary mt-0.5">
              Verified identity resolved from the authenticated JWT session.
            </p>
          </div>

          <div className="space-y-4 pt-4 border-t border-border">
            <div>
              <label className="block text-xs font-semibold text-secondary uppercase tracking-wider mb-1">
                Full Name
              </label>
              <p className="text-sm font-medium text-primary">
                {user?.full_name || "Enterprise User"}
              </p>
            </div>

            <div>
              <label className="block text-xs font-semibold text-secondary uppercase tracking-wider mb-1">
                Corporate Email Address
              </label>
              <p className="text-sm font-medium text-primary font-mono text-xs">
                {user?.email || "user@cogniva.enterprise"}
              </p>
            </div>

            <div>
              <label className="block text-xs font-semibold text-secondary uppercase tracking-wider mb-1">
                Tenant / User Identifier
              </label>
              <div className="flex items-center gap-2 max-w-md">
                <code className="text-xs bg-panel px-2.5 py-1 rounded border border-border text-primary font-mono truncate flex-1">
                  {user?.id || "e3b0c442-98fc-1c14-9af0-2a3b95ff1d1b"}
                </code>
                <Button
                  variant="outline"
                  size="xs"
                  onClick={handleCopyId}
                  className="shrink-0"
                >
                  {copiedId ? (
                    <Check className="w-3.5 h-3.5 text-accent" />
                  ) : (
                    <Copy className="w-3.5 h-3.5" />
                  )}
                </Button>
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-secondary uppercase tracking-wider mb-1">
                Account Status
              </label>
              <Badge variant="success" size="xs">
                Active Tenant
              </Badge>
            </div>
          </div>
        </div>
      )}

      {/* Security Tab */}
      {activeTab === "security" && (
        <div className="bg-surface border border-border rounded-xl p-6 max-w-2xl space-y-6 transition-colors">
          <div>
            <h3 className="text-sm font-semibold text-primary">
              Enterprise Security & Isolation
            </h3>
            <p className="text-xs text-secondary mt-0.5">
              Multi-tenant boundaries and transport layer security posture.
            </p>
          </div>

          <div className="space-y-4 pt-4 border-t border-border">
            <div className="flex items-start gap-3 p-3.5 rounded-lg bg-panel/40 border border-border">
              <Lock className="w-4 h-4 text-accent mt-0.5 shrink-0" />
              <div>
                <p className="text-xs font-semibold text-primary">Cryptographic Transport</p>
                <p className="text-[11px] text-secondary mt-0.5">
                  All requests encrypted using TLS 1.3 with SHA-256 certificate fingerprints.
                </p>
              </div>
            </div>

            <div className="flex items-start gap-3 p-3.5 rounded-lg bg-panel/40 border border-border">
              <Key className="w-4 h-4 text-accent mt-0.5 shrink-0" />
              <div>
                <p className="text-xs font-semibold text-primary">Authentication & Tokens</p>
                <p className="text-[11px] text-secondary mt-0.5">
                  Stateless JSON Web Tokens signed with HS256 algorithm and automated expiry invalidation.
                </p>
              </div>
            </div>

            <div className="flex items-start gap-3 p-3.5 rounded-lg bg-panel/40 border border-border">
              <Database className="w-4 h-4 text-accent mt-0.5 shrink-0" />
              <div>
                <p className="text-xs font-semibold text-primary">Tenant Data Isolation</p>
                <p className="text-[11px] text-secondary mt-0.5">
                  All vector similarities, document excerpts, and conversation history are strictly filtered by user ID at the SQL layer.
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Appearance Tab */}
      {activeTab === "appearance" && (
        <div className="bg-surface border border-border rounded-xl p-6 max-w-2xl space-y-6 transition-colors">
          <div>
            <h3 className="text-sm font-semibold text-primary">
              Interface Display & Theme
            </h3>
            <p className="text-xs text-secondary mt-0.5">
              Select your workspace theme mode. Preference is persisted locally and applied instantly.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-4 border-t border-border">
            {themeOptions.map((opt) => {
              const Icon = opt.icon;
              const isSelected = theme === opt.id;
              return (
                <button
                  key={opt.id}
                  onClick={() => setTheme(opt.id)}
                  className={`p-4 rounded-xl border text-left transition-all cursor-pointer ${
                    isSelected
                      ? "border-accent bg-panel ring-1 ring-accent"
                      : "border-border bg-surface hover:bg-panel/40"
                  }`}
                >
                  <div className="flex items-center justify-between mb-2">
                    <Icon className={`w-4 h-4 ${isSelected ? "text-accent" : "text-secondary"}`} />
                    {isSelected && (
                      <span className="w-2 h-2 rounded-full bg-accent" />
                    )}
                  </div>
                  <h4 className="text-xs font-semibold text-primary">{opt.title}</h4>
                  <p className="text-[11px] text-secondary mt-1 leading-snug">{opt.desc}</p>
                </button>
              );
            })}
          </div>

          <div className="p-3.5 rounded-lg bg-panel/40 border border-border flex items-center justify-between text-xs text-secondary">
            <span>Currently Active Palette:</span>
            <span className="font-semibold text-primary uppercase font-mono">
              {resolvedTheme} ({theme === "system" ? "System Auto" : "Manual"})
            </span>
          </div>
        </div>
      )}

      {/* Audit Trail Tab */}
      {activeTab === "audit" && (
        <div className="bg-surface border border-border rounded-xl p-6 space-y-4 transition-colors">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <div>
              <h3 className="text-sm font-semibold text-primary">
                Tenant Operational Audit Trail
              </h3>
              <p className="text-xs text-secondary mt-0.5">
                Immutable security logs of document access, comparisons, extractions, and queries.
              </p>
            </div>
            <Button
              variant="outline"
              size="xs"
              onClick={loadAuditLogs}
              disabled={loadingAudit}
              className="flex items-center gap-1.5 text-xs"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loadingAudit ? "animate-spin" : ""}`} />
              Refresh Logs
            </Button>
          </div>

          {loadingAudit ? (
            <div className="py-12 text-center text-xs text-secondary">
              <RefreshCw className="w-5 h-5 text-accent animate-spin mx-auto mb-2" />
              Loading security audit events...
            </div>
          ) : auditError ? (
            <div className="p-3.5 rounded bg-red-500/10 border border-red-500/20 text-xs text-red-600 dark:text-red-400">
              {auditError}
            </div>
          ) : auditLogs.length === 0 ? (
            <div className="py-12 text-center text-xs text-secondary">
              No audit records registered yet in this session.
            </div>
          ) : (
            <div className="overflow-x-auto border border-border rounded-lg">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="bg-panel/50 border-b border-border text-secondary font-medium">
                    <th className="py-2 px-3">Timestamp</th>
                    <th className="py-2 px-3">Action</th>
                    <th className="py-2 px-3">Resource Type</th>
                    <th className="py-2 px-3">Status</th>
                    <th className="py-2 px-3">Resource ID</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {auditLogs.map((log) => (
                    <tr key={log.id} className="hover:bg-panel/20 transition-colors">
                      <td className="py-2.5 px-3 text-secondary font-mono text-[11px] whitespace-nowrap">
                        {log.created_at ? new Date(log.created_at).toLocaleString() : "N/A"}
                      </td>
                      <td className="py-2.5 px-3 font-semibold text-primary font-mono text-[11px]">
                        {log.action}
                      </td>
                      <td className="py-2.5 px-3 text-secondary uppercase font-mono text-[10px]">
                        {log.resource_type}
                      </td>
                      <td className="py-2.5 px-3">
                        <Badge
                          variant={log.status === "SUCCESS" ? "success" : "danger"}
                          size="xs"
                        >
                          {log.status}
                        </Badge>
                      </td>
                      <td className="py-2.5 px-3 text-secondary font-mono text-[10px] truncate max-w-[140px]">
                        {log.resource_id || "--"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Evaluation & Quality Tab */}
      {activeTab === "evaluation" && (
        <div className="bg-surface border border-border rounded-xl p-6 space-y-6 transition-colors">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <div>
              <h3 className="text-sm font-semibold text-primary">
                System Quality & Evaluation Telemetry
              </h3>
              <p className="text-xs text-secondary mt-0.5">
                Authentic live retrieval measurements and grounded generation benchmark scores.
              </p>
            </div>
            <Button
              variant="outline"
              size="xs"
              onClick={loadEvaluationMetrics}
              disabled={loadingMetrics}
              className="flex items-center gap-1.5 text-xs"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loadingMetrics ? "animate-spin" : ""}`} />
              Refresh Telemetry
            </Button>
          </div>

          {loadingMetrics ? (
            <div className="py-12 text-center text-xs text-secondary">
              <RefreshCw className="w-5 h-5 text-accent animate-spin mx-auto mb-2" />
              Calculating live telemetry and benchmark coverage...
            </div>
          ) : metricsError ? (
            <div className="p-3.5 rounded bg-red-500/10 border border-red-500/20 text-xs text-red-600 dark:text-red-400">
              {metricsError}
            </div>
          ) : metrics ? (
            <div className="space-y-6">
              {/* Live Tenant Measurements */}
              <div>
                <h4 className="text-xs font-semibold text-primary uppercase tracking-wider mb-3">
                  Live Tenant Quality Metrics
                </h4>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  <div className="p-3.5 rounded-lg border border-border bg-panel/30">
                    <span className="text-[10px] text-secondary uppercase font-semibold">
                      Processed Docs
                    </span>
                    <p className="text-lg font-bold text-primary mt-1">
                      {metrics.live_metrics.processed_documents}
                    </p>
                  </div>
                  <div className="p-3.5 rounded-lg border border-border bg-panel/30">
                    <span className="text-[10px] text-secondary uppercase font-semibold">
                      Indexed Chunks
                    </span>
                    <p className="text-lg font-bold text-primary mt-1">
                      {metrics.live_metrics.total_indexed_chunks}
                    </p>
                  </div>
                  <div className="p-3.5 rounded-lg border border-border bg-panel/30">
                    <span className="text-[10px] text-secondary uppercase font-semibold">
                      Citation Coverage
                    </span>
                    <p className="text-lg font-bold text-accent mt-1">
                      {metrics.live_metrics.citation_coverage_pct}%
                    </p>
                  </div>
                  <div className="p-3.5 rounded-lg border border-border bg-panel/30">
                    <span className="text-[10px] text-secondary uppercase font-semibold">
                      Avg Citations / Answer
                    </span>
                    <p className="text-lg font-bold text-primary mt-1">
                      {metrics.live_metrics.avg_citations_per_answer}
                    </p>
                  </div>
                </div>
              </div>

              {/* Offline Benchmark Quality Scores */}
              <div>
                <h4 className="text-xs font-semibold text-primary uppercase tracking-wider mb-3">
                  Benchmark Accuracy Scores ({metrics.benchmark_metrics.dataset})
                </h4>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  <div className="p-3.5 rounded-lg border border-border bg-panel/30">
                    <span className="text-[10px] text-secondary uppercase font-semibold">
                      Retrieval Hit Rate @ 5
                    </span>
                    <p className="text-lg font-bold text-primary mt-1">
                      {(metrics.benchmark_metrics.retrieval_hit_rate_at_5 * 100).toFixed(1)}%
                    </p>
                  </div>
                  <div className="p-3.5 rounded-lg border border-border bg-panel/30">
                    <span className="text-[10px] text-secondary uppercase font-semibold">
                      Mean Reciprocal Rank (MRR)
                    </span>
                    <p className="text-lg font-bold text-primary mt-1">
                      {metrics.benchmark_metrics.retrieval_mrr.toFixed(3)}
                    </p>
                  </div>
                  <div className="p-3.5 rounded-lg border border-border bg-panel/30">
                    <span className="text-[10px] text-secondary uppercase font-semibold">
                      Faithfulness Score
                    </span>
                    <p className="text-lg font-bold text-emerald-600 dark:text-emerald-400 mt-1">
                      {(metrics.benchmark_metrics.groundedness_faithfulness_score * 100).toFixed(1)}%
                    </p>
                  </div>
                  <div className="p-3.5 rounded-lg border border-border bg-panel/30">
                    <span className="text-[10px] text-secondary uppercase font-semibold">
                      Hallucination Rate
                    </span>
                    <p className="text-lg font-bold text-accent mt-1">
                      {metrics.benchmark_metrics.hallucination_rate_pct}%
                    </p>
                  </div>
                </div>
              </div>

              {/* Architecture & Provider Telemetry */}
              <div>
                <h4 className="text-xs font-semibold text-primary uppercase tracking-wider mb-3">
                  Active Vector & Model Infrastructure
                </h4>
                <div className="p-4 rounded-lg border border-border bg-panel/20 grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                  <div>
                    <span className="text-secondary">Embedding Model:</span>
                    <p className="font-medium text-primary font-mono text-[11px] mt-0.5">
                      {metrics.provider_telemetry.embedding_model}
                    </p>
                  </div>
                  <div>
                    <span className="text-secondary">Synthesis Model:</span>
                    <p className="font-medium text-primary font-mono text-[11px] mt-0.5">
                      {metrics.provider_telemetry.generation_model}
                    </p>
                  </div>
                  <div>
                    <span className="text-secondary">Vector Dimensions:</span>
                    <p className="font-medium text-primary font-mono text-[11px] mt-0.5">
                      {metrics.provider_telemetry.vector_dimension} dims (pgvector)
                    </p>
                  </div>
                  <div>
                    <span className="text-secondary">Hybrid Retrieval Pipeline:</span>
                    <p className="font-medium text-accent font-mono text-[11px] mt-0.5">
                      {metrics.provider_telemetry.hybrid_search_enabled ? "Enabled (Vector + BM25 Boost)" : "Vector Only"}
                    </p>
                  </div>
                </div>
              </div>
            </div>
          ) : null}
        </div>
      )}
    </div>
  );
};

export default SettingsPage;
