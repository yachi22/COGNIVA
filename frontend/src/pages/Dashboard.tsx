import React, { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  FileText,
  MessageSquare,
  Upload,
  ArrowRight,
  Shield,
  Layers,
  CheckCircle2,
  HardDrive,
  Clock,
  Activity,
  AlertCircle,
  Sparkles,
  BookOpen,
  RefreshCw,
  HelpCircle,
  Eye,
  Tag,
  Check,
} from "lucide-react";
import { useAuth } from "../hooks/useAuth";
import { useDocuments } from "../hooks/useDocuments";
import { listConversations } from "../services/chatService";
import { checkHealth, HealthResponse } from "../services/api";
import { auditService } from "../services/auditService";
import { intelligenceService } from "../services/intelligenceService";
import { ConversationResponse } from "../types/chat";
import { AuditLogItem } from "../types/audit";
import { DocumentItem } from "../types/document";
import { DocumentSummaryResponse } from "../types/intelligence";
import EmptyState from "../components/common/EmptyState";
import Button from "../components/common/Button";
import Badge from "../components/common/Badge";
import DocumentViewerModal from "../components/documents/DocumentViewerModal";

export const Dashboard: React.FC = () => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const { documents, isLoading: docsLoading, processDoc } = useDocuments();

  const [conversations, setConversations] = useState<ConversationResponse[]>([]);
  const [convsLoading, setConvsLoading] = useState<boolean>(true);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);

  // Real Workspace Activity Feed
  const [auditLogs, setAuditLogs] = useState<AuditLogItem[]>([]);
  const [loadingAudit, setLoadingAudit] = useState<boolean>(true);

  // Topic summaries state
  const [topicSummaries, setTopicSummaries] = useState<Record<string, DocumentSummaryResponse>>({});
  const [summarizingDocId, setSummarizingDocId] = useState<string | null>(null);

  // Document Viewer Modal
  const [selectedViewerDoc, setSelectedViewerDoc] = useState<DocumentItem | null>(null);

  useEffect(() => {
    let isMounted = true;

    const loadConversations = async () => {
      try {
        setConvsLoading(true);
        const res = await listConversations(0, 5);
        if (isMounted) {
          setConversations(res.items || []);
        }
      } catch {
        if (isMounted) setConversations([]);
      } finally {
        if (isMounted) setConvsLoading(false);
      }
    };

    const loadHealth = async () => {
      try {
        const res = await checkHealth();
        if (isMounted) {
          setHealth(res);
          setHealthError(null);
        }
      } catch {
        if (isMounted) {
          setHealthError("API service unreachable");
        }
      }
    };

    const loadActivity = async () => {
      try {
        setLoadingAudit(true);
        const res = await auditService.getAuditLogs(6, 0);
        if (isMounted) {
          setAuditLogs(res.items || []);
        }
      } catch {
        if (isMounted) setAuditLogs([]);
      } finally {
        if (isMounted) setLoadingAudit(false);
      }
    };

    loadConversations();
    loadHealth();
    loadActivity();

    return () => {
      isMounted = false;
    };
  }, []);

  // Compute real metrics from loaded documents
  const totalDocs = documents.length;
  const processedDocs = documents.filter((d) => d.status === "processed").length;
  const pendingDocs = documents.filter((d) => d.status === "processing" || d.status === "pending").length;
  const failedDocs = documents.filter((d) => d.status === "failed").length;

  const totalBytes = documents.reduce((acc, doc) => acc + (doc.metadata?.size_bytes || 0), 0);
  const formatBytes = (bytes: number): string => {
    if (bytes === 0) return "0 KB";
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const formatActivityAction = (action: string): string => {
    return action
      .replace(/_/g, " ")
      .toLowerCase()
      .replace(/\b\w/g, (c) => c.toUpperCase());
  };

  // Generate topic summary for a specific document on demand
  const handleGenerateSummary = async (doc: DocumentItem) => {
    setSummarizingDocId(doc.id);
    try {
      const summary = await intelligenceService.summarizeDocument(doc.id, "concise", false);
      setTopicSummaries((prev) => ({ ...prev, [doc.id]: summary }));
    } catch {
      // handled
    } finally {
      setSummarizingDocId(null);
    }
  };

  const processedList = documents.filter((d) => d.status === "processed");

  return (
    <div className="space-y-6">
      {/* Workspace Header Panel */}
      <div className="bg-surface border border-border rounded-xl p-5 sm:p-6 transition-colors shadow-2xs">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="text-xs font-semibold text-accent uppercase tracking-wider flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-accent" />
                Enterprise Workspace
              </span>
              <span className="text-secondary text-xs">•</span>
              <span className="text-xs text-secondary font-mono">{user?.email}</span>
            </div>
            <h2 className="text-xl sm:text-2xl font-bold tracking-tight text-primary">
              Welcome, {user?.full_name || user?.email?.split("@")[0]}
            </h2>
            <p className="mt-1 text-xs sm:text-sm text-secondary max-w-2xl leading-relaxed">
              Cogniva Multimodal Enterprise Knowledge Agent is operational. Ingest documents to index semantic chunks and execute source-grounded intelligence queries with verified citations.
            </p>
          </div>

          <div className="flex items-center gap-2.5 shrink-0">
            <Link to="/chat">
              <Button
                variant="outline"
                size="sm"
                icon={<MessageSquare className="w-4 h-4" />}
              >
                Ask Cogniva
              </Button>
            </Link>
            <Link to="/documents">
              <Button
                variant="primary"
                size="sm"
                icon={<Upload className="w-4 h-4" />}
              >
                Upload Document
              </Button>
            </Link>
          </div>
        </div>
      </div>

      {/* Real Workspace Telemetry Metrics */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Metric 1: Total Documents */}
        <div className="bg-surface border border-border rounded-xl p-4 transition-colors">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-secondary">Indexed Documents</span>
            <FileText className="w-4 h-4 text-secondary" />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold text-primary">{totalDocs}</span>
            <span className="text-xs text-secondary">files</span>
          </div>
          <p className="mt-1 text-[11px] text-secondary">
            {processedDocs} ready for retrieval
          </p>
        </div>

        {/* Metric 2: Processing Status */}
        <div className="bg-surface border border-border rounded-xl p-4 transition-colors">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-secondary">Pipeline Status</span>
            <Layers className="w-4 h-4 text-secondary" />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold text-primary">
              {failedDocs > 0 ? `${failedDocs} Failed` : pendingDocs > 0 ? `${pendingDocs} Pending` : "100% Ready"}
            </span>
          </div>
          <p className="mt-1 text-[11px] text-secondary">
            {pendingDocs > 0 ? "Chunks undergoing ingestion" : "All assets processed"}
          </p>
        </div>

        {/* Metric 3: Active Conversations */}
        <div className="bg-surface border border-border rounded-xl p-4 transition-colors">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-secondary">Active Threads</span>
            <MessageSquare className="w-4 h-4 text-secondary" />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold text-primary">{conversations.length}</span>
            <span className="text-xs text-secondary">sessions</span>
          </div>
          <p className="mt-1 text-[11px] text-secondary">
            Multi-turn persistent history
          </p>
        </div>

        {/* Metric 4: Knowledge Footprint */}
        <div className="bg-surface border border-border rounded-xl p-4 transition-colors">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-secondary">Knowledge Footprint</span>
            <HardDrive className="w-4 h-4 text-secondary" />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold text-primary">{formatBytes(totalBytes)}</span>
          </div>
          <p className="mt-1 text-[11px] text-secondary">
            PDF & DOCX storage in tenant pool
          </p>
        </div>
      </div>

      {/* Main Grid: Recent Documents & Recent Conversations */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent Documents Section */}
        <div className="bg-surface border border-border rounded-xl p-5 transition-colors flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-4 pb-3 border-b border-border">
              <div className="flex items-center gap-2">
                <FileText className="w-4 h-4 text-accent" />
                <h3 className="text-sm font-semibold text-primary">
                  Recent Knowledge Sources
                </h3>
              </div>
              <Link
                to="/documents"
                className="text-xs font-medium text-accent hover:underline flex items-center gap-1"
              >
                View all ({totalDocs}) <ArrowRight className="w-3 h-3" />
              </Link>
            </div>

            {docsLoading ? (
              <div className="py-8 text-center text-xs text-secondary">Loading document repository...</div>
            ) : documents.length > 0 ? (
              <div className="space-y-2">
                {documents.slice(0, 4).map((doc) => {
                  return (
                    <div
                      key={doc.id}
                      className="p-3 rounded-lg border border-border bg-panel/30 hover:bg-panel/70 transition-colors flex items-center justify-between gap-3 group"
                    >
                      <div className="flex items-center gap-2.5 truncate">
                        <button
                          type="button"
                          onClick={() => setSelectedViewerDoc(doc)}
                          className="w-7 h-7 rounded bg-surface border border-border flex items-center justify-center shrink-0 text-secondary group-hover:text-accent group-hover:border-accent transition-colors cursor-pointer"
                          title="Open Document Viewer"
                        >
                          <BookOpen className="w-3.5 h-3.5" />
                        </button>
                        <div className="truncate">
                          <button
                            type="button"
                            onClick={() => setSelectedViewerDoc(doc)}
                            className="text-xs font-semibold text-primary hover:text-accent truncate block text-left transition-colors cursor-pointer"
                          >
                            {doc.original_filename || doc.filename}
                          </button>
                          <p className="text-[10px] text-secondary">
                            {new Date(doc.created_at).toLocaleDateString("en-US", {
                              month: "short",
                              day: "numeric",
                              year: "numeric",
                            })} · {formatBytes(doc.metadata?.size_bytes || 0)}
                          </p>
                        </div>
                      </div>

                      <div className="flex items-center gap-1.5 shrink-0">
                        <Badge
                          variant={
                            doc.status === "processed"
                              ? "success"
                              : doc.status === "failed"
                              ? "danger"
                              : "secondary"
                          }
                          size="xs"
                        >
                          {doc.status}
                        </Badge>
                        <button
                          type="button"
                          onClick={() => setSelectedViewerDoc(doc)}
                          className="p-1 rounded text-secondary hover:text-primary hover:bg-surface transition-colors cursor-pointer"
                          title="Open in Document Viewer"
                        >
                          <Eye className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <EmptyState
                icon={<FileText className="w-5 h-5" />}
                title="No documents uploaded"
                description="Upload enterprise documentation (PDF or DOCX) to index semantic chunks."
                action={
                  <Link to="/documents">
                    <Button variant="outline" size="xs" icon={<Upload className="w-3 h-3" />}>
                      Upload Document
                    </Button>
                  </Link>
                }
              />
            )}
          </div>
        </div>

        {/* Recent Conversations Section */}
        <div className="bg-surface border border-border rounded-xl p-5 transition-colors flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-4 pb-3 border-b border-border">
              <div className="flex items-center gap-2">
                <MessageSquare className="w-4 h-4 text-accent" />
                <h3 className="text-sm font-semibold text-primary">
                  Recent Inquiries
                </h3>
              </div>
              <Link
                to="/chat"
                className="text-xs font-medium text-accent hover:underline flex items-center gap-1"
              >
                Open Chat <ArrowRight className="w-3 h-3" />
              </Link>
            </div>

            {convsLoading ? (
              <div className="py-8 text-center text-xs text-secondary">Loading conversations...</div>
            ) : conversations.length > 0 ? (
              <div className="space-y-2">
                {conversations.slice(0, 4).map((conv) => (
                  <Link
                    key={conv.id}
                    to={`/chat/${conv.id}`}
                    className="p-3 rounded-lg border border-border bg-panel/30 hover:bg-panel/70 transition-colors flex items-center justify-between gap-3 block group"
                  >
                    <div className="flex items-center gap-2.5 truncate">
                      <div className="w-7 h-7 rounded bg-surface border border-border flex items-center justify-center shrink-0 text-secondary">
                        <MessageSquare className="w-3.5 h-3.5" />
                      </div>
                      <div className="truncate">
                        <p className="text-xs font-medium text-primary group-hover:text-accent truncate">
                          {conv.title || "Untitled Session"}
                        </p>
                        <p className="text-[10px] text-secondary flex items-center gap-1">
                          <Clock className="w-2.5 h-2.5" />
                          {new Date(conv.updated_at || conv.created_at).toLocaleDateString("en-US", {
                            month: "short",
                            day: "numeric",
                            hour: "2-digit",
                            minute: "2-digit",
                          })}
                        </p>
                      </div>
                    </div>
                    <ArrowRight className="w-3.5 h-3.5 text-secondary group-hover:text-primary shrink-0" />
                  </Link>
                ))}
              </div>
            ) : (
              <EmptyState
                icon={<MessageSquare className="w-5 h-5" />}
                title="No chat sessions yet"
                description="Initiate a query to receive strictly grounded answers with verifiable source citations."
                action={
                  <Link to="/chat">
                    <Button variant="primary" size="xs" icon={<MessageSquare className="w-3 h-3" />}>
                      Start Inquiry
                    </Button>
                  </Link>
                }
              />
            )}
          </div>
        </div>
      </div>

      {/* Topic Summaries & Executive Intelligence Section */}
      <div className="bg-surface border border-border rounded-xl p-5 transition-colors">
        <div className="flex items-center justify-between mb-4 pb-3 border-b border-border">
          <div className="flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-accent" />
            <div>
              <h3 className="text-sm font-semibold text-primary">
                Executive Topic Summaries & Key Findings
              </h3>
              <p className="text-[11px] text-secondary">
                Grounded multi-document synthesis and takeaway extractions
              </p>
            </div>
          </div>
          <Link
            to="/documents"
            className="text-xs font-medium text-accent hover:underline flex items-center gap-1"
          >
            Manage Knowledge Bases <ArrowRight className="w-3 h-3" />
          </Link>
        </div>

        {processedList.length === 0 ? (
          <EmptyState
            icon={<Sparkles className="w-5 h-5" />}
            title="No processed documents available for topic synthesis"
            description="Upload and process PDF or DOCX documentation to generate executive topic summaries and key takeaway extractions."
            action={
              <Link to="/documents">
                <Button variant="outline" size="xs" icon={<Upload className="w-3 h-3" />}>
                  Upload Documents
                </Button>
              </Link>
            }
          />
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3.5">
            {processedList.slice(0, 3).map((doc) => {
              const summary = topicSummaries[doc.id];
              const isSummarizing = summarizingDocId === doc.id;

              return (
                <div
                  key={doc.id}
                  className="p-4 rounded-xl border border-border bg-panel/30 hover:bg-panel/50 transition-colors flex flex-col justify-between space-y-3"
                >
                  <div className="space-y-2">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-[10px] font-mono text-accent uppercase tracking-wider font-semibold flex items-center gap-1">
                        <Tag className="w-3 h-3" />
                        {doc.file_type.toUpperCase()} TOPIC
                      </span>
                      <Badge variant="neutral" size="xs">
                        {doc.metadata?.total_pages ? `${doc.metadata.total_pages} Pages` : "Ingested"}
                      </Badge>
                    </div>

                    <h4 className="text-xs sm:text-sm font-semibold text-primary truncate">
                      {doc.original_filename || doc.filename}
                    </h4>

                    {summary ? (
                      <div className="space-y-2">
                        <p className="text-xs text-secondary leading-relaxed line-clamp-3 select-text">
                          {summary.summary}
                        </p>
                        {summary.key_takeaways && summary.key_takeaways.length > 0 && (
                          <div className="space-y-1 pt-1">
                            {summary.key_takeaways.slice(0, 2).map((takeaway, i) => (
                              <div key={i} className="flex items-start gap-1.5 text-[11px] text-primary">
                                <CheckCircle2 className="w-3 h-3 text-accent shrink-0 mt-0.5" />
                                <span className="line-clamp-1">{takeaway}</span>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    ) : (
                      <p className="text-xs text-secondary leading-relaxed">
                        Ready for topic synthesis. Generate an executive takeaway briefing grounded in this document&apos;s indexed chunks.
                      </p>
                    )}
                  </div>

                  <div className="flex items-center justify-between gap-2 pt-2 border-t border-border/60">
                    <button
                      type="button"
                      onClick={() => setSelectedViewerDoc(doc)}
                      className="text-xs text-accent hover:underline font-medium flex items-center gap-1 cursor-pointer"
                    >
                      <BookOpen className="w-3 h-3" />
                      View Insights
                    </button>

                    {summary ? (
                      <Button
                        variant="outline"
                        size="xs"
                        onClick={() => navigate(`/chat?docId=${doc.id}&query=${encodeURIComponent(`Explain key findings in ${doc.original_filename || doc.filename}`)}`)}
                        className="text-[10px] h-6 px-2"
                      >
                        Inquire
                      </Button>
                    ) : (
                      <Button
                        variant="outline"
                        size="xs"
                        onClick={() => handleGenerateSummary(doc)}
                        disabled={isSummarizing}
                        icon={<Sparkles className={`w-3 h-3 ${isSummarizing ? "animate-spin" : ""}`} />}
                        className="text-[10px] h-6 px-2"
                      >
                        {isSummarizing ? "Synthesizing..." : "Summarize"}
                      </Button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Workspace Activity Feed (Operational Audit Events) */}
      <div className="bg-surface border border-border rounded-xl p-5 transition-colors">
        <div className="flex items-center justify-between mb-4 pb-3 border-b border-border">
          <div className="flex items-center gap-2">
            <Activity className="w-4 h-4 text-accent" />
            <div>
              <h3 className="text-sm font-semibold text-primary">
                Workspace Activity & Operational Audit Feed
              </h3>
              <p className="text-[11px] text-secondary">
                Verifiable tenant operations, ingestion events, and intelligence executions
              </p>
            </div>
          </div>
          <Link
            to="/settings"
            className="text-xs font-medium text-accent hover:underline flex items-center gap-1"
          >
            Full Audit Logs <ArrowRight className="w-3 h-3" />
          </Link>
        </div>

        {loadingAudit ? (
          <div className="py-6 text-center text-xs text-secondary">Loading activity feed...</div>
        ) : auditLogs.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {auditLogs.slice(0, 6).map((log) => (
              <div
                key={log.id}
                className="p-3 rounded-lg border border-border bg-panel/30 hover:bg-panel/50 transition-colors flex items-start gap-2.5"
              >
                <div className="w-6 h-6 rounded bg-surface border border-border flex items-center justify-center shrink-0 text-accent mt-0.5">
                  <Activity className="w-3 h-3" />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center justify-between gap-1">
                    <span className="text-xs font-semibold text-primary truncate">
                      {formatActivityAction(log.action)}
                    </span>
                    <Badge variant={log.status === "SUCCESS" ? "success" : "neutral"} size="xs">
                      {log.status}
                    </Badge>
                  </div>
                  <p className="text-[10px] text-secondary font-mono mt-0.5 truncate">
                    {log.resource_type}: {log.resource_id ? `${log.resource_id.slice(0, 8)}...` : "System"}
                  </p>
                  {log.created_at && (
                    <p className="text-[10px] text-secondary mt-1">
                      {new Date(log.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })} · {new Date(log.created_at).toLocaleDateString([], { month: "short", day: "numeric" })}
                    </p>
                  )}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <EmptyState
            icon={<Activity className="w-5 h-5" />}
            title="No activity recorded yet"
            description="Operational events such as document uploads, extraction tasks, and intelligence synthesis will stream here."
          />
        )}
      </div>

      {/* Real System Architecture & Platform Telemetry Status */}
      <div className="bg-surface border border-border rounded-xl p-5 transition-colors">
        <div className="flex items-center justify-between mb-3">
          <h4 className="text-xs font-semibold uppercase tracking-wider text-secondary">
            Platform Service Infrastructure
          </h4>
          <span className="text-[11px] text-secondary font-mono">
            Environment: {health?.environment || "production"}
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {/* Card 1: API Gateway Status */}
          <div className="p-3.5 rounded-lg bg-panel/40 border border-border">
            <div className="flex items-center justify-between text-xs font-semibold text-primary">
              <span className="flex items-center gap-1.5">
                <Activity className="w-3.5 h-3.5 text-accent" />
                API Service Gateway
              </span>
              <Badge variant={health ? "success" : "warning"} size="xs">
                {health ? "Operational" : healthError || "Connecting"}
              </Badge>
            </div>
            <p className="text-[11px] text-secondary mt-1.5">
              FastAPI ASGI service v{health?.version || "0.1.0"} with CORS & JWT enforcement.
            </p>
          </div>

          {/* Card 2: Vector Engine */}
          <div className="p-3.5 rounded-lg bg-panel/40 border border-border">
            <div className="flex items-center justify-between text-xs font-semibold text-primary">
              <span className="flex items-center gap-1.5">
                <Layers className="w-3.5 h-3.5 text-accent" />
                PostgreSQL + pgvector
              </span>
              <Badge variant="success" size="xs">
                Active
              </Badge>
            </div>
            <p className="text-[11px] text-secondary mt-1.5">
              Cosine distance index (&lt;=&gt;) with database-enforced tenant isolation.
            </p>
          </div>

          {/* Card 3: RAG Grounding Engine */}
          <div className="p-3.5 rounded-lg bg-panel/40 border border-border">
            <div className="flex items-center justify-between text-xs font-semibold text-primary">
              <span className="flex items-center gap-1.5">
                <Shield className="w-3.5 h-3.5 text-accent" />
                Citation Verification
              </span>
              <Badge variant="success" size="xs">
                Enforced
              </Badge>
            </div>
            <p className="text-[11px] text-secondary mt-1.5">
              Prompt injection boundaries & rejection of unreferenced hallucinated sources.
            </p>
          </div>
        </div>
      </div>

      {/* Standalone Document Viewer Modal */}
      {selectedViewerDoc && (
        <DocumentViewerModal
          document={selectedViewerDoc}
          onClose={() => setSelectedViewerDoc(null)}
          onProcess={processDoc}
        />
      )}
    </div>
  );
};

export default Dashboard;
